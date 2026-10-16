from typing import Any


class WareFlowException(Exception):
    """Base exception for all WareFlow domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ResourceNotFoundException(WareFlowException):
    """Raised when an entity is not found."""


class DuplicateResourceException(WareFlowException):
    """Raised when unique constraints are violated at business level."""


class InactiveWarehouseException(WareFlowException):
    """Raised when an operation targets an inactive warehouse."""


class InsufficientStockException(WareFlowException):
    """Raised when available stock cannot fulfill an order requirement."""


class InvalidOrderStateException(WareFlowException):
    """Raised when an order transition is illegal (e.g. double cancellation)."""


class IdempotencyConflictException(WareFlowException):
    """Raised when an idempotency key is reused with mismatched parameters or is currently processing."""


class InvalidAllocationException(WareFlowException):
    """Raised when an allocation request has invalid data (e.g. non-positive quantity)."""
