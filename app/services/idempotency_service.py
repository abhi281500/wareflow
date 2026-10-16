import hashlib
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import IdempotencyConflictException
from app.models.idempotency import IdempotencyRecord, IdempotencyStatus

logger = logging.getLogger(__name__)


class IdempotencyService:
    @staticmethod
    def calculate_request_hash(payload: Any) -> str:
        """Calculates a deterministic SHA-256 hash of the JSON-serializable request payload."""
        normalized_str = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(normalized_str.encode("utf-8")).hexdigest()

    @staticmethod
    def acquire_key(
        db: Session,
        idempotency_key: str,
        payload: Any,
    ) -> IdempotencyRecord | None:
        """
        Attempts to acquire an idempotency key.
        Returns the existing completed record if already processed (cache hit),
        raises IdempotencyConflictException if mismatched or concurrent,
        or creates a new PROCESSING record and returns None.
        """
        req_hash = IdempotencyService.calculate_request_hash(payload)

        stmt = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == idempotency_key).with_for_update()
        record = db.scalar(stmt)

        if record:
            if record.request_hash != req_hash:
                raise IdempotencyConflictException(
                    "Idempotency key has already been used with a different request payload."
                )
            if record.status == IdempotencyStatus.PROCESSING.value:
                raise IdempotencyConflictException(
                    "A request with this idempotency key is currently being processed. Please retry shortly."
                )
            if record.status == IdempotencyStatus.COMPLETED.value:
                logger.info("Idempotent request cache hit for key: %s", idempotency_key)
                return record
            # If previous attempt failed, allow retry by updating status back to PROCESSING
            record.status = IdempotencyStatus.PROCESSING.value
            db.flush()
            return None

        # Insert new record in PROCESSING state
        new_record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            request_hash=req_hash,
            status=IdempotencyStatus.PROCESSING.value,
        )
        db.add(new_record)
        db.flush()
        return None

    @staticmethod
    def complete_key(
        db: Session,
        idempotency_key: str,
        status_code: int,
        response_body: dict[str, Any],
    ) -> None:
        """Marks the idempotency record as COMPLETED with the final response."""
        stmt = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == idempotency_key).with_for_update()
        record = db.scalar(stmt)
        if record:
            record.status = IdempotencyStatus.COMPLETED.value
            record.response_code = status_code
            record.response_body = response_body
            db.flush()

    @staticmethod
    def fail_key(db: Session, idempotency_key: str) -> None:
        """Marks the idempotency record as FAILED or clears it to allow fresh retry."""
        stmt = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == idempotency_key).with_for_update()
        record = db.scalar(stmt)
        if record:
            record.status = IdempotencyStatus.FAILED.value
            db.flush()
