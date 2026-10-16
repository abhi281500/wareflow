from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateResourceException, ResourceNotFoundException
from app.db.session import get_db
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseResponse, WarehouseUpdateStatus

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse(warehouse_in: WarehouseCreate, db: Session = Depends(get_db)):
    """Creates a new warehouse with a unique code."""
    existing = db.scalar(select(Warehouse).where(Warehouse.code == warehouse_in.code))
    if existing:
        raise DuplicateResourceException(f"Warehouse with code '{warehouse_in.code}' already exists")

    warehouse = Warehouse(
        code=warehouse_in.code,
        name=warehouse_in.name,
        location=warehouse_in.location,
        is_active=warehouse_in.is_active,
    )
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


@router.get("", response_model=list[WarehouseResponse])
def list_warehouses(
    is_active: bool | None = None,
    db: Session = Depends(get_db),
):
    """Lists all warehouses with optional active status filter."""
    stmt = select(Warehouse)
    if is_active is not None:
        stmt = stmt.where(Warehouse.is_active == is_active)
    return list(db.scalars(stmt).all())


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    """Retrieves a single warehouse by ID."""
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise ResourceNotFoundException(f"Warehouse with ID {warehouse_id} not found")
    return warehouse


@router.patch("/{warehouse_id}/status", response_model=WarehouseResponse)
def update_warehouse_status(
    warehouse_id: int,
    status_update: WarehouseUpdateStatus,
    db: Session = Depends(get_db),
):
    """Activates or deactivates a warehouse."""
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise ResourceNotFoundException(f"Warehouse with ID {warehouse_id} not found")
    warehouse.is_active = status_update.is_active
    db.commit()
    db.refresh(warehouse)
    return warehouse
