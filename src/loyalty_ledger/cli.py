"""Command-line interface for generating, validating, exporting, and serving the loyalty platform."""
import argparse
import sys
import json
from loyalty_ledger.db import create_app_engine, Base, SessionFactory, init_db
from loyalty_ledger.generator.data_generator import SyntheticDataGenerator
from loyalty_ledger.anomaly_detection.anomaly_injector import AnomalyInjector
from loyalty_ledger.anomaly_detection.detector import AnomalyDetector
from loyalty_ledger.anomaly_detection.evaluator import AnomalyEvaluator
from loyalty_ledger.validation.validator import ValidationEngine
from loyalty_ledger.reports.exporter import DataExporter
from loyalty_ledger.reports.reproducibility import ReproducibilityVerifier
from loyalty_ledger.config import REPORTS_DIR, BASE_DIR

def run_generate(args):
    import os
    from pathlib import Path
    print(f"=== Generating Dataset (scale={args.scale}, seed={args.seed}) ===")
    os.environ["LOYALTY_DISABLE_FK"] = "1"

    # Clean up unresolved Git LFS pointer file if present before initializing database
    from loyalty_ledger.config import DATABASE_URL
    from loyalty_ledger.db import remove_lfs_pointer_if_present
    if remove_lfs_pointer_if_present(DATABASE_URL):
        print(f"Detected Git LFS pointer text file at {DATABASE_URL}; removed pointer to initialize a fresh SQLite database.")

    init_db()
    session = SessionFactory()
    try:
        # Clear existing data if clean generation requested
        if args.clean:
            print("Cleaning existing database tables...")
            Base.metadata.drop_all(bind=session.get_bind())
            Base.metadata.create_all(bind=session.get_bind())

        generator = SyntheticDataGenerator(seed=args.seed)
        res = generator.generate_dataset(
            session=session,
            scale=args.scale,
            custom_customers=args.customers,
            custom_orders=args.orders,
            custom_transactions=args.transactions
        )

        if not args.no_anomalies:
            print("Injecting mandatory anomalies (AN-001 through AN-005)...")
            injector = AnomalyInjector(session=session, seed=args.seed)
            next_tx = res["transactions_count"] + 1
            gt_records, final_tx_count = injector.inject_anomalies(start_tx_idx=next_tx)
            print(f"Injected {len(gt_records)} anomaly cases into Ground Truth. Final points transactions count: {final_tx_count - 1}")

        # Automatically export datasets and manifests
        print("Generating canonical exports (CSV, JSON, SQL) and manifests...")
        exporter = DataExporter(session=session)
        manifest = exporter.export_all(seed=args.seed, scale=args.scale)
        print("Dataset generation complete!")
        print(json.dumps(manifest["row_counts"], indent=2))
    finally:
        os.environ.pop("LOYALTY_DISABLE_FK", None)
        session.close()

def run_validate(args):
    scale_arg = getattr(args, "scale", "auto")
    print(f"=== Running Validation Suite (mode={args.mode}, scale={scale_arg}) ===")
    session = SessionFactory()
    try:
        engine = ValidationEngine(session=session)
        summary = engine.validate_all(mode=args.mode, scale=scale_arg if scale_arg != "auto" else None)

        # Save machine-readable validation_summary.json
        summary_path = REPORTS_DIR / "validation_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        with open(BASE_DIR / "validation_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Save human-readable validation_report.md
        md_lines = [
            "# Validation Report: Loyalty Ledger Intelligence Platform\n",
            f"- **Validation Timestamp**: {summary['validation_timestamp']}",
            f"- **Validation Mode**: {summary['mode']}",
            f"- **Overall Status**: **{summary['overall_status']}**",
            f"- **Checks Passed**: {summary['passed_checks']} / {summary['total_checks']}",
            f"- **Checks Failed**: {summary['failed_checks']}\n",
            "| # | Check Name | Entity | Status | Severity | Details |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        for f in summary["findings"]:
            status_badge = "PASS" if f["passed"] else "FAIL"
            md_lines.append(f"| {f['check_number']} | {f['name']} | {f['entity']} | {status_badge} | {f['severity']} | {f['explanation']} |")

        report_path = REPORTS_DIR / "validation_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
        with open(BASE_DIR / "validation_report.md", "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        print(f"Validation finished: {summary['passed_checks']}/{summary['total_checks']} checks passed.")
        print(f"Saved reports to {summary_path} and {report_path}")
    finally:
        session.close()

def run_reproduce(args):
    print(f"=== Running Two-Run Reproducibility Verification (seed={args.seed}, scale={args.scale}) ===")
    verifier = ReproducibilityVerifier(seed=args.seed, scale=args.scale)
    report = verifier.verify()
    print("Reproducibility Result:")
    print(json.dumps(report, indent=2))
    if not report["reproducible"]:
        sys.exit(1)

def run_export(args):
    print(f"=== Exporting Datasets (scale={args.scale}, seed={args.seed}) ===")
    session = SessionFactory()
    try:
        exporter = DataExporter(session=session)
        manifest = exporter.export_all(seed=args.seed, scale=args.scale)
        print("Exports completed successfully:")
        print(json.dumps(manifest["checksums"], indent=2))
    finally:
        session.close()

def run_evaluate(args):
    print("=== Evaluating Anomaly Detection against Ground Truth ===")
    session = SessionFactory()
    try:
        detector = AnomalyDetector(session)
        findings = detector.detect_all()
        evaluator = AnomalyEvaluator(session)
        metrics = evaluator.evaluate(findings)

        metrics_path = REPORTS_DIR / "evaluation_metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        with open(BASE_DIR / "evaluation_metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        print(json.dumps(metrics, indent=2))
    finally:
        session.close()

def run_serve(args):
    import uvicorn
    print(f"Starting Loyalty Ledger API & Web Console on http://{args.host}:{args.port}")
    uvicorn.run("loyalty_ledger.api.main:app", host=args.host, port=args.port, reload=args.reload)

def main():
    parser = argparse.ArgumentParser(prog="loyalty-ledger", description="Loyalty Ledger Intelligence Platform CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    gen_p = subparsers.add_parser("generate", help="Generate synthetic loyalty dataset")
    gen_p.add_argument("--scale", choices=["starter", "full", "custom"], default="starter", help="Dataset scale")
    gen_p.add_argument("--seed", type=int, default=20261022, help="Deterministic random seed")
    gen_p.add_argument("--customers", type=int, default=None, help="Custom customer count")
    gen_p.add_argument("--orders", type=int, default=None, help="Custom order count")
    gen_p.add_argument("--transactions", type=int, default=None, help="Custom points transaction count")
    gen_p.add_argument("--clean", action="store_true", default=True, help="Clean database before generation")
    gen_p.add_argument("--no-anomalies", action="store_true", help="Skip anomaly injection")
    gen_p.set_defaults(func=run_generate)

    # validate
    val_p = subparsers.add_parser("validate", help="Run 20-check validation suite")
    val_p.add_argument("--mode", choices=["baseline", "evaluation"], default="baseline", help="Validation mode")
    val_p.add_argument("--scale", choices=["starter", "full", "auto"], default="auto", help="Profile scale to validate against (default: auto)")
    val_p.set_defaults(func=run_validate)

    # reproduce
    rep_p = subparsers.add_parser("reproduce", help="Run two-run reproducibility verification")
    rep_p.add_argument("--scale", choices=["starter", "full"], default="starter", help="Scale for test")
    rep_p.add_argument("--seed", type=int, default=20261022, help="Seed to verify")
    rep_p.set_defaults(func=run_reproduce)

    # export
    exp_p = subparsers.add_parser("export", help="Export dataset to CSV, JSON, and SQL")
    exp_p.add_argument("--scale", default="starter", help="Dataset scale tag")
    exp_p.add_argument("--seed", type=int, default=20261022, help="Seed tag")
    exp_p.set_defaults(func=run_export)

    # evaluate
    eval_p = subparsers.add_parser("evaluate", help="Compute detection PR/Recall/F1 metrics")
    eval_p.set_defaults(func=run_evaluate)

    # serve
    srv_p = subparsers.add_parser("serve", help="Start web dashboard and API server")
    srv_p.add_argument("--host", default="0.0.0.0", help="Bind host")
    srv_p.add_argument("--port", type=int, default=8000, help="Bind port")
    srv_p.add_argument("--reload", action="store_true", help="Auto-reload on code change")
    srv_p.set_defaults(func=run_serve)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
