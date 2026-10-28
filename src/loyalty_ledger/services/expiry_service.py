"""Idempotent batch point expiry service."""
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from loyalty_ledger.domain.models import (
    ExpiryBatch, PointLot, PointsTransaction, LoyaltyAccount
)
from loyalty_ledger.ledger.ledger import LedgerService
from loyalty_ledger.db import begin_write_transaction

class ExpiryService:
    def __init__(self, session: Session):
        self.session = session
        self.ledger = LedgerService(session)

    def run_expiry_batch(
        self,
        cutoff_at: datetime,
        idempotency_key: str,
        expiry_batch_id: Optional[str] = None
    ) -> ExpiryBatch:
        """
        Executes an idempotent batch expiry of points reaching cutoff_at.
        If batch idempotency_key already ran, returns the existing batch without duplicate deductions.
        """
        begin_write_transaction(self.session)
        existing = self.session.query(ExpiryBatch).filter_by(
            idempotency_key=idempotency_key
        ).first()
        if existing and existing.status == "COMPLETED":
            return existing

        now = datetime.now(timezone.utc)
        batch_pk = expiry_batch_id or f"EXP-{cutoff_at.year}-{idempotency_key[-6:]}"

        batch = existing or ExpiryBatch(
            expiry_batch_id=batch_pk,
            run_at=now,
            cutoff_at=cutoff_at,
            status="STARTED",
            lots_scanned=0,
            points_expired=0,
            idempotency_key=idempotency_key
        )
        if not existing:
            self.session.add(batch)
            self.session.flush()

        # Find all open lots where expires_at <= cutoff_at and remaining_points > 0
        lots_to_expire = self.session.query(PointLot).filter(
            PointLot.status == "OPEN",
            PointLot.expires_at <= cutoff_at,
            PointLot.remaining_points > 0
        ).order_by(PointLot.expires_at.asc(), PointLot.lot_id.asc()).all()

        total_lots = len(lots_to_expire)
        total_points_expired = 0

        for lot in lots_to_expire:
            pts = lot.remaining_points
            if pts <= 0:
                continue

            # Record EXPIRY transaction for the account
            tx_idemp = f"IDEMP-EXP-{batch_pk}-{lot.lot_id}"
            tx = self.ledger.record_transaction(
                account_id=lot.account_id,
                transaction_type="EXPIRY",
                points_delta=-pts,
                source_type="EXPIRY_BATCH",
                source_id=batch.expiry_batch_id,
                idempotency_key=tx_idemp,
                reason_code="LOT_EXPIRY",
                correlation_id=f"CORR-EXP-{batch.expiry_batch_id}",
                event_at=cutoff_at,
                effective_at=cutoff_at,
                rule_id="RULE-EXPIRY-V1"
            )

            # Allocate full remaining points as EXPIRY
            self.ledger.allocate_from_lot(
                transaction_id=tx.transaction_id,
                lot=lot,
                points_to_allocate=pts,
                allocation_type="EXPIRY"
            )
            total_points_expired += pts

        batch.lots_scanned = total_lots
        batch.points_expired = total_points_expired
        batch.status = "COMPLETED"
        self.session.flush()

        return batch
