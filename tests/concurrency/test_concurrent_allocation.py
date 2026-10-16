import concurrent.futures
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InsufficientStockException
from app.models.allocation import OrderAllocation
from app.models.inventory import WarehouseInventory
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.schemas.order import OrderCreate, OrderItemCreate
from app.services.allocation_service import OrderAllocationService
from tests.conftest import TestingSessionLocal


def test_concurrent_orders_prevent_overselling():
    """
    Simulates high concurrency against PostgreSQL:
    - 10 units available in stock.
    - 15 concurrent worker threads attempt to purchase 2 units each (total demand: 30 units).
    - Invariant: Exactly 5 orders succeed, exactly 10 fail.
    - PostgreSQL row-level locks (SELECT ... FOR UPDATE) prevent any overselling or negative inventory.
    """
    # 1. Setup seed data in a fresh session
    setup_session = TestingSessionLocal()
    try:
        product = Product(sku="CONCURRENT-LAPTOP", name="Hot Product", price=Decimal("999.00"))
        warehouse = Warehouse(code="WH-CONCURRENT-01", name="Central Hub", is_active=True)
        setup_session.add_all([product, warehouse])
        setup_session.flush()

        inventory = WarehouseInventory(
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity_available=10,
            quantity_reserved=0,
        )
        setup_session.add(inventory)
        setup_session.commit()

        prod_id = product.id
        wh_id = warehouse.id
    finally:
        setup_session.close()

    # 2. Worker function executed across concurrent threads
    def place_order_worker(worker_id: int) -> bool:
        worker_db: Session = TestingSessionLocal()
        try:
            order_in = OrderCreate(
                order_number=f"CONC-ORD-{worker_id:02d}",
                items=[OrderItemCreate(product_id=prod_id, quantity=2)],
            )
            OrderAllocationService.create_order_with_allocation(db=worker_db, order_in=order_in)
            worker_db.commit()
            return True
        except InsufficientStockException:
            worker_db.rollback()
            return False
        except Exception:
            worker_db.rollback()
            raise
        finally:
            worker_db.close()

    # 3. Fire 15 concurrent threads simultaneously
    num_threads = 15
    results: list[bool] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(place_order_worker, i) for i in range(num_threads)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # 4. Verify outcomes
    successful_orders = sum(1 for r in results if r is True)
    failed_orders = sum(1 for r in results if r is False)

    assert successful_orders == 5, f"Expected exactly 5 successful orders, got {successful_orders}"
    assert failed_orders == 10, f"Expected exactly 10 failed orders, got {failed_orders}"

    # 5. Verify physical PostgreSQL invariants
    verify_session = TestingSessionLocal()
    try:
        inv = verify_session.scalar(
            select(WarehouseInventory).where(
                WarehouseInventory.product_id == prod_id,
                WarehouseInventory.warehouse_id == wh_id,
            )
        )
        assert inv.quantity_available == 0, f"Available stock must be exactly 0, got {inv.quantity_available}"
        assert inv.quantity_reserved == 10, f"Reserved stock must be exactly 10, got {inv.quantity_reserved}"

        total_allocations = verify_session.scalars(
            select(OrderAllocation).where(OrderAllocation.warehouse_id == wh_id)
        ).all()
        total_allocated_units = sum(a.quantity_allocated for a in total_allocations)
        assert total_allocated_units == 10, f"Total allocated units must equal 10, got {total_allocated_units}"
    finally:
        verify_session.close()
