"""Order return and points reversal service."""
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from loyalty_ledger.domain.models import (
    Order, OrderLine, OrderReturn, PointsTransaction, PointLot, LoyaltyAccount, AuditEvent
)
from loyalty_ledger.domain.rules import RuleEngine
from loyalty_ledger.ledger.ledger import LedgerService
from loyalty_ledger.db import begin_write_transaction

class ReturnsService:
    def __init__(self, session: Session):
        self.session = session
        self.ledger = LedgerService(session)

    def process_order_return(
        self,
        order_id: str,
        returned_lines: List[Dict[str, Any]],
        reason: str = "CUSTOMER_RETURN",
        idempotency_key: Optional[str] = None,
        return_id: Optional[str] = None,
        reversal_transaction_id: Optional[str] = None,
        return_date: Optional[datetime] = None
    ) -> OrderReturn:
        """
        Processes a full or partial return, validates quantities, calculates proportional reversals,
        and posts an immutable REVERSAL transaction referencing the original accrual.
        """
        begin_write_transaction(self.session)
        order = self.session.query(Order).filter_by(order_id=order_id).first()
        if not order:
            raise ValueError(f"Order {order_id} not found")

        account = self.session.query(LoyaltyAccount).filter_by(customer_id=order.customer_id).first()
        if not account:
            raise ValueError(f"No loyalty account found for customer {order.customer_id}")

        now = return_date or datetime.now(timezone.utc)

        # Idempotency check: if already processed with this key, return existing return
        if idempotency_key:
            existing_tx = self.session.query(PointsTransaction).filter_by(
                idempotency_key=idempotency_key
            ).first()
            if existing_tx:
                existing_ret = self.session.query(OrderReturn).filter_by(
                    reversal_transaction_id=existing_tx.transaction_id
                ).first()
                if existing_ret:
                    return existing_ret

        ret_count = self.session.query(OrderReturn).filter_by(order_id=order_id).count() + 1
        ret_pk = return_id or f"RET-{order_id}-{now.strftime('%Y%m%d%H%M%S')}-{ret_count:02d}"

        # Find original accrual transaction for this order
        original_tx = self.session.query(PointsTransaction).filter(
            PointsTransaction.source_type == "ORDER",
            PointsTransaction.source_id == order_id,
            PointsTransaction.transaction_type == "ACCRUAL"
        ).first()

        if not original_tx:
            raise ValueError(f"No original accrual transaction found for order {order_id}")

        # Find prior reversals to prevent over-reversing
        prior_reversals = self.session.query(PointsTransaction).filter(
            PointsTransaction.original_transaction_id == original_tx.transaction_id,
            PointsTransaction.transaction_type == "REVERSAL"
        ).all()
        already_reversed_points = sum(abs(tx.points_delta) for tx in prior_reversals)
        max_reversable_points = max(0, original_tx.points_delta - already_reversed_points)

        # Calculate returned eligible spend and update returned_quantity
        total_returned_eligible_spend = 0
        for item in returned_lines:
            line_id = item["order_line_id"]
            qty = item["quantity"]

            line = self.session.query(OrderLine).filter_by(order_line_id=line_id, order_id=order_id).first()
            if not line:
                raise ValueError(f"OrderLine {line_id} not found on order {order_id}")

            if line.returned_quantity + qty > line.quantity:
                raise ValueError(f"Returned quantity {line.returned_quantity + qty} exceeds ordered quantity {line.quantity}")

            line.returned_quantity += qty
            # Calculate proportion of line eligible spend
            unit_eligible = line.eligible_spend_minor / line.quantity
            total_returned_eligible_spend += int(unit_eligible * qty)

        # Calculate proportional reversal points
        total_order_eligible_spend = sum(line.eligible_spend_minor for line in order.lines)
        if total_order_eligible_spend <= 0:
            total_order_eligible_spend = max(1, order.net_merchandise_minor)

        reversal_points = RuleEngine.calculate_return_reversal_points(
            original_points=original_tx.points_delta,
            original_eligible_spend_minor=total_order_eligible_spend,
            returned_eligible_spend_minor=total_returned_eligible_spend
        )
        # Cap at remaining points awarded on original transaction
        points_to_reverse = min(reversal_points, max_reversable_points)

        # Update order status
        all_returned = all(line.returned_quantity == line.quantity for line in order.lines)
        order.status = "RETURNED" if all_returned else "PARTIALLY_RETURNED"

        # Record REVERSAL transaction in ledger (points_delta is negative)
        rev_tx = None
        if points_to_reverse > 0:
            rev_idemp = idempotency_key or f"IDEMP-REV-{ret_pk}"
            rev_tx = self.ledger.record_transaction(
                account_id=account.account_id,
                transaction_type="REVERSAL",
                points_delta=-points_to_reverse,
                source_type="RETURN",
                source_id=ret_pk,
                idempotency_key=rev_idemp,
                reason_code="RETURN_REVERSAL",
                correlation_id=f"CORR-{order_id}",
                event_at=now,
                effective_at=now,
                original_transaction_id=original_tx.transaction_id,
                rule_id="RULE-REVERSAL-V1",
                transaction_id=reversal_transaction_id
            )

            # Deplete from corresponding lot if open
            lot = self.session.query(PointLot).filter_by(
                source_transaction_id=original_tx.transaction_id
            ).first()
            if lot and lot.status == "OPEN" and lot.remaining_points > 0:
                self.ledger.allocate_from_lot(
                    transaction_id=rev_tx.transaction_id,
                    lot=lot,
                    points_to_allocate=points_to_reverse,
                    allocation_type="REVERSAL"
                )

            # Check if balance became negative (pre-spent points)
            current_balance = self.ledger.get_ledger_balance(account.account_id)
            if current_balance < 0:
                audit = AuditEvent(
                    audit_id=f"AUD-DEBT-{account.account_id}-{now.strftime('%Y%m%d%H%M%S')}",
                    entity_type="LOYALTY_ACCOUNT",
                    entity_id=account.account_id,
                    action="DEBT_FLAGGED",
                    actor="SYSTEM_RETURNS_SERVICE",
                    timestamp=now,
                    details=f"Account balance negative ({current_balance}) following return reversal on {order_id}"
                )
                self.session.add(audit)

        order_return = OrderReturn(
            return_id=ret_pk,
            order_id=order_id,
            return_date=now,
            reason=reason,
            returned_eligible_spend_minor=total_returned_eligible_spend,
            reversal_transaction_id=rev_tx.transaction_id if rev_tx else None
        )
        self.session.add(order_return)
        self.session.flush()

        return order_return
