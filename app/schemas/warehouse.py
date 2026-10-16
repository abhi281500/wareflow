from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WarehouseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)


class WarehouseCreate(WarehouseBase):
    code: str = Field(..., min_length=1, max_length=64, description="Unique warehouse code")


class WarehouseUpdateStatus(BaseModel):
    is_active: bool


class WarehouseResponse(WarehouseBase):
    id: int
    code: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
