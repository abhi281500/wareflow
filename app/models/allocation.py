from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order, OrderItem
    from app.models.warehouse import Warehouse


class OrderAllocation(Base):
    __tablename__ = "order_allocations"
    __table_args__ = (CheckConstraint("quantity_allocated > 0", name="ck_allocation_quantity_positive"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity_allocated: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="allocations")
    order_item: Mapped["OrderItem"] = relationship("OrderItem", back_populates="allocations")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="allocations")
