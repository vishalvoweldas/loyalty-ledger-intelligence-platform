"""Atomic and concurrency-safe redemption service."""
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from loyalty_ledger.domain.models import (
    Redemption, Reward, LoyaltyAccount, PointLot, PointsTransaction, RedemptionAttempt
)
from loyalty_ledger.ledger.ledger import LedgerService
from loyalty_ledger.db import begin_write_transaction

class RedemptionService:
    def __init__(self, session: Session):
        self.session = session
        self.ledger = LedgerService(session)

    def process_redemption(
        self,
        account_id: str,
        reward_id: str,
        requested_points: int,
        idempotency_key: str,
        redemption_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        requested_at: Optional[datetime] = None
    ) -> Redemption:
        """
        Executes an atomic points redemption against open point lots (FIFO earliest-expiry-first).
        Rejects if available points < requested_points.
        Idempotent: returns existing redemption if idempotency_key is repeated.
        """
        begin_write_transaction(self.session)
        existing = self.session.query(Redemption).filter_by(
            idempotency_key=idempotency_key
        ).first()
        if existing:
            return existing

        now = requested_at or datetime.now(timezone.utc)
        rdm_pk = redemption_id or f"RDM-{now.year}-{idempotency_key[-6:]}"

        account = self.session.query(LoyaltyAccount).filter_by(
            account_id=account_id
        ).with_for_update().first()
        if not account:
            raise ValueError(f"Account {account_id} not found")

        reward = self.session.query(Reward).filter_by(reward_id=reward_id).first()
        if not reward:
            raise ValueError(f"Reward {reward_id} not found")

        # Query eligible unexpired point lots sorted by:
        # 1. expires_at ASC (earliest expiry first)
        # 2. accrued_at ASC
        # 3. lot_id ASC (deterministic tie-breaker)
        lots = self.session.query(PointLot).filter(
            PointLot.account_id == account_id,
            PointLot.status == "OPEN",
            PointLot.expires_at > now,
            PointLot.remaining_points > 0
        ).order_by(
            PointLot.expires_at.asc(),
            PointLot.accrued_at.asc(),
            PointLot.lot_id.asc()
        ).with_for_update().all()

        total_available = sum(lot.remaining_points for lot in lots)

        if total_available < requested_points:
            # Insufficient points: record rejected redemption attempt
            rdm = Redemption(
                redemption_id=rdm_pk,
                account_id=account_id,
                reward_id=reward_id,
                requested_points=requested_points,
                approved_points=0,
                status="REJECTED",
                requested_at=now,
                processed_at=now,
                rejection_reason="INSUFFICIENT_AVAILABLE_POINTS",
                idempotency_key=idempotency_key
            )
            self.session.add(rdm)
            attempt = RedemptionAttempt(
                attempt_id=f"ATT-{rdm_pk}",
                account_id=account_id,
                reward_id=reward_id,
                requested_points=requested_points,
                status="REJECTED",
                rejection_reason="INSUFFICIENT_AVAILABLE_POINTS",
                attempted_at=now,
                idempotency_key=idempotency_key
            )
            self.session.add(attempt)
            self.session.flush()
            return rdm

        # Approved: allocate points from lots
        rdm = Redemption(
            redemption_id=rdm_pk,
            account_id=account_id,
            reward_id=reward_id,
            requested_points=requested_points,
            approved_points=requested_points,
            status="APPROVED",
            requested_at=now,
            processed_at=now,
            rejection_reason=None,
            idempotency_key=idempotency_key
        )
        self.session.add(rdm)
        attempt = RedemptionAttempt(
            attempt_id=f"ATT-{rdm_pk}",
            account_id=account_id,
            reward_id=reward_id,
            requested_points=requested_points,
            status="SUCCESS",
            rejection_reason=None,
            attempted_at=now,
            idempotency_key=idempotency_key
        )
        self.session.add(attempt)
        self.session.flush()

        # Record negative points movement in ledger
        tx = self.ledger.record_transaction(
            account_id=account_id,
            transaction_type="REDEMPTION",
            points_delta=-requested_points,
            source_type="REDEMPTION",
            source_id=rdm.redemption_id,
            idempotency_key=f"IDEMP-TX-{idempotency_key}",
            reason_code="REWARD_REDEMPTION",
            correlation_id=f"CORR-RDM-{rdm.redemption_id}",
            event_at=now,
            effective_at=now,
            rule_id="RULE-REDEMPTION-V1",
            transaction_id=transaction_id
        )

        # Allocate points across lots
        remaining_to_deduct = requested_points
        for lot in lots:
            if remaining_to_deduct <= 0:
                break
            points_from_lot = min(lot.remaining_points, remaining_to_deduct)
            self.ledger.allocate_from_lot(
                transaction_id=tx.transaction_id,
                lot=lot,
                points_to_allocate=points_from_lot,
                allocation_type="REDEMPTION"
            )
            remaining_to_deduct -= points_from_lot

        return rdm
