from pydantic import BaseModel


class InventorySummaryResponse(BaseModel):
    total_products: int
    total_warehouses: int
    total_available_stock: int
    total_reserved_stock: int


class WarehouseStockSummary(BaseModel):
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    total_available: int
    total_reserved: int


class OrderStatusCountsResponse(BaseModel):
    allocated: int
    cancelled: int
    pending: int
    total_orders: int
