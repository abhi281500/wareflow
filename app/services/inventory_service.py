import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InactiveWarehouseException,
    InvalidAllocationException,
    ResourceNotFoundException,
)
from app.models.inventory import WarehouseInventory
from app.models.product import Product
from app.models.warehouse import Warehouse

logger = logging.getLogger(__name__)


class InventoryService:
    @staticmethod
    def restock(db: Session, product_id: int, warehouse_id: int, quantity: int) -> WarehouseInventory:
        """Restocks product quantity in a specified active warehouse."""
        if quantity <= 0:
            raise InvalidAllocationException("Restock quantity must be strictly positive")

        # 1. Verify product exists
        product = db.get(Product, product_id)
        if not product:
            raise ResourceNotFoundException(f"Product with ID {product_id} not found")

        # 2. Verify warehouse exists and is active
        warehouse = db.get(Warehouse, warehouse_id)
        if not warehouse:
            raise ResourceNotFoundException(f"Warehouse with ID {warehouse_id} not found")
        if not warehouse.is_active:
            raise InactiveWarehouseException(
                f"Warehouse '{warehouse.code}' (ID {warehouse_id}) is inactive; cannot restock"
            )

        # 3. Fetch or initialize inventory record with row-level lock
        stmt = (
            select(WarehouseInventory)
            .where(
                WarehouseInventory.product_id == product_id,
                WarehouseInventory.warehouse_id == warehouse_id,
            )
            .with_for_update()
        )
        inventory = db.scalar(stmt)

        if not inventory:
            inventory = WarehouseInventory(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity_available=quantity,
                quantity_reserved=0,
            )
            db.add(inventory)
        else:
            inventory.quantity_available += quantity

        db.flush()
        logger.info(
            "Restocked %s units for product %s in warehouse %s. New available: %s",
            quantity,
            product_id,
            warehouse_id,
            inventory.quantity_available,
        )
        return inventory

    @staticmethod
    def get_inventory_records(
        db: Session,
        product_id: int | None = None,
        warehouse_id: int | None = None,
    ) -> list[WarehouseInventory]:
        stmt = select(WarehouseInventory)
        if product_id is not None:
            stmt = stmt.where(WarehouseInventory.product_id == product_id)
        if warehouse_id is not None:
            stmt = stmt.where(WarehouseInventory.warehouse_id == warehouse_id)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_detailed_inventory(
        db: Session,
        product_id: int | None = None,
        warehouse_id: int | None = None,
    ) -> list[dict]:
        stmt = (
            select(
                WarehouseInventory.id,
                WarehouseInventory.product_id,
                Product.sku.label("product_sku"),
                Product.name.label("product_name"),
                WarehouseInventory.warehouse_id,
                Warehouse.code.label("warehouse_code"),
                Warehouse.name.label("warehouse_name"),
                WarehouseInventory.quantity_available,
                WarehouseInventory.quantity_reserved,
                (WarehouseInventory.quantity_available + WarehouseInventory.quantity_reserved).label("total_quantity"),
                WarehouseInventory.updated_at,
            )
            .join(Product, WarehouseInventory.product_id == Product.id)
            .join(Warehouse, WarehouseInventory.warehouse_id == Warehouse.id)
        )
        if product_id is not None:
            stmt = stmt.where(WarehouseInventory.product_id == product_id)
        if warehouse_id is not None:
            stmt = stmt.where(WarehouseInventory.warehouse_id == warehouse_id)

        rows = db.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    def get_reorder_alerts(db: Session, threshold: int = 10) -> list[dict]:
        stmt = (
            select(
                WarehouseInventory.product_id,
                Product.sku.label("product_sku"),
                Product.name.label("product_name"),
                WarehouseInventory.warehouse_id,
                Warehouse.code.label("warehouse_code"),
                WarehouseInventory.quantity_available,
            )
            .join(Product, WarehouseInventory.product_id == Product.id)
            .join(Warehouse, WarehouseInventory.warehouse_id == Warehouse.id)
            .where(WarehouseInventory.quantity_available <= threshold)
            .order_by(WarehouseInventory.quantity_available.asc())
        )
        rows = db.execute(stmt).mappings().all()
        return [{**dict(row), "threshold": threshold} for row in rows]
