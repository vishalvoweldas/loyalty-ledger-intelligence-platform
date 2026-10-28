"""Tier progression service evaluating rolling 12-month net qualifying spend."""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from loyalty_ledger.domain.models import (
    LoyaltyAccount, Order, OrderReturn, AccountTierHistory, Tier
)
from loyalty_ledger.domain.rules import RuleEngine, DEFAULT_TIERS_CONFIG
from loyalty_ledger.db import begin_write_transaction

class TierService:
    def __init__(self, session: Session):
        self.session = session

    def calculate_qualifying_spend(
        self,
        customer_id: str,
        as_of_date: datetime,
        rolling_days: int = 365
    ) -> int:
        """
        Calculates net qualifying merchandise spend in minor units over the rolling window:
        Sum(eligible net merchandise spend of completed orders) - Sum(returned eligible spend).
        Excludes taxes, shipping fees, and cancelled orders.
        """
        window_start = as_of_date - timedelta(days=rolling_days)

        orders = self.session.query(Order).filter(
            Order.customer_id == customer_id,
            Order.status.in_(["COMPLETED", "PARTIALLY_RETURNED", "RETURNED"]),
            Order.order_date >= window_start,
            Order.order_date <= as_of_date
        ).all()

        total_qualifying = 0
        for ord in orders:
            # Eligible net spend across order lines
            line_spend = sum(line.eligible_spend_minor for line in ord.lines)
            if line_spend <= 0:
                line_spend = max(0, ord.net_merchandise_minor)
            total_qualifying += line_spend

        # Subtract returns processed in this window
        order_ids = [ord.order_id for ord in orders]
        if order_ids:
            returns = self.session.query(OrderReturn).filter(
                OrderReturn.order_id.in_(order_ids),
                OrderReturn.return_date >= window_start,
                OrderReturn.return_date <= as_of_date
            ).all()
            total_returned = sum(ret.returned_eligible_spend_minor for ret in returns)
            total_qualifying = max(0, total_qualifying - total_returned)

        return total_qualifying

    def evaluate_and_update_tier(
        self,
        account_id: str,
        as_of_date: Optional[datetime] = None,
        reason: str = "SCHEDULED_EVALUATION"
    ) -> LoyaltyAccount:
        """
        Recomputes qualifying spend and updates account tier if a transition occurred.
        Appends an AccountTierHistory record.
        """
        begin_write_transaction(self.session)
        account = self.session.query(LoyaltyAccount).filter_by(account_id=account_id).first()
        if not account:
            raise ValueError(f"Account {account_id} not found")

        eval_date = as_of_date or datetime.now(timezone.utc)
        qualifying_spend = self.calculate_qualifying_spend(account.customer_id, eval_date)

        # Query configured tiers
        tiers = self.session.query(Tier).filter_by(status="ACTIVE").all()
        tiers_list = [
            {
                "tier_id": t.tier_id,
                "tier_name": t.tier_name,
                "min_qualifying_spend_minor": t.min_qualifying_spend_minor,
                "spend_per_point_minor": t.spend_per_point_minor,
                "earning_rate_points": t.earning_rate_points
            }
            for t in tiers
        ] or DEFAULT_TIERS_CONFIG

        new_tier_id, new_tier_name, _, _ = RuleEngine.evaluate_tier(qualifying_spend, tiers_list)

        if account.current_tier_id != new_tier_id:
            # Close previous tier history
            prev_history = self.session.query(AccountTierHistory).filter_by(
                account_id=account_id,
                effective_to=None
            ).first()
            if prev_history:
                prev_history.effective_to = eval_date

            # Create new history entry
            history = AccountTierHistory(
                history_id=f"TH-{account_id}-{eval_date.strftime('%Y%m%d%H%M%S')}",
                account_id=account_id,
                tier_id=new_tier_id,
                qualifying_spend_minor=qualifying_spend,
                effective_from=eval_date,
                effective_to=None,
                reason=reason
            )
            self.session.add(history)
            account.current_tier_id = new_tier_id
            self.session.flush()

        return account
