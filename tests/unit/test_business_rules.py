from app.core.exceptions import (
    DuplicateResourceException,
    InactiveWarehouseException,
    InsufficientStockException,
    ResourceNotFoundException,
    WareFlowException,
)
from app.services.idempotency_service import IdempotencyService


def test_idempotency_request_hash_is_order_invariant():
    """Verifies that dictionaries with different key orders produce identical SHA-256 hashes."""
    payload_a = {"order_number": "ORD-123", "items": [{"product_id": 1, "quantity": 5}]}
    payload_b = {"items": [{"product_id": 1, "quantity": 5}], "order_number": "ORD-123"}

    hash_a = IdempotencyService.calculate_request_hash(payload_a)
    hash_b = IdempotencyService.calculate_request_hash(payload_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_idempotency_request_hash_detects_value_changes():
    """Verifies that different payloads produce distinct hashes."""
    payload_a = {"items": [{"product_id": 1, "quantity": 5}]}
    payload_b = {"items": [{"product_id": 1, "quantity": 6}]}

    hash_a = IdempotencyService.calculate_request_hash(payload_a)
    hash_b = IdempotencyService.calculate_request_hash(payload_b)

    assert hash_a != hash_b


def test_exception_inheritance():
    """Verifies all domain exceptions inherit from WareFlowException."""
    assert issubclass(ResourceNotFoundException, WareFlowException)
    assert issubclass(DuplicateResourceException, WareFlowException)
    assert issubclass(InactiveWarehouseException, WareFlowException)
    assert issubclass(InsufficientStockException, WareFlowException)
