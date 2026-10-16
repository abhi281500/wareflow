from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.inventory import (
    InventoryDetailedResponse,
    InventoryResponse,
    RestockRequest,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post("/restock", response_model=InventoryResponse, status_code=status.HTTP_200_OK)
def restock_inventory(
    restock_in: RestockRequest,
    db: Session = Depends(get_db),
):
    """Restocks inventory for a product in an active warehouse."""
    inventory = InventoryService.restock(
        db=db,
        product_id=restock_in.product_id,
        warehouse_id=restock_in.warehouse_id,
        quantity=restock_in.quantity,
    )
    db.commit()
    db.refresh(inventory)
    return inventory


@router.get("", response_model=list[InventoryResponse])
def get_inventory(
    product_id: int | None = Query(None, description="Filter by product ID"),
    warehouse_id: int | None = Query(None, description="Filter by warehouse ID"),
    db: Session = Depends(get_db),
):
    """Retrieves raw inventory records."""
    return InventoryService.get_inventory_records(
        db=db,
        product_id=product_id,
        warehouse_id=warehouse_id,
    )


@router.get("/detailed", response_model=list[InventoryDetailedResponse])
def get_detailed_inventory(
    product_id: int | None = Query(None, description="Filter by product ID"),
    warehouse_id: int | None = Query(None, description="Filter by warehouse ID"),
    db: Session = Depends(get_db),
):
    """Retrieves enriched inventory records including SKU and Warehouse codes."""
    return InventoryService.get_detailed_inventory(
        db=db,
        product_id=product_id,
        warehouse_id=warehouse_id,
    )
