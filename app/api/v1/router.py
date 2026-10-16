from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    health,
    inventory,
    orders,
    products,
    warehouses,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(products.router)
api_router.include_router(warehouses.router)
api_router.include_router(inventory.router)
api_router.include_router(orders.router)
api_router.include_router(analytics.router)
