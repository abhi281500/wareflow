import logging

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ResourceNotFoundException
from app.db.session import get_db
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderResponse
from app.services.allocation_service import OrderAllocationService
from app.services.idempotency_service import IdempotencyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_in: OrderCreate,
    response: Response,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """
    Creates an order and allocates stock transactionally across warehouses.
    Supports safe retry via the Idempotency-Key HTTP header.
    """
    # 1. Check idempotency if key provided
    if idempotency_key:
        cached_record = IdempotencyService.acquire_key(
            db=db,
            idempotency_key=idempotency_key,
            payload=order_in.model_dump(),
        )
        if cached_record and cached_record.response_body:
            response.status_code = cached_record.response_code or status.HTTP_200_OK
            return cached_record.response_body

    try:
        # 2. Execute transactional order allocation
        order = OrderAllocationService.create_order_with_allocation(
            db=db,
            order_in=order_in,
        )
        db.commit()

        # Re-fetch order with relationships loaded for serialization
        fresh_order = db.scalar(
            select(Order)
            .where(Order.id == order.id)
            .options(
                joinedload(Order.items),
                joinedload(Order.allocations),
            )
        )
        serialized_response = jsonable_encoder(OrderResponse.model_validate(fresh_order))

        # 3. Complete idempotency record
        if idempotency_key:
            IdempotencyService.complete_key(
                db=db,
                idempotency_key=idempotency_key,
                status_code=status.HTTP_201_CREATED,
                response_body=serialized_response,
            )
            db.commit()

        return serialized_response

    except Exception:
        db.rollback()
        if idempotency_key:
            # Mark key as failed in a separate transaction so the client can retry cleanly
            try:
                fail_db = next(get_db())
                IdempotencyService.fail_key(fail_db, idempotency_key)
                fail_db.commit()
            except Exception as fail_err:
                logger.error("Failed to update idempotency failure status: %s", fail_err)
        raise


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Retrieves order details, order items, and allocation breakdown."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            joinedload(Order.items),
            joinedload(Order.allocations),
        )
    )
    order = db.scalar(stmt)
    if not order:
        raise ResourceNotFoundException(f"Order with ID {order_id} not found")
    return order


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    """Cancels an order and atomically restores allocated stock."""
    try:
        order = OrderAllocationService.cancel_order(db=db, order_id=order_id)
        db.commit()

        fresh_order = db.scalar(
            select(Order)
            .where(Order.id == order.id)
            .options(
                joinedload(Order.items),
                joinedload(Order.allocations),
            )
        )
        return fresh_order
    except Exception:
        db.rollback()
        raise
