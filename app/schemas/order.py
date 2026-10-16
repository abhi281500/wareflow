from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0, description="Order item quantity must be positive")


class OrderCreate(BaseModel):
    order_number: str | None = Field(default=None, max_length=64)
    items: list[OrderItemCreate] = Field(..., min_length=1, description="Order must contain at least one item")


class OrderAllocationResponse(BaseModel):
    id: int
    order_item_id: int
    warehouse_id: int
    quantity_allocated: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    allocations: list[OrderAllocationResponse] = []

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    order_number: str
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse] = []
    allocations: list[OrderAllocationResponse] = []

    model_config = ConfigDict(from_attributes=True)
