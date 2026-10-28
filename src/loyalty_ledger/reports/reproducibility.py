"""Two-run reproducibility verification tool comparing row counts and SHA-256 checksums."""
import os
import json
import tempfile
import shutil
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loyalty_ledger.config import BASE_DIR, REPORTS_DIR
from loyalty_ledger.db import Base, _sqlite_on_connect
from loyalty_ledger.generator.data_generator import SyntheticDataGenerator
from loyalty_ledger.anomaly_detection.anomaly_injector import AnomalyInjector
from loyalty_ledger.reports.exporter import DataExporter, compute_sha256

class ReproducibilityVerifier:
    def __init__(self, seed: int = 20261022, scale: str = "starter"):
        self.seed = seed
        self.scale = scale

    def verify(self) -> Dict[str, Any]:
        """
        Executes two independent generation runs with the identical seed and scale into temporary databases,
        compares row counts, record IDs, and canonical table SHA-256 checksums.
        """
        print(f"Executing Run 1 (seed={self.seed}, scale={self.scale})...")
        run1_data = self._execute_isolated_run("run1")

        print(f"Executing Run 2 (seed={self.seed}, scale={self.scale})...")
        run2_data = self._execute_isolated_run("run2")

        # Compare row counts
        counts_match = (run1_data["row_counts"] == run2_data["row_counts"])

        # Compare checksums
        checksum_diffs = {}
        all_files = sorted(list(set(list(run1_data["checksums"].keys()) + list(run2_data["checksums"].keys()))))
        for f in all_files:
            c1 = run1_data["checksums"].get(f)
            c2 = run2_data["checksums"].get(f)
            if c1 != c2:
                checksum_diffs[f] = {"run1": c1, "run2": c2}

        checksums_match = (len(checksum_diffs) == 0)
        reproducible = counts_match and checksums_match

        report = {
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "seed": self.seed,
            "scale": self.scale,
            "reproducible": reproducible,
            "row_counts_identical": counts_match,
            "checksums_identical": checksums_match,
            "run1_id": run1_data["run_id"],
            "run1_timestamp": run1_data["start_time"],
            "run2_id": run2_data["run_id"],
            "run2_timestamp": run2_data["start_time"],
            "run1_row_counts": run1_data["row_counts"],
            "run2_row_counts": run2_data["row_counts"],
            "checksum_differences": checksum_diffs,
            "canonical_checksums": run1_data["checksums"]
        }

        # Save scale-specific report and general report
        scale_rep_path = REPORTS_DIR / f"reproducibility_report_{self.scale}.json"
        with open(scale_rep_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        root_scale_rep_path = BASE_DIR / f"reproducibility_report_{self.scale}.json"
        with open(root_scale_rep_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        rep_path = REPORTS_DIR / "reproducibility_report.json"
        with open(rep_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        root_rep_path = BASE_DIR / "reproducibility_report.json"
        with open(root_rep_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report

    def _execute_isolated_run(self, run_tag: str) -> Dict[str, Any]:
        temp_dir = tempfile.mkdtemp(prefix=f"loyalty_{run_tag}_")
        db_path = os.path.join(temp_dir, f"{run_tag}.db")
        db_url = f"sqlite:///{db_path}"
        start_time = datetime.now(timezone.utc).isoformat()
        run_id = f"RUN-{self.scale.upper()}-{run_tag.upper()}-{int(datetime.now(timezone.utc).timestamp())}"

        eng = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=eng)
        sess_factory = sessionmaker(bind=eng)
        sess = sess_factory()

        os.environ["LOYALTY_DISABLE_FK"] = "1"
        try:
            gen = SyntheticDataGenerator(seed=self.seed)
            gen_res = gen.generate_dataset(session=sess, scale=self.scale)

            inj = AnomalyInjector(session=sess, seed=self.seed)
            next_tx = gen_res["transactions_count"] + 1
            inj.inject_anomalies(start_tx_idx=next_tx)

            import hashlib
            from loyalty_ledger.domain.models import (
                Customer, LoyaltyAccount, Tier, Rule, Order, OrderLine,
                PointsTransaction, Reward, Redemption, ExpiryBatch, PointLot,
                TransactionLotAllocation, AccountTierHistory, OrderReturn
            )
            ALL_MODELS = [
                ("customers", Customer, "customer_id"),
                ("loyalty_accounts", LoyaltyAccount, "account_id"),
                ("tiers", Tier, "tier_id"),
                ("rules", Rule, "rule_id"),
                ("orders", Order, "order_id"),
                ("order_lines", OrderLine, "order_line_id"),
                ("points_transactions", PointsTransaction, "transaction_id"),
                ("rewards", Reward, "reward_id"),
                ("redemptions", Redemption, "redemption_id"),
                ("expiry_batches", ExpiryBatch, "expiry_batch_id"),
                ("point_lots", PointLot, "lot_id"),
                ("transaction_lot_allocations", TransactionLotAllocation, "allocation_id"),
                ("account_tier_history", AccountTierHistory, "history_id"),
                ("order_returns", OrderReturn, "return_id"),
            ]

            row_counts = {}
            checksums = {}

            for entity_name, model_cls, pk_field in ALL_MODELS:
                col_attr = getattr(model_cls, pk_field)
                cols = [c.name for c in model_cls.__table__.columns]
                rows = sess.connection().execute(model_cls.__table__.select().order_by(col_attr)).fetchall()
                row_counts[entity_name] = len(rows)
                hasher = hashlib.sha256()
                for r in rows:
                    hasher.update("|".join(str(r._mapping[c]) for c in cols).encode("utf-8"))
                checksums[f"{entity_name}_canonical_sha256"] = hasher.hexdigest()

            end_time = datetime.now(timezone.utc).isoformat()
            return {
                "run_id": run_id,
                "start_time": start_time,
                "end_time": end_time,
                "row_counts": row_counts,
                "checksums": checksums
            }
        finally:
            os.environ.pop("LOYALTY_DISABLE_FK", None)
            sess.close()
            eng.dispose()
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
