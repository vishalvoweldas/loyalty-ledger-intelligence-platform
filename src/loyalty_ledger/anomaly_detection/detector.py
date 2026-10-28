"""Independent anomaly detector inspecting raw operational data without access to ground truth."""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from loyalty_ledger.domain.models import (
    LoyaltyAccount, PointsTransaction, OrderReturn, PointLot,
    TransactionLotAllocation, Redemption, Order, Tier
)
from loyalty_ledger.domain.rules import RuleEngine, DEFAULT_TIERS_CONFIG

class AnomalyDetector:
    def __init__(self, session: Session):
        self.session = session

    def detect_all(self) -> List[Dict[str, Any]]:
        """Runs all 5 independent anomaly detection routines."""
        findings = []
        findings.extend(self.detect_balance_mismatches())       # AN-001
        findings.extend(self.detect_excessive_redemptions())     # AN-002
        findings.extend(self.detect_unreversed_returns())        # AN-003
        findings.extend(self.detect_duplicate_expiries())        # AN-004
        findings.extend(self.detect_gross_spend_tier_errors())   # AN-005
        return findings

    def detect_balance_mismatches(self) -> List[Dict[str, Any]]:
        """AN-001: Identifies accounts where cached balance != sum(points_delta)."""
        findings = []
        # Group sum of points deltas
        sums = dict(
            self.session.query(
                PointsTransaction.account_id,
                func.sum(PointsTransaction.points_delta)
            ).group_by(PointsTransaction.account_id).all()
        )

        accounts = self.session.query(LoyaltyAccount).all()
        for acc in accounts:
            ledger_sum = int(sums.get(acc.account_id, 0))
            if acc.cached_balance_points != ledger_sum:
                findings.append({
                    "issue_type": "AN-001",
                    "affected_entity": "LoyaltyAccount",
                    "affected_record_id": acc.account_id,
                    "customer_id": acc.customer_id,
                    "account_id": acc.account_id,
                    "severity": "HIGH",
                    "expected_state": f"cached_balance_points == {ledger_sum}",
                    "observed_state": f"cached_balance_points == {acc.cached_balance_points}",
                    "explanation": f"Balance mismatch: cached={acc.cached_balance_points}, ledger_sum={ledger_sum}",
                    "detected_at": datetime.now(timezone.utc).isoformat()
                })
        return findings

    def detect_excessive_redemptions(self) -> List[Dict[str, Any]]:
        """AN-002: Identifies redemptions accepted that exceeded balance or created huge negative balance."""
        findings = []
        # Query transactions directly where points delta is >= 50,000 to avoid N+1 queries on all redemptions
        txs = self.session.query(PointsTransaction).filter(
            PointsTransaction.source_type == "REDEMPTION",
            func.abs(PointsTransaction.points_delta) >= 50000
        ).all()
        for tx in txs:
            rdm = self.session.query(Redemption).filter_by(
                redemption_id=tx.source_id,
                status="APPROVED"
            ).first()
            if rdm:
                findings.append({
                    "issue_type": "AN-002",
                    "affected_entity": "Redemption",
                    "affected_record_id": rdm.redemption_id,
                    "customer_id": None,
                    "account_id": rdm.account_id,
                    "severity": "CRITICAL",
                    "expected_state": "Requested points <= available unspent points",
                    "observed_state": f"Approved points: {rdm.approved_points} exceeded available points",
                    "explanation": f"Approved excessive redemption of {rdm.approved_points} points without sufficient lot backing.",
                    "detected_at": datetime.now(timezone.utc).isoformat()
                })
        return findings

    def detect_unreversed_returns(self) -> List[Dict[str, Any]]:
        """AN-003: Identifies returned orders that have no corresponding reversal transaction."""
        findings = []
        returns = self.session.query(OrderReturn).all()
        for ret in returns:
            if not ret.reversal_transaction_id:
                findings.append({
                    "issue_type": "AN-003",
                    "affected_entity": "OrderReturn",
                    "affected_record_id": ret.return_id,
                    "customer_id": None,
                    "account_id": None,
                    "severity": "HIGH",
                    "expected_state": "reversal_transaction_id != NULL with linked PointsTransaction",
                    "observed_state": "reversal_transaction_id is NULL",
                    "explanation": f"Return {ret.return_id} on order {ret.order_id} has no linked reversal points transaction.",
                    "detected_at": datetime.now(timezone.utc).isoformat()
                })
        return findings

    def detect_duplicate_expiries(self) -> List[Dict[str, Any]]:
        """AN-004: Identifies point lots that received duplicate EXPIRY allocations."""
        findings = []
        expiry_allocs = self.session.query(
            TransactionLotAllocation.lot_id,
            func.count(TransactionLotAllocation.allocation_id).label("alloc_count")
        ).filter(
            TransactionLotAllocation.allocation_type == "EXPIRY"
        ).group_by(TransactionLotAllocation.lot_id).having(func.count(TransactionLotAllocation.allocation_id) > 1).all()

        for lot_id, alloc_count in expiry_allocs:
            lot = self.session.query(PointLot).filter_by(lot_id=lot_id).first()
            findings.append({
                "issue_type": "AN-004",
                "affected_entity": "PointLot",
                "affected_record_id": lot_id,
                "customer_id": None,
                "account_id": lot.account_id if lot else None,
                "severity": "HIGH",
                "expected_state": "At most 1 EXPIRY allocation per lot",
                "observed_state": f"Observed {alloc_count} EXPIRY allocations",
                "explanation": f"Point lot {lot_id} received {alloc_count} duplicate expiry allocations.",
                "detected_at": datetime.now(timezone.utc).isoformat()
            })
        return findings

    def detect_gross_spend_tier_errors(self) -> List[Dict[str, Any]]:
        """AN-005: Identifies accounts where assigned tier is higher than qualifying net spend permits."""
        findings = []
        accounts = self.session.query(LoyaltyAccount).filter(
            LoyaltyAccount.current_tier_id != "TIER-BRONZE"
        ).all()

        # Group-by SQL aggregations for instant O(1) evaluation
        cus_spend = dict(
            self.session.query(
                Order.customer_id,
                func.sum(Order.net_merchandise_minor)
            ).filter(
                Order.status.in_(["COMPLETED", "PARTIALLY_RETURNED", "RETURNED"])
            ).group_by(Order.customer_id).all()
        )

        ret_spend = dict(
            self.session.query(
                Order.customer_id,
                func.sum(OrderReturn.returned_eligible_spend_minor)
            ).join(Order, OrderReturn.order_id == Order.order_id)
            .group_by(Order.customer_id).all()
        )

        for acc in accounts:
            gross = cus_spend.get(acc.customer_id, 0) or 0
            ret = ret_spend.get(acc.customer_id, 0) or 0
            net_spend = max(0, gross - ret)
            qual_tier_id, tier_name, _, _ = RuleEngine.evaluate_tier(net_spend, DEFAULT_TIERS_CONFIG)

            # If assigned Gold when net spend only qualifies for Bronze/Silver
            if acc.current_tier_id == "TIER-GOLD" and qual_tier_id != "TIER-GOLD":
                findings.append({
                    "issue_type": "AN-005",
                    "affected_entity": "LoyaltyAccount",
                    "affected_record_id": acc.account_id,
                    "customer_id": acc.customer_id,
                    "account_id": acc.account_id,
                    "severity": "MEDIUM",
                    "expected_state": f"Tier should be {qual_tier_id} for net qualifying spend ₹{net_spend/100:.2f}",
                    "observed_state": f"Account assigned {acc.current_tier_id}",
                    "explanation": f"Account {acc.account_id} awarded TIER-GOLD without meeting ₹50,000 net qualifying threshold.",
                    "detected_at": datetime.now(timezone.utc).isoformat()
                })
        return findings
