import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    DuplicateResourceException,
    IdempotencyConflictException,
    InactiveWarehouseException,
    InsufficientStockException,
    InvalidAllocationException,
    InvalidOrderStateException,
    ResourceNotFoundException,
    WareFlowException,
)

logger = logging.getLogger(__name__)


def create_error_response(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ResourceNotFoundException)
    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundException):
        return create_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="RESOURCE_NOT_FOUND",
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(DuplicateResourceException)
    async def duplicate_resource_handler(request: Request, exc: DuplicateResourceException):
        return create_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_RESOURCE",
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(InactiveWarehouseException)
    async def inactive_warehouse_handler(request: Request, exc: InactiveWarehouseException):
        return create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INACTIVE_WAREHOUSE",
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(InsufficientStockException)
    async def insufficient_stock_handler(request: Request, exc: InsufficientStockException):
        return create_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="INSUFFICIENT_STOCK",
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(InvalidOrderStateException)
    async def invalid_order_state_handler(request: Request, exc: InvalidOrderStateException):
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_ORDER_STATE",
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(IdempotencyConflictException)
    async def idempotency_conflict_handler(request: Request, exc: IdempotencyConflictException):
        return create_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_CONFLICT",
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(InvalidAllocationException)
    async def invalid_allocation_handler(request: Request, exc: InvalidAllocationException):
        return create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_ALLOCATION",
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(WareFlowException)
    async def generic_wareflow_handler(request: Request, exc: WareFlowException):
        return create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST",
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        logger.error("Database integrity error occurred: %s", exc)
        return create_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="DATABASE_INTEGRITY_VIOLATION",
            message="Operation violated a database constraint.",
            details={"orig": str(exc.orig) if hasattr(exc, "orig") else None},
        )
