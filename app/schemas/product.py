from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None)
    price: Decimal = Field(..., gt=0, decimal_places=2)


class ProductCreate(ProductBase):
    sku: str = Field(..., min_length=1, max_length=64, description="Unique SKU code")


class ProductResponse(ProductBase):
    id: int
    sku: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
