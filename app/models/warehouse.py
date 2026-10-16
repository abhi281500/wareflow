from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.allocation import OrderAllocation
    from app.models.inventory import WarehouseInventory


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inventory_records: Mapped[list["WarehouseInventory"]] = relationship(
        "WarehouseInventory", back_populates="warehouse", cascade="all, delete-orphan"
    )
    allocations: Mapped[list["OrderAllocation"]] = relationship("OrderAllocation", back_populates="warehouse")
