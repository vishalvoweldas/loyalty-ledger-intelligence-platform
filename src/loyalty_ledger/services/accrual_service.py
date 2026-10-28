"""Points accrual service handling eligible order processing and lot generation."""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from loyalty_ledger.domain.models import Order, LoyaltyAccount, Tier, PointsTransaction, PointLot
from loyalty_ledger.domain.rules import RuleEngine
from loyalty_ledger.ledger.ledger import LedgerService
from loyalty_ledger.db import begin_write_transaction

class AccrualService:
    def __init__(self, session: Session):
        self.session = session
        self.ledger = LedgerService(session)

    def accrue_points_for_order(
        self,
        order_id: str,
        idempotency_key: Optional[str] = None,
        transaction_id: Optional[str] = None,
        lot_id: Optional[str] = None
    ) -> Optional[PointsTransaction]:
        """
        Calculates eligible spend and posts an ACCRUAL transaction and PointLot.
        Idempotent: if already processed, returns existing transaction.
        """
        begin_write_transaction(self.session)
        idemp = idempotency_key or f"IDEMP-ACCR-{order_id}"
        existing = self.session.query(PointsTransaction).filter_by(idempotency_key=idemp).first()
        if existing:
            return existing

        order = self.session.query(Order).filter_by(order_id=order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found")

        if order.status == "CANCELLED":
            # Cancelled orders do not accrue points
            return None

        # Find customer's loyalty account
        account = self.session.query(LoyaltyAccount).filter_by(customer_id=order.customer_id).first()
        if not account:
            raise ValueError(f"No loyalty account found for customer {order.customer_id}")

        # Fetch active tier
        tier = self.session.query(Tier).filter_by(tier_id=account.current_tier_id).first()
        spend_per_point = tier.spend_per_point_minor if tier else 10000

        # Calculate total eligible merchandise spend across lines
        eligible_spend_minor = sum(line.eligible_spend_minor for line in order.lines)
        if eligible_spend_minor <= 0:
            # Fallback to net merchandise spend if lines empty
            eligible_spend_minor = max(0, order.net_merchandise_minor)

        points_earned = RuleEngine.calculate_points_earned(eligible_spend_minor, spend_per_point)
        if points_earned <= 0:
            return None

        # Append transaction to ledger
        tx = self.ledger.record_transaction(
            account_id=account.account_id,
            transaction_type="ACCRUAL",
            points_delta=points_earned,
            source_type="ORDER",
            source_id=order.order_id,
            idempotency_key=idemp,
            reason_code="PURCHASE_ACCRUAL",
            correlation_id=f"CORR-{order.order_id}",
            event_at=order.order_date,
            effective_at=order.order_date,
            rule_id="RULE-ACCRUAL-V1",
            transaction_id=transaction_id
        )

        # Create corresponding point lot (valid for 365 days)
        expires_at = order.order_date + timedelta(days=365)
        self.ledger.create_point_lot(
            account_id=account.account_id,
            source_transaction_id=tx.transaction_id,
            points=points_earned,
            accrued_at=order.order_date,
            expires_at=expires_at,
            lot_id=lot_id,
            rule_id="RULE-ACCRUAL-V1"
        )

        return tx
