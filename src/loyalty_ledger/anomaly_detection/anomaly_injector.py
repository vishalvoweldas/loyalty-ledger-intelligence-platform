"""Controlled anomaly injection layer for introducing and labelling the 5 mandatory anomalies."""
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from loyalty_ledger.domain.models import (
    Customer, LoyaltyAccount, Order, OrderReturn, PointsTransaction,
    PointLot, TransactionLotAllocation, Redemption, GroundTruthRecord
)
from loyalty_ledger.db import begin_write_transaction

class AnomalyInjector:
    def __init__(self, session: Session, seed: int = 20261022):
        self.session = session
        self.seed = seed

    def inject_anomalies(self, start_tx_idx: int) -> Tuple[List[GroundTruthRecord], int]:
        """
        Injects the 5 mandatory anomaly types into designated records and labels them in GroundTruthRecord.
        Returns: (ground_truth_records, next_tx_idx)
        """
        begin_write_transaction(self.session)
        gt_records = []
        current_tx_counter = start_tx_idx
        now = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Clear existing ground truth records to ensure idempotency
        self.session.query(GroundTruthRecord).delete()
        self.session.flush()

        # -------------------------------------------------------------
        # AN-001: Stored account balance differs from ledger sum (2 cases)
        # -------------------------------------------------------------
        acc_1 = self.session.query(LoyaltyAccount).filter_by(account_id="LOY-CUS-000010").first()
        if acc_1:
            acc_1.cached_balance_points += 250  # Tamper cached balance
            gt1 = GroundTruthRecord(
                anomaly_id="AN-001-0001",
                issue_type="AN-001",
                affected_entity="LoyaltyAccount",
                affected_record_id=acc_1.account_id,
                customer_id=acc_1.customer_id,
                account_id=acc_1.account_id,
                expected_outcome="DETECT_BALANCE_MISMATCH",
                severity="HIGH",
                explanation=f"Stored balance tampered (+250 pts). Stored: {acc_1.cached_balance_points}, does not equal ledger sum.",
                expected_detector_result="BALANCE_MISMATCH",
                generation_seed=self.seed,
                scenario_id="SCENARIO_AN001_TAMPERED_BALANCE_OVER"
            )
            gt_records.append(gt1)

        acc_2 = self.session.query(LoyaltyAccount).filter_by(account_id="LOY-CUS-000020").first()
        if acc_2:
            acc_2.cached_balance_points -= 150  # Tamper cached balance negative
            gt2 = GroundTruthRecord(
                anomaly_id="AN-001-0002",
                issue_type="AN-001",
                affected_entity="LoyaltyAccount",
                affected_record_id=acc_2.account_id,
                customer_id=acc_2.customer_id,
                account_id=acc_2.account_id,
                expected_outcome="DETECT_BALANCE_MISMATCH",
                severity="HIGH",
                explanation=f"Stored balance tampered (-150 pts). Stored: {acc_2.cached_balance_points}, does not equal ledger sum.",
                expected_detector_result="BALANCE_MISMATCH",
                generation_seed=self.seed,
                scenario_id="SCENARIO_AN001_TAMPERED_BALANCE_UNDER"
            )
            gt_records.append(gt2)

        # -------------------------------------------------------------
        # AN-002: Redemption exceeds available points (2 cases, consumes 2 txs)
        # -------------------------------------------------------------
        for case_idx, target_acc_id in enumerate(["LOY-CUS-000030", "LOY-CUS-000031"], 1):
            acc = self.session.query(LoyaltyAccount).filter_by(account_id=target_acc_id).first()
            if acc:
                rdm_id = f"RDM-AN002-{case_idx:04d}"
                tx_id = f"PTS-2026-{current_tx_counter:08d}"
                current_tx_counter += 1
                excessive_pts = 99999  # Far exceeds balance

                rdm = Redemption(
                    redemption_id=rdm_id,
                    account_id=acc.account_id,
                    reward_id="REW-VOUCHER-1000",
                    requested_points=excessive_pts,
                    approved_points=excessive_pts,
                    status="APPROVED",  # Injected defect: accepted despite insufficient points
                    requested_at=now,
                    processed_at=now,
                    rejection_reason=None,
                    idempotency_key=f"IDEMP-{rdm_id}"
                )
                self.session.add(rdm)

                # Matching transaction that makes points overdrawn
                tx = PointsTransaction(
                    transaction_id=tx_id,
                    account_id=acc.account_id,
                    transaction_type="REDEMPTION",
                    points_delta=-excessive_pts,
                    event_at=now,
                    effective_at=now,
                    source_type="REDEMPTION",
                    source_id=rdm_id,
                    original_transaction_id=None,
                    rule_id="RULE-REDEMPTION-V1",
                    status="POSTED",
                    idempotency_key=f"IDEMP-TX-{rdm_id}",
                    reason_code="REWARD_REDEMPTION",
                    correlation_id=f"CORR-{rdm_id}",
                    created_at=now
                )
                self.session.add(tx)
                acc.cached_balance_points += tx.points_delta

                gt = GroundTruthRecord(
                    anomaly_id=f"AN-002-{case_idx:04d}",
                    issue_type="AN-002",
                    affected_entity="Redemption",
                    affected_record_id=rdm_id,
                    customer_id=acc.customer_id,
                    account_id=acc.account_id,
                    expected_outcome="DETECT_EXCESSIVE_REDEMPTION",
                    severity="CRITICAL",
                    explanation=f"Approved redemption {rdm_id} for {excessive_pts} pts exceeded available balance.",
                    expected_detector_result="EXCESSIVE_REDEMPTION",
                    generation_seed=self.seed,
                    scenario_id="SCENARIO_AN002_ACCEPTED_OVERSPEND"
                )
                gt_records.append(gt)

        # -------------------------------------------------------------
        # AN-003: Returned order keeps all earned points (missing reversal, 2 cases)
        # Select 2 unreturned orders from Bronze accounts to isolate AN-003 without collateral tier mismatches
        candidate_orders = (
            self.session.query(Order)
            .join(LoyaltyAccount, LoyaltyAccount.customer_id == Order.customer_id)
            .filter(LoyaltyAccount.current_tier_id == "TIER-BRONZE")
            .filter(~Order.order_id.in_(self.session.query(OrderReturn.order_id)))
            .limit(2)
            .all()
        )
        for case_idx, ord_obj in enumerate(candidate_orders, 1):
            target_ord_id = ord_obj.order_id
            if ord_obj:
                ret_id = f"RET-AN003-{case_idx:04d}"
                ord_obj.status = "RETURNED"

                # Return is logged but reversal_transaction_id is NULL and no reversal transaction posted
                ret = OrderReturn(
                    return_id=ret_id,
                    order_id=target_ord_id,
                    return_date=now,
                    reason="CUSTOMER_RETURN_FULL",
                    returned_eligible_spend_minor=ord_obj.net_merchandise_minor,
                    reversal_transaction_id=None
                )
                self.session.add(ret)

                gt = GroundTruthRecord(
                    anomaly_id=f"AN-003-{case_idx:04d}",
                    issue_type="AN-003",
                    affected_entity="OrderReturn",
                    affected_record_id=ret_id,
                    customer_id=ord_obj.customer_id,
                    account_id=f"LOY-{ord_obj.customer_id}",
                    expected_outcome="DETECT_UNREVERSED_RETURN",
                    severity="HIGH",
                    explanation=f"Returned order {target_ord_id} was returned but no reversal transaction was posted.",
                    expected_detector_result="UNREVERSED_RETURN",
                    generation_seed=self.seed,
                    scenario_id="SCENARIO_AN003_UNREVERSED_POINTS"
                )
                gt_records.append(gt)

        # -------------------------------------------------------------
        # AN-004: Points expire twice (duplicate expiry movements, 8 cases)
        # Consumes exactly 8 transactions
        # -------------------------------------------------------------
        expired_lot_ids = [
            row[0] for row in self.session.query(TransactionLotAllocation.lot_id)
            .filter_by(allocation_type="EXPIRY")
            .distinct()
            .limit(8)
            .all()
        ]
        if len(expired_lot_ids) >= 8:
            lots = self.session.query(PointLot).filter(PointLot.lot_id.in_(expired_lot_ids)).all()
        else:
            lots = self.session.query(PointLot).limit(8).all()

        for case_idx, lot in enumerate(lots, 1):
            tx_id = f"PTS-2026-{current_tx_counter:08d}"
            current_tx_counter += 1
            duplicate_exp_pts = 10

            # Ensure lot has a baseline EXPIRY allocation if it didn't have one
            existing_exp_alloc = self.session.query(TransactionLotAllocation).filter_by(
                lot_id=lot.lot_id,
                allocation_type="EXPIRY"
            ).first()
            if not existing_exp_alloc:
                base_alloc = TransactionLotAllocation(
                    allocation_id=f"ALLOC-BASE-EXP-{case_idx:04d}",
                    transaction_id=lot.source_transaction_id,
                    lot_id=lot.lot_id,
                    allocated_points=5,
                    allocation_type="EXPIRY",
                    created_at=now
                )
                self.session.add(base_alloc)

            # Injected second duplicate expiry movement for the same lot
            tx = PointsTransaction(
                transaction_id=tx_id,
                account_id=lot.account_id,
                transaction_type="EXPIRY",
                points_delta=-duplicate_exp_pts,
                event_at=now,
                effective_at=now,
                source_type="EXPIRY_BATCH",
                source_id="EXP-2026-ANOMALY-01",
                original_transaction_id=None,
                rule_id="RULE-EXPIRY-V1",
                status="POSTED",
                idempotency_key=f"IDEMP-DUP-EXP-{case_idx}-{lot.lot_id}",
                reason_code="LOT_EXPIRY",
                correlation_id=f"CORR-DUP-EXP-{case_idx}",
                created_at=now
            )
            self.session.add(tx)
            lot_acc = self.session.query(LoyaltyAccount).filter_by(account_id=lot.account_id).first()
            if lot_acc:
                lot_acc.cached_balance_points += tx.points_delta

            alloc = TransactionLotAllocation(
                allocation_id=f"ALLOC-AN004-{case_idx:04d}",
                transaction_id=tx_id,
                lot_id=lot.lot_id,
                allocated_points=duplicate_exp_pts,
                allocation_type="EXPIRY",
                created_at=now
            )
            self.session.add(alloc)

            gt = GroundTruthRecord(
                anomaly_id=f"AN-004-{case_idx:04d}",
                issue_type="AN-004",
                affected_entity="PointLot",
                affected_record_id=lot.lot_id,
                customer_id=None,
                account_id=lot.account_id,
                expected_outcome="DETECT_DUPLICATE_EXPIRY",
                severity="HIGH",
                explanation=f"Point lot {lot.lot_id} received duplicate expiry allocation of {duplicate_exp_pts} pts.",
                expected_detector_result="DUPLICATE_EXPIRY",
                generation_seed=self.seed,
                scenario_id="SCENARIO_AN004_DUPLICATE_LOT_EXPIRY"
            )
            gt_records.append(gt)

        # -------------------------------------------------------------
        # AN-005: Tier assignment uses gross spend rather than qualifying net spend (2 cases)
        # -------------------------------------------------------------
        bronze_accounts = (
            self.session.query(LoyaltyAccount)
            .filter_by(current_tier_id="TIER-BRONZE")
            .limit(2)
            .all()
        )
        for case_idx, acc in enumerate(bronze_accounts, 1):
            # Force Gold tier when qualifying net spend is only Bronze level
            acc.current_tier_id = "TIER-GOLD"
            gt = GroundTruthRecord(
                anomaly_id=f"AN-005-{case_idx:04d}",
                issue_type="AN-005",
                affected_entity="LoyaltyAccount",
                affected_record_id=acc.account_id,
                customer_id=acc.customer_id,
                account_id=acc.account_id,
                expected_outcome="DETECT_GROSS_SPEND_TIER",
                severity="MEDIUM",
                explanation=f"Account {acc.account_id} assigned TIER-GOLD despite qualifying net spend being below ₹50,000 threshold.",
                expected_detector_result="GROSS_SPEND_TIER",
                generation_seed=self.seed,
                scenario_id="SCENARIO_AN005_GROSS_SPEND_TIER_OVERRIDE"
            )
            gt_records.append(gt)

        # Save all ground truth records
        self.session.bulk_save_objects(gt_records)
        self.session.flush()
        self.session.commit()

        return gt_records, current_tx_counter
