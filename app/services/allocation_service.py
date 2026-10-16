import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InactiveWarehouseException,
    InsufficientStockException,
    InvalidAllocationException,
    InvalidOrderStateException,
    ResourceNotFoundException,
)
from app.models.allocation import OrderAllocation
from app.models.inventory import WarehouseInventory
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.schemas.order import OrderCreate

logger = logging.getLogger(__name__)


class OrderAllocationService:
    @staticmethod
    def create_order_with_allocation(
        db: Session,
        order_in: OrderCreate,
    ) -> Order:
        """
        Creates and transactionally allocates an order across active warehouses.
        Uses deterministic row-level locking (SELECT ... FOR UPDATE) to prevent
        race conditions, overselling, and deadlocks.
        """
        if not order_in.items:
            raise InvalidAllocationException("Order must have at least one item")

        # 1. Aggregate requested quantities per product to avoid internal duplicates
        requested_qty_by_product: dict[int, int] = {}
        for item in order_in.items:
            if item.quantity <= 0:
                raise InvalidAllocationException(
                    f"Quantity for product {item.product_id} must be positive, got {item.quantity}"
                )
            requested_qty_by_product[item.product_id] = requested_qty_by_product.get(item.product_id, 0) + item.quantity

        product_ids = sorted(requested_qty_by_product.keys())

        # 2. Verify all products exist and retrieve pricing
        products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
        products_by_id = {p.id: p for p in products}

        missing_ids = set(product_ids) - set(products_by_id.keys())
        if missing_ids:
            raise ResourceNotFoundException(f"Products with IDs {list(missing_ids)} do not exist")

        # 3. Retrieve all active warehouses
        active_warehouses = db.scalars(select(Warehouse).where(Warehouse.is_active.is_(True))).all()
        if not active_warehouses:
            raise InactiveWarehouseException("No active warehouses available for fulfillment")

        active_warehouse_ids = {w.id for w in active_warehouses}

        # 4. DETERMINISTIC ROW-LEVEL LOCKING:
        # Lock inventory rows ordered strictly by (product_id ASC, warehouse_id ASC).
        # This completely eliminates circular-wait deadlock conditions across concurrent transactions.
        inventory_stmt = (
            select(WarehouseInventory)
            .where(
                WarehouseInventory.product_id.in_(product_ids),
                WarehouseInventory.warehouse_id.in_(active_warehouse_ids),
            )
            .order_by(WarehouseInventory.product_id.asc(), WarehouseInventory.warehouse_id.asc())
            .with_for_update()
        )
        locked_inventories = db.scalars(inventory_stmt).all()

        # Group locked inventory rows: product_id -> list of WarehouseInventory
        inv_by_product_warehouse: dict[tuple[int, int], WarehouseInventory] = {
            (inv.product_id, inv.warehouse_id): inv for inv in locked_inventories
        }
        inv_by_product: dict[int, list[WarehouseInventory]] = {pid: [] for pid in product_ids}
        for inv in locked_inventories:
            inv_by_product[inv.product_id].append(inv)

        # 5. ALLOCATION STRATEGY:
        # Strategy A: Check if a single warehouse can fulfill all items (preferred for logistics)
        single_wh_candidate: int | None = None
        for wh in active_warehouses:
            wh_can_fulfill_all = True
            for pid, req_qty in requested_qty_by_product.items():
                inv = inv_by_product_warehouse.get((pid, wh.id))
                if not inv or inv.quantity_available < req_qty:
                    wh_can_fulfill_all = False
                    break
            if wh_can_fulfill_all:
                single_wh_candidate = wh.id
                break

        # Calculate planned allocations: dict of (product_id, warehouse_id) -> quantity_allocated
        planned_allocations: dict[tuple[int, int], int] = {}

        if single_wh_candidate is not None:
            # Single-warehouse fulfillment
            for pid, req_qty in requested_qty_by_product.items():
                planned_allocations[(pid, single_wh_candidate)] = req_qty
        else:
            # Strategy B: Multi-warehouse split allocation
            for pid, req_qty in requested_qty_by_product.items():
                available_records = inv_by_product.get(pid, [])
                # Sort warehouses with most available stock first
                available_records_sorted = sorted(
                    [r for r in available_records if r.quantity_available > 0],
                    key=lambda r: r.quantity_available,
                    reverse=True,
                )

                remaining_to_allocate = req_qty
                for inv_rec in available_records_sorted:
                    if remaining_to_allocate <= 0:
                        break
                    take = min(inv_rec.quantity_available, remaining_to_allocate)
                    planned_allocations[(pid, inv_rec.warehouse_id)] = take
                    remaining_to_allocate -= take

                if remaining_to_allocate > 0:
                    product_obj = products_by_id[pid]
                    total_avail = sum(r.quantity_available for r in available_records)
                    raise InsufficientStockException(
                        f"Insufficient stock for product '{product_obj.sku}'. "
                        f"Requested: {req_qty}, Available across active warehouses: {total_avail}"
                    )

        # 6. Apply deductions and create DB entities
        order_number = order_in.order_number or f"ORD-{uuid.uuid4().hex[:8].upper()}"
        order = Order(
            order_number=order_number,
            status=OrderStatus.ALLOCATED.value,
        )
        db.add(order)
        db.flush()

        # Create OrderItems and OrderAllocations
        for pid, req_qty in requested_qty_by_product.items():
            product_obj = products_by_id[pid]
            order_item = OrderItem(
                order_id=order.id,
                product_id=pid,
                quantity=req_qty,
                unit_price=product_obj.price,
            )
            db.add(order_item)
            db.flush()

            # Find matching planned allocations for this product
            for (alloc_pid, alloc_wh_id), alloc_qty in planned_allocations.items():
                if alloc_pid == pid and alloc_qty > 0:
                    allocation = OrderAllocation(
                        order_id=order.id,
                        order_item_id=order_item.id,
                        warehouse_id=alloc_wh_id,
                        quantity_allocated=alloc_qty,
                    )
                    db.add(allocation)

                    # Update locked inventory balance
                    inv = inv_by_product_warehouse[(pid, alloc_wh_id)]
                    inv.quantity_available -= alloc_qty
                    inv.quantity_reserved += alloc_qty

        db.flush()
        logger.info("Order %s successfully allocated and committed.", order.order_number)
        return order

    @staticmethod
    def cancel_order(db: Session, order_id: int) -> Order:
        """
        Cancels an allocated order and releases reserved stock back to available stock.
        Guarantees that cancellation is atomic and cannot release stock twice.
        """
        # 1. Lock the order row (without outer joins to avoid PostgreSQL FOR UPDATE errors)
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        order = db.scalar(stmt)
        if not order:
            raise ResourceNotFoundException(f"Order with ID {order_id} not found")

        if order.status == OrderStatus.CANCELLED.value:
            raise InvalidOrderStateException(f"Order {order.order_number} is already cancelled")

        if order.status != OrderStatus.ALLOCATED.value:
            raise InvalidOrderStateException(f"Cannot cancel order {order.order_number} with status '{order.status}'")

        # 2. Extract product-warehouse pairs from allocations
        items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
        allocations = db.scalars(select(OrderAllocation).where(OrderAllocation.order_id == order.id)).all()
        if allocations:
            item_by_id = {item.id: item for item in items}
            pairs: list[tuple[int, int, int]] = []
            for alloc in allocations:
                item = item_by_id.get(alloc.order_item_id)
                if item:
                    pairs.append((item.product_id, alloc.warehouse_id, alloc.quantity_allocated))

            # Sort deterministically by (product_id, warehouse_id)
            sorted_pairs = sorted(pairs, key=lambda x: (x[0], x[1]))
            product_ids = sorted({p[0] for p in sorted_pairs})
            warehouse_ids = sorted({p[1] for p in sorted_pairs})

            # Lock inventory rows
            inv_stmt = (
                select(WarehouseInventory)
                .where(
                    WarehouseInventory.product_id.in_(product_ids),
                    WarehouseInventory.warehouse_id.in_(warehouse_ids),
                )
                .order_by(WarehouseInventory.product_id.asc(), WarehouseInventory.warehouse_id.asc())
                .with_for_update()
            )
            locked_invs = db.scalars(inv_stmt).all()
            inv_map = {(inv.product_id, inv.warehouse_id): inv for inv in locked_invs}

            # Release stock: decrement reserved, increment available
            for pid, wh_id, qty in sorted_pairs:
                inv = inv_map.get((pid, wh_id))
                if inv:
                    inv.quantity_reserved = max(0, inv.quantity_reserved - qty)
                    inv.quantity_available += qty

        # 3. Transition order status
        order.status = OrderStatus.CANCELLED.value
        db.flush()
        logger.info("Order %s cancelled and stock released.", order.order_number)
        return order
