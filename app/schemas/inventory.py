from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RestockRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    warehouse_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0, description="Quantity to add must be positive")


class InventoryResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    quantity_available: int
    quantity_reserved: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryDetailedResponse(BaseModel):
    id: int
    product_id: int
    product_sku: str
    product_name: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    quantity_available: int
    quantity_reserved: int
    total_quantity: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReorderAlertResponse(BaseModel):
    product_id: int
    product_sku: str
    product_name: str
    warehouse_id: int
    warehouse_code: str
    quantity_available: int
    threshold: int
