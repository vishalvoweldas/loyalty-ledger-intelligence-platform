"""Export engine generating CSV, JSON, SQL seeds, and manifest artifacts with SHA-256 checksums."""
import os
import json
import csv
import hashlib
import tempfile
import shutil
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from loyalty_ledger.config import EXPORTS_DIR, DATA_DIR, REPORTS_DIR, BASE_DIR
from loyalty_ledger.db import Base
from loyalty_ledger.generator.data_generator import SyntheticDataGenerator
from loyalty_ledger.anomaly_detection.anomaly_injector import AnomalyInjector
from loyalty_ledger.domain.models import (
    Customer, LoyaltyAccount, Tier, Rule, Order, OrderLine,
    PointsTransaction, Reward, Redemption, ExpiryBatch, PointLot,
    TransactionLotAllocation, AccountTierHistory, OrderReturn, AuditEvent,
    GroundTruthRecord
)

ENTITIES_TO_EXPORT = [
    ("customers", Customer),
    ("loyalty_accounts", LoyaltyAccount),
    ("tiers", Tier),
    ("rules", Rule),
    ("orders", Order),
    ("order_lines", OrderLine),
    ("points_transactions", PointsTransaction),
    ("rewards", Reward),
    ("redemptions", Redemption),
    ("expiry_batches", ExpiryBatch),
    ("point_lots", PointLot),
    ("transaction_lot_allocations", TransactionLotAllocation),
    ("account_tier_history", AccountTierHistory),
    ("order_returns", OrderReturn),
    ("audit_events", AuditEvent)
]

def compute_sha256(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

class DataExporter:
    def __init__(self, session: Session):
        self.session = session

    def export_all(self, seed: int = 20261022, scale: str = "full") -> Dict[str, Any]:
        """Exports all entities to CSV, JSON, and SQL seed files, generating scale-consistent manifests."""
        if scale == "starter":
            return self._export_starter_scale(seed=seed)
        else:
            return self._export_full_scale(seed=seed)

    def _export_full_scale(self, seed: int) -> Dict[str, Any]:
        csv_dir = EXPORTS_DIR / "csv"
        json_dir = EXPORTS_DIR / "json"
        sql_dir = EXPORTS_DIR / "sql"

        csv_dir.mkdir(parents=True, exist_ok=True)
        json_dir.mkdir(parents=True, exist_ok=True)
        sql_dir.mkdir(parents=True, exist_ok=True)

        checksums = {}
        row_counts = {}

        # 1. Export CSV & JSON for each entity from active database
        for table_name, model in ENTITIES_TO_EXPORT:
            columns = [c.name for c in model.__table__.columns]
            cursor_res = self.session.connection().execute(model.__table__.select()).fetchall()
            row_counts[table_name] = len(cursor_res)

            rows = []
            for r in cursor_res:
                row_dict = {}
                for idx, col in enumerate(columns):
                    val = r[idx]
                    if isinstance(val, datetime):
                        val = val.isoformat()
                    row_dict[col] = val
                rows.append(row_dict)

            # Write CSV
            csv_path = csv_dir / f"{table_name}.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            checksums[f"csv/{table_name}.csv"] = compute_sha256(str(csv_path))

            # Write JSON
            json_path = json_dir / f"{table_name}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(rows, f)
            checksums[f"json/{table_name}.json"] = compute_sha256(str(json_path))

        # 2. Export Ground Truth
        gt_records = self.session.query(GroundTruthRecord).all()
        gt_cols = [c.name for c in GroundTruthRecord.__table__.columns]
        gt_rows = [{col: getattr(r, col) for col in gt_cols} for r in gt_records]

        for p in [BASE_DIR / "ground_truth.csv", DATA_DIR / "ground_truth" / "ground_truth.csv"]:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=gt_cols)
                writer.writeheader()
                for r in gt_rows:
                    writer.writerow(r)

        for p in [BASE_DIR / "ground_truth.json", DATA_DIR / "ground_truth" / "ground_truth.json"]:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(gt_rows, f, indent=2)

        checksums["ground_truth.csv"] = compute_sha256(str(BASE_DIR / "ground_truth.csv"))
        checksums["ground_truth.json"] = compute_sha256(str(BASE_DIR / "ground_truth.json"))

        # 3. Export SQL Schema & Seeds
        sql_schema_path = sql_dir / "schema.sql"
        sql_seed_path = sql_dir / "seed.sql"

        with open(sql_schema_path, "w", encoding="utf-8") as f:
            f.write("-- Loyalty Ledger Intelligence Platform Schema (PostgreSQL / SQLite Compatible)\n")
            f.write("CREATE TABLE IF NOT EXISTS customers (\n")
            f.write("    customer_id VARCHAR(32) PRIMARY KEY,\n")
            f.write("    name VARCHAR(128) NOT NULL,\n")
            f.write("    email VARCHAR(128) NOT NULL UNIQUE,\n")
            f.write("    region VARCHAR(32) NOT NULL,\n")
            f.write("    status VARCHAR(16) NOT NULL,\n")
            f.write("    created_at TIMESTAMP NOT NULL\n")
            f.write(");\n\n")
            f.write("CREATE TABLE IF NOT EXISTS tiers (\n")
            f.write("    tier_id VARCHAR(32) PRIMARY KEY,\n")
            f.write("    tier_name VARCHAR(64) NOT NULL UNIQUE,\n")
            f.write("    min_qualifying_spend_minor INTEGER NOT NULL,\n")
            f.write("    spend_per_point_minor INTEGER NOT NULL,\n")
            f.write("    earning_rate_points INTEGER NOT NULL,\n")
            f.write("    effective_from TIMESTAMP NOT NULL,\n")
            f.write("    effective_to TIMESTAMP,\n")
            f.write("    status VARCHAR(16) NOT NULL\n")
            f.write(");\n\n")
            f.write("CREATE TABLE IF NOT EXISTS loyalty_accounts (\n")
            f.write("    account_id VARCHAR(32) PRIMARY KEY,\n")
            f.write("    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),\n")
            f.write("    current_tier_id VARCHAR(32) NOT NULL REFERENCES tiers(tier_id),\n")
            f.write("    status VARCHAR(16) NOT NULL,\n")
            f.write("    opened_at TIMESTAMP NOT NULL,\n")
            f.write("    closed_at TIMESTAMP,\n")
            f.write("    cached_balance_points INTEGER NOT NULL DEFAULT 0\n")
            f.write(");\n\n")
            f.write("CREATE TABLE IF NOT EXISTS points_transactions (\n")
            f.write("    transaction_id VARCHAR(32) PRIMARY KEY,\n")
            f.write("    account_id VARCHAR(32) NOT NULL REFERENCES loyalty_accounts(account_id),\n")
            f.write("    transaction_type VARCHAR(24) NOT NULL,\n")
            f.write("    points_delta INTEGER NOT NULL,\n")
            f.write("    event_at TIMESTAMP NOT NULL,\n")
            f.write("    effective_at TIMESTAMP NOT NULL,\n")
            f.write("    source_type VARCHAR(32) NOT NULL,\n")
            f.write("    source_id VARCHAR(64) NOT NULL,\n")
            f.write("    original_transaction_id VARCHAR(32),\n")
            f.write("    rule_id VARCHAR(32),\n")
            f.write("    status VARCHAR(16) NOT NULL,\n")
            f.write("    idempotency_key VARCHAR(64) NOT NULL UNIQUE,\n")
            f.write("    reason_code VARCHAR(32) NOT NULL,\n")
            f.write("    correlation_id VARCHAR(64) NOT NULL,\n")
            f.write("    created_at TIMESTAMP NOT NULL\n")
            f.write(");\n")

        with open(sql_seed_path, "w", encoding="utf-8") as f:
            f.write("-- Loyalty Ledger Sample Master Seed Data\n")
            for t_cfg in [
                ("TIER-BRONZE", "Bronze", 0, 10000, 1),
                ("TIER-SILVER", "Silver", 1000000, 5000, 2),
                ("TIER-GOLD", "Gold", 5000000, 3333, 3)
            ]:
                f.write(f"INSERT INTO tiers (tier_id, tier_name, min_qualifying_spend_minor, spend_per_point_minor, earning_rate_points, effective_from, status) VALUES ('{t_cfg[0]}', '{t_cfg[1]}', {t_cfg[2]}, {t_cfg[3]}, {t_cfg[4]}, '2026-01-01 00:00:00', 'ACTIVE') ON CONFLICT DO NOTHING;\n")

        checksums["sql/schema.sql"] = compute_sha256(str(sql_schema_path))
        checksums["sql/seed.sql"] = compute_sha256(str(sql_seed_path))

        # 4. Manifests
        now_iso = datetime.now(timezone.utc).isoformat()
        dataset_manifest = {
            "generator_name": "Loyalty Ledger Synthetic Factory",
            "generator_version": "1.0.0",
            "seed": seed,
            "scale": "full",
            "simulated_start": "2026-01-01T00:00:00Z",
            "simulated_end": "2026-10-22T23:59:59Z",
            "created_at": now_iso,
            "row_counts": row_counts,
            "checksums": checksums
        }
        with open(BASE_DIR / "dataset_manifest.json", "w", encoding="utf-8") as f:
            json.dump(dataset_manifest, f, indent=2)

        with open(REPORTS_DIR / "dataset_manifest.json", "w", encoding="utf-8") as f:
            json.dump(dataset_manifest, f, indent=2)

        source_manifest = {
            "provenance": "100% Synthetic Data Factory",
            "external_personal_data_used": False,
            "legal_terms": "Synthetic benchmark data for testing, evaluation and demonstration",
            "fixed_seed": seed,
            "default_timezone": "UTC",
            "currency": "INR (Paise)",
            "generator_version": "1.0.0"
        }
        with open(BASE_DIR / "source_manifest.json", "w", encoding="utf-8") as f:
            json.dump(source_manifest, f, indent=2)

        return dataset_manifest

    def _export_starter_scale(self, seed: int) -> Dict[str, Any]:
        """Generates and exports an isolated starter scale dataset without affecting the full scale database."""
        temp_dir = tempfile.mkdtemp(prefix="loyalty_export_starter_")
        db_path = os.path.join(temp_dir, "starter_export.db")
        eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=eng)
        sess_factory = sessionmaker(bind=eng)
        sess = sess_factory()

        os.environ["LOYALTY_DISABLE_FK"] = "1"
        try:
            gen = SyntheticDataGenerator(seed=seed)
            gen_res = gen.generate_dataset(session=sess, scale="starter")
            inj = AnomalyInjector(session=sess, seed=seed)
            inj.inject_anomalies(start_tx_idx=gen_res["transactions_count"] + 1)

            starter_dir = EXPORTS_DIR / "starter"
            csv_dir = starter_dir / "csv"
            json_dir = starter_dir / "json"
            sql_dir = starter_dir / "sql"

            csv_dir.mkdir(parents=True, exist_ok=True)
            json_dir.mkdir(parents=True, exist_ok=True)
            sql_dir.mkdir(parents=True, exist_ok=True)

            checksums = {}
            row_counts = {}

            for table_name, model in ENTITIES_TO_EXPORT:
                columns = [c.name for c in model.__table__.columns]
                cursor_res = sess.connection().execute(model.__table__.select()).fetchall()
                row_counts[table_name] = len(cursor_res)

                rows = []
                for r in cursor_res:
                    row_dict = {}
                    for idx, col in enumerate(columns):
                        val = r[idx]
                        if isinstance(val, datetime):
                            val = val.isoformat()
                        row_dict[col] = val
                    rows.append(row_dict)

                csv_path = csv_dir / f"{table_name}.csv"
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    for r in rows:
                        writer.writerow(r)
                checksums[f"csv/{table_name}.csv"] = compute_sha256(str(csv_path))

                json_path = json_dir / f"{table_name}.json"
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(rows, f)
                checksums[f"json/{table_name}.json"] = compute_sha256(str(json_path))

            now_iso = datetime.now(timezone.utc).isoformat()
            starter_manifest = {
                "generator_name": "Loyalty Ledger Synthetic Factory",
                "generator_version": "1.0.0",
                "seed": seed,
                "scale": "starter",
                "simulated_start": "2026-01-01T00:00:00Z",
                "simulated_end": "2026-10-22T23:59:59Z",
                "created_at": now_iso,
                "row_counts": row_counts,
                "checksums": checksums
            }

            with open(starter_dir / "dataset_manifest.json", "w", encoding="utf-8") as f:
                json.dump(starter_manifest, f, indent=2)
            with open(REPORTS_DIR / "dataset_manifest_starter.json", "w", encoding="utf-8") as f:
                json.dump(starter_manifest, f, indent=2)
            with open(BASE_DIR / "dataset_manifest_starter.json", "w", encoding="utf-8") as f:
                json.dump(starter_manifest, f, indent=2)

            return starter_manifest
        finally:
            os.environ.pop("LOYALTY_DISABLE_FK", None)
            sess.close()
            eng.dispose()
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
