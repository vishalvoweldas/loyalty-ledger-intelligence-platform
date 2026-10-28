"""Append-only points ledger, point-lot management, and allocation tracking."""
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple, Any
from loyalty_ledger.domain.models import (
    PointsTransaction, PointLot, TransactionLotAllocation, LoyaltyAccount
)
from loyalty_ledger.db import begin_write_transaction

class LedgerService:
    def __init__(self, session: Session):
        self.session = session

    def record_transaction(
        self,
        account_id: str,
        transaction_type: str,
        points_delta: int,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        reason_code: str,
        correlation_id: str,
        event_at: datetime,
        effective_at: Optional[datetime] = None,
        original_transaction_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        transaction_id: Optional[str] = None
    ) -> PointsTransaction:
        """
        Appends an immutable transaction to the ledger.
        If idempotency_key already exists, returns the existing transaction.
        """
        begin_write_transaction(self.session)
        existing = self.session.query(PointsTransaction).filter_by(
            idempotency_key=idempotency_key
        ).first()
        if existing:
            return existing

        now_utc = datetime.now(timezone.utc)
        effective = effective_at or event_at

        # If transaction_id not provided, assign deterministic sequenced ID
        if not transaction_id:
            tx_count = self.session.query(PointsTransaction).count() + 1
            tx_pk = f"PTS-{event_at.year}-{tx_count:08d}"
            while self.session.query(PointsTransaction).filter_by(transaction_id=tx_pk).first() is not None:
                tx_count += 1
                tx_pk = f"PTS-{event_at.year}-{tx_count:08d}"
        else:
            tx_pk = transaction_id

        tx = PointsTransaction(
            transaction_id=tx_pk,
            account_id=account_id,
            transaction_type=transaction_type,
            points_delta=points_delta,
            event_at=event_at,
            effective_at=effective,
            source_type=source_type,
            source_id=source_id,
            original_transaction_id=original_transaction_id,
            rule_id=rule_id,
            status="POSTED",
            idempotency_key=idempotency_key,
            reason_code=reason_code,
            correlation_id=correlation_id,
            created_at=now_utc
        )
        self.session.add(tx)
        self.session.flush()

        # Update cached balance on loyalty account
        account = self.session.query(LoyaltyAccount).filter_by(account_id=account_id).first()
        if account:
            account.cached_balance_points += points_delta
            self.session.flush()

        return tx

    def create_point_lot(
        self,
        account_id: str,
        source_transaction_id: str,
        points: int,
        accrued_at: datetime,
        expires_at: datetime,
        lot_id: Optional[str] = None,
        rule_id: Optional[str] = None
    ) -> PointLot:
        """Creates an identifiable point lot corresponding to an accrual."""
        begin_write_transaction(self.session)
        lot_pk = lot_id or f"LOT-{source_transaction_id}"
        lot = PointLot(
            lot_id=lot_pk,
            account_id=account_id,
            source_transaction_id=source_transaction_id,
            original_points=points,
            remaining_points=points,
            accrued_at=accrued_at,
            expires_at=expires_at,
            status="OPEN",
            rule_id=rule_id
        )
        self.session.add(lot)
        self.session.flush()
        return lot

    def allocate_from_lot(
        self,
        transaction_id: str,
        lot: PointLot,
        points_to_allocate: int,
        allocation_type: str,
        allocation_id: Optional[str] = None
    ) -> TransactionLotAllocation:
        """Deducts points from a lot and writes a TransactionLotAllocation record."""
        begin_write_transaction(self.session)
        points = min(points_to_allocate, lot.remaining_points)
        alloc_count = self.session.query(TransactionLotAllocation).count() + 1
        alloc_pk = allocation_id or f"ALLOC-{transaction_id}-{lot.lot_id}-{alloc_count:04d}"
        while self.session.query(TransactionLotAllocation).filter_by(allocation_id=alloc_pk).first() is not None:
            alloc_count += 1
            alloc_pk = f"ALLOC-{transaction_id}-{lot.lot_id}-{alloc_count:04d}"

        alloc = TransactionLotAllocation(
            allocation_id=alloc_pk,
            transaction_id=transaction_id,
            lot_id=lot.lot_id,
            allocated_points=points,
            allocation_type=allocation_type,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(alloc)

        lot.remaining_points -= points
        if lot.remaining_points <= 0:
            lot.remaining_points = 0
            if allocation_type == "EXPIRY":
                lot.status = "EXPIRED"
            else:
                lot.status = "EXHAUSTED"

        self.session.flush()
        return alloc

    def get_ledger_balance(self, account_id: str) -> int:
        """Calculates signed ledger balance sum(points_delta)."""
        res = self.session.query(
            func.coalesce(func.sum(PointsTransaction.points_delta), 0)
        ).filter(PointsTransaction.account_id == account_id).scalar()
        return int(res)

    def get_available_balance(self, account_id: str, current_time: Optional[datetime] = None) -> int:
        """
        Calculates available points from unexpired, open point lots.
        """
        now = current_time or datetime.now(timezone.utc)
        lots = self.session.query(PointLot).filter(
            PointLot.account_id == account_id,
            PointLot.status == "OPEN",
            PointLot.expires_at > now
        ).all()
        return sum(lot.remaining_points for lot in lots)

    def reconcile_account(self, account_id: str) -> Dict[str, Any]:
        """Compares cached_balance_points against the signed ledger sum."""
        account = self.session.query(LoyaltyAccount).filter_by(account_id=account_id).first()
        if not account:
            return {"error": "Account not found"}

        ledger_sum = self.get_ledger_balance(account_id)
        is_reconciled = (account.cached_balance_points == ledger_sum)
        diff = account.cached_balance_points - ledger_sum

        tx_count = self.session.query(PointsTransaction).filter_by(
            account_id=account_id
        ).count()

        return {
            "account_id": account_id,
            "cached_balance": account.cached_balance_points,
            "ledger_derived_balance": ledger_sum,
            "is_reconciled": is_reconciled,
            "difference": diff,
            "transaction_count": tx_count
        }
