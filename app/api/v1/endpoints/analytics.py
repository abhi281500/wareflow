from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.inventory import WarehouseInventory
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.schemas.analytics import (
    InventorySummaryResponse,
    OrderStatusCountsResponse,
    WarehouseStockSummary,
)
from app.schemas.inventory import ReorderAlertResponse
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=InventorySummaryResponse)
def get_inventory_summary(db: Session = Depends(get_db)):
    """Provides high-level system metrics across inventory, products, and warehouses."""
    total_products = db.scalar(select(func.count(Product.id))) or 0
    total_warehouses = db.scalar(select(func.count(Warehouse.id))) or 0
    total_available = db.scalar(select(func.coalesce(func.sum(WarehouseInventory.quantity_available), 0))) or 0
    total_reserved = db.scalar(select(func.coalesce(func.sum(WarehouseInventory.quantity_reserved), 0))) or 0

    return InventorySummaryResponse(
        total_products=total_products,
        total_warehouses=total_warehouses,
        total_available_stock=total_available,
        total_reserved_stock=total_reserved,
    )


@router.get("/warehouse-stock", response_model=list[WarehouseStockSummary])
def get_warehouse_stock_summary(db: Session = Depends(get_db)):
    """Aggregates inventory counts per warehouse."""
    stmt = (
        select(
            Warehouse.id.label("warehouse_id"),
            Warehouse.code.label("warehouse_code"),
            Warehouse.name.label("warehouse_name"),
            func.coalesce(func.sum(WarehouseInventory.quantity_available), 0).label("total_available"),
            func.coalesce(func.sum(WarehouseInventory.quantity_reserved), 0).label("total_reserved"),
        )
        .outerjoin(WarehouseInventory, Warehouse.id == WarehouseInventory.warehouse_id)
        .group_by(Warehouse.id, Warehouse.code, Warehouse.name)
        .order_by(Warehouse.code.asc())
    )
    rows = db.execute(stmt).mappings().all()
    return [WarehouseStockSummary(**dict(r)) for r in rows]


@router.get("/reorder-alerts", response_model=list[ReorderAlertResponse])
def get_reorder_alerts(
    threshold: int = Query(10, ge=1, description="Stock alert threshold"),
    db: Session = Depends(get_db),
):
    """Lists inventory locations where available stock is below or at threshold."""
    alerts = InventoryService.get_reorder_alerts(db=db, threshold=threshold)
    return [ReorderAlertResponse(**a) for a in alerts]


@router.get("/order-status-counts", response_model=OrderStatusCountsResponse)
def get_order_status_counts(db: Session = Depends(get_db)):
    """Counts orders grouped by status."""
    stmt = select(Order.status, func.count(Order.id)).group_by(Order.status)
    counts = dict(db.execute(stmt).all())

    allocated = counts.get(OrderStatus.ALLOCATED.value, 0)
    cancelled = counts.get(OrderStatus.CANCELLED.value, 0)
    pending = counts.get(OrderStatus.PENDING.value, 0)

    return OrderStatusCountsResponse(
        allocated=allocated,
        cancelled=cancelled,
        pending=pending,
        total_orders=allocated + cancelled + pending,
    )
