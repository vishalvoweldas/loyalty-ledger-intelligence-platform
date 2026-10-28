"""FastAPI API routes implementing all requested loyalty ledger endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from loyalty_ledger.db import get_db, begin_write_transaction
from loyalty_ledger.domain.models import (
    Customer, LoyaltyAccount, Tier, Rule, Order, OrderLine,
    PointsTransaction, Reward, Redemption, ExpiryBatch, PointLot,
    OrderReturn, AuditEvent, GroundTruthRecord
)
from loyalty_ledger.domain.schemas import (
    CustomerResponse, LoyaltyAccountResponse, TierResponse, RuleResponse,
    OrderResponse, PointsTransactionResponse, RewardResponse,
    RedemptionRequest, RedemptionResponse, ReturnRequest,
    ExpiryBatchRequest, ExpiryBatchResponse, ReconciliationReport,
    DashboardSummary, AnomalyReportItem, ValidationFinding
)
from loyalty_ledger.ledger.ledger import LedgerService
from loyalty_ledger.services.accrual_service import AccrualService
from loyalty_ledger.services.redemption_service import RedemptionService
from loyalty_ledger.services.returns_service import ReturnsService
from loyalty_ledger.services.expiry_service import ExpiryService
from loyalty_ledger.services.tier_service import TierService
from loyalty_ledger.anomaly_detection.detector import AnomalyDetector
from loyalty_ledger.anomaly_detection.evaluator import AnomalyEvaluator
from loyalty_ledger.validation.validator import ValidationEngine
from loyalty_ledger.reports.exporter import DataExporter
from loyalty_ledger.reports.reproducibility import ReproducibilityVerifier

router = APIRouter(prefix="/api/v1")

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint checking database connectivity."""
    db.execute(Customer.__table__.select().limit(1))
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected",
        "version": "1.0.0"
    }

_DASHBOARD_ANOMALY_CACHE = {}

@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    response: Response,
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Aggregates executive dashboard metrics."""
    total_cus = db.query(Customer).count()
    total_ord = db.query(Order).count()
    total_tx = db.query(PointsTransaction).count()

    from sqlalchemy import func
    type_sums = dict(
        db.query(
            PointsTransaction.transaction_type,
            func.sum(PointsTransaction.points_delta)
        ).group_by(PointsTransaction.transaction_type).all()
    )
    accrued = int(type_sums.get("ACCRUAL", 0) or 0)
    redeemed = int(abs(type_sums.get("REDEMPTION", 0) or 0))
    reversed_pts = int(abs(type_sums.get("REVERSAL", 0) or 0))
    expired = int(abs(type_sums.get("EXPIRY", 0) or 0))
    outstanding = accrued - redeemed - reversed_pts - expired

    # Tier distribution
    tier_dist = dict(
        db.query(
            LoyaltyAccount.current_tier_id,
            func.count(LoyaltyAccount.account_id)
        ).group_by(LoyaltyAccount.current_tier_id).all()
    )

    # Anomaly counts (cached per db_url with short 15s TTL, bypassable via force_refresh)
    import time
    db_url = str(db.get_bind().url)
    now_ts = time.time()
    
    if force_refresh and db_url in _DASHBOARD_ANOMALY_CACHE:
        del _DASHBOARD_ANOMALY_CACHE[db_url]

    cached = _DASHBOARD_ANOMALY_CACHE.get(db_url)
    is_cached = False
    cache_age = 0.0
    if (not force_refresh) and cached and (now_ts - cached["time"] < 15.0):
        anomalies_by_type = cached["by_type"]
        anomalies_by_sev = cached["by_sev"]
        is_cached = True
        cache_age = round(now_ts - cached["time"], 2)
        response.headers["X-Cache"] = "HIT"
    else:
        detector = AnomalyDetector(db)
        detected = detector.detect_all()
        anomalies_by_type = {}
        anomalies_by_sev = {}
        for d in detected:
            t = d["issue_type"]
            s = d["severity"]
            anomalies_by_type[t] = anomalies_by_type.get(t, 0) + 1
            anomalies_by_sev[s] = anomalies_by_sev.get(s, 0) + 1
        _DASHBOARD_ANOMALY_CACHE[db_url] = {"time": now_ts, "by_type": anomalies_by_type, "by_sev": anomalies_by_sev}
        response.headers["X-Cache"] = "MISS"

    # Reconciliation mismatches
    mismatches = anomalies_by_type.get("STORED_BALANCE_MISMATCH", 0)

    approved_rdm = db.query(Redemption).filter_by(status="APPROVED").count()
    rejected_rdm = db.query(Redemption).filter_by(status="REJECTED").count()

    return DashboardSummary(
        total_customers=total_cus,
        total_orders=total_ord,
        total_points_transactions=total_tx,
        total_points_accrued=accrued,
        total_points_redeemed=redeemed,
        total_points_reversed=reversed_pts,
        total_points_expired=expired,
        total_outstanding_points=outstanding,
        reconciliation_mismatches_count=mismatches,
        tier_distribution=tier_dist,
        anomalies_by_type=anomalies_by_type,
        anomalies_by_severity=anomalies_by_sev,
        redemption_stats={"approved": approved_rdm, "rejected": rejected_rdm},
        is_cached=is_cached,
        cache_age_seconds=cache_age
    )

@router.get("/customers", response_model=List[CustomerResponse])
def list_customers(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    region: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Customer)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            Customer.name.ilike(search_term) |
            Customer.email.ilike(search_term) |
            Customer.customer_id.ilike(search_term)
        )
    if region:
        query = query.filter(Customer.region == region)
    total_count = query.count()
    response.headers["X-Total-Count"] = str(total_count)
    return query.order_by(Customer.customer_id.asc()).offset((page - 1) * page_size).limit(page_size).all()

@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    cus = db.query(Customer).filter_by(customer_id=customer_id).first()
    if not cus:
        raise HTTPException(status_code=404, detail="Customer not found")
    return cus

@router.get("/accounts/{account_id}", response_model=LoyaltyAccountResponse)
def get_account(account_id: str, db: Session = Depends(get_db)):
    acc = db.query(LoyaltyAccount).filter_by(account_id=account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Loyalty account not found")
    return acc

@router.get("/accounts/{account_id}/ledger", response_model=List[PointsTransactionResponse])
def get_account_ledger(
    response: Response,
    account_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    transaction_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(PointsTransaction).filter_by(account_id=account_id)
    if transaction_type:
        query = query.filter_by(transaction_type=transaction_type)
    total_count = query.count()
    response.headers["X-Total-Count"] = str(total_count)
    return query.order_by(PointsTransaction.event_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

@router.get("/accounts/{account_id}/reconciliation", response_model=ReconciliationReport)
def reconcile_account_endpoint(account_id: str, db: Session = Depends(get_db)):
    ledger = LedgerService(db)
    rep = ledger.reconcile_account(account_id)
    if "error" in rep:
        raise HTTPException(status_code=404, detail=rep["error"])
    return rep

@router.get("/orders", response_model=List[OrderResponse])
def list_orders(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Order)
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    if status:
        query = query.filter_by(status=status)
    total_count = query.count()
    response.headers["X-Total-Count"] = str(total_count)
    return query.order_by(Order.order_date.desc()).offset((page - 1) * page_size).limit(page_size).all()

@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, db: Session = Depends(get_db)):
    ord_obj = db.query(Order).filter_by(order_id=order_id).first()
    if not ord_obj:
        raise HTTPException(status_code=404, detail="Order not found")
    return ord_obj

@router.post("/orders/{order_id}/accrue", response_model=PointsTransactionResponse)
def accrue_order_points(
    order_id: str,
    idempotency_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    service = AccrualService(db)
    tx = service.accrue_points_for_order(order_id, idempotency_key=idempotency_key)
    if not tx:
        raise HTTPException(status_code=400, detail="Order not eligible for points accrual")
    db.commit()
    return tx

@router.post("/orders/{order_id}/returns")
def process_return(
    order_id: str,
    req: ReturnRequest,
    db: Session = Depends(get_db)
):
    service = ReturnsService(db)
    returned_lines_dict = [{"order_line_id": l.order_line_id, "quantity": l.quantity} for l in req.returned_lines]
    try:
        ret = service.process_order_return(
            order_id=order_id,
            returned_lines=returned_lines_dict,
            reason=req.reason,
            idempotency_key=req.idempotency_key
        )
        db.commit()
        rev_tx = None
        points_reversed = 0
        if ret.reversal_transaction_id:
            rev_tx = db.query(PointsTransaction).filter_by(transaction_id=ret.reversal_transaction_id).first()
            if rev_tx:
                points_reversed = abs(rev_tx.points_delta)
        return {
            "status": "PROCESSED",
            "return_id": ret.return_id,
            "order_id": ret.order_id,
            "returned_eligible_spend_minor": ret.returned_eligible_spend_minor,
            "reversal_transaction_id": ret.reversal_transaction_id,
            "points_reversed": points_reversed
        }
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/redemptions", response_model=RedemptionResponse)
def create_redemption(
    req: RedemptionRequest,
    db: Session = Depends(get_db)
):
    service = RedemptionService(db)
    try:
        rdm = service.process_redemption(
            account_id=req.account_id,
            reward_id=req.reward_id,
            requested_points=req.requested_points,
            idempotency_key=req.idempotency_key
        )
        db.commit()
        return rdm
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/redemptions/{redemption_id}", response_model=RedemptionResponse)
def get_redemption(redemption_id: str, db: Session = Depends(get_db)):
    rdm = db.query(Redemption).filter_by(redemption_id=redemption_id).first()
    if not rdm:
        raise HTTPException(status_code=404, detail="Redemption not found")
    return rdm

@router.post("/expiry-batches", response_model=ExpiryBatchResponse)
def trigger_expiry_batch(
    req: ExpiryBatchRequest,
    db: Session = Depends(get_db)
):
    service = ExpiryService(db)
    batch = service.run_expiry_batch(cutoff_at=req.cutoff_at, idempotency_key=req.idempotency_key)
    db.commit()
    return batch

@router.get("/tiers", response_model=List[TierResponse])
def list_tiers(db: Session = Depends(get_db)):
    return db.query(Tier).all()

@router.get("/rules", response_model=List[RuleResponse])
def list_rules(db: Session = Depends(get_db)):
    return db.query(Rule).all()

@router.get("/anomalies")
def list_anomalies(
    issue_type: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db)
):
    detector = AnomalyDetector(db)
    findings = detector.detect_all()
    if issue_type:
        findings = [f for f in findings if f["issue_type"] == issue_type]
    if severity:
        findings = [f for f in findings if f["severity"] == severity]
    return findings

@router.get("/anomalies/evaluation")
def get_anomaly_evaluation(db: Session = Depends(get_db)):
    detector = AnomalyDetector(db)
    findings = detector.detect_all()
    evaluator = AnomalyEvaluator(db)
    return evaluator.evaluate(findings)

@router.post("/anomalies/{anomaly_id}/review")
def review_anomaly(
    anomaly_id: str,
    action: str = Query("REVIEWED"),
    notes: Optional[str] = None,
    actor: str = Query("ops_manager"),
    db: Session = Depends(get_db)
):
    """Appends an operational audit event for an anomaly investigation without altering ledger history."""
    begin_write_transaction(db)
    now = datetime.now(timezone.utc)
    audit = AuditEvent(
        audit_id=f"AUD-{anomaly_id}-{now.strftime('%Y%m%d%H%M%S')}",
        entity_type="ANOMALY",
        entity_id=anomaly_id,
        action=action,
        actor=actor,
        timestamp=now,
        details=notes
    )
    db.add(audit)
    db.commit()
    return {"status": "success", "audit_id": audit.audit_id}

@router.post("/reconciliation/run")
def run_full_reconciliation(db: Session = Depends(get_db)):
    ledger = LedgerService(db)
    accounts = db.query(LoyaltyAccount).all()
    mismatches = []
    for acc in accounts:
        r = ledger.reconcile_account(acc.account_id)
        if not r["is_reconciled"]:
            mismatches.append(r)
    return {
        "total_accounts_checked": len(accounts),
        "reconciled_accounts": len(accounts) - len(mismatches),
        "mismatches_count": len(mismatches),
        "mismatches": mismatches
    }

@router.post("/validation/run")
def run_validation(
    mode: str = Query("baseline"),
    db: Session = Depends(get_db)
):
    engine = ValidationEngine(db)
    return engine.validate_all(mode=mode)

@router.get("/anomalies/{anomaly_id}")
def get_anomaly_by_id(anomaly_id: str, db: Session = Depends(get_db)):
    """Fetch details of a specific detected anomaly or ground-truth record."""
    detector = AnomalyDetector(db)
    findings = detector.detect_all()
    for f in findings:
        if f.get("affected_record_id") == anomaly_id or f.get("issue_type") == anomaly_id:
            return f
    gt = db.query(GroundTruthRecord).filter_by(anomaly_id=anomaly_id).first()
    if gt:
        return {
            "anomaly_id": gt.anomaly_id,
            "issue_type": gt.issue_type,
            "affected_entity": gt.affected_entity,
            "affected_record_id": gt.affected_record_id,
            "customer_id": gt.customer_id,
            "account_id": gt.account_id,
            "severity": gt.severity,
            "expected_state": gt.expected_outcome,
            "observed_state": "Injected evaluation anomaly",
            "explanation": gt.explanation
        }
    raise HTTPException(status_code=404, detail="Anomaly not found")

@router.post("/datasets/generate")
def generate_dataset_endpoint(
    scale: str = Query("starter"),
    seed: int = Query(20261022),
    inject_anomalies: bool = Query(True),
    db: Session = Depends(get_db)
):
    """Generates synthetic dataset and optionally injects mandatory anomaly cases."""
    from loyalty_ledger.generator.data_generator import SyntheticDataGenerator
    from loyalty_ledger.anomaly_detection.anomaly_injector import AnomalyInjector
    
    gen = SyntheticDataGenerator(seed=seed)
    res = gen.generate_dataset(session=db, scale=scale)
    anomalies_count = 0
    if inject_anomalies:
        inj = AnomalyInjector(session=db, seed=seed)
        anomalies_count = len(inj.inject_anomalies(start_tx_idx=res["transactions_count"] + 1))
    return {
        "status": "COMPLETED",
        "scale": scale,
        "seed": seed,
        "customers_count": res["customers_count"],
        "orders_count": res["orders_count"],
        "transactions_count": res["transactions_count"],
        "anomalies_injected": anomalies_count
    }

@router.post("/datasets/export")
def export_dataset_endpoint(
    scale: str = Query("full"),
    seed: int = Query(20261022),
    db: Session = Depends(get_db)
):
    exporter = DataExporter(db)
    manifest = exporter.export_all(seed=seed, scale=scale)
    return manifest

@router.get("/datasets/manifest")
def get_dataset_manifest_endpoint(scale: str = Query("full")):
    """Returns the scale-specific export manifest."""
    from loyalty_ledger.config import BASE_DIR, EXPORTS_DIR
    import json
    if scale == "starter":
        for p in [BASE_DIR / "dataset_manifest_starter.json", EXPORTS_DIR / "starter" / "dataset_manifest.json"]:
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
    full_file = BASE_DIR / "dataset_manifest.json"
    if full_file.exists():
        with open(full_file, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail=f"Manifest for scale '{scale}' not found")

@router.post("/reproducibility/verify")
def verify_reproducibility_endpoint(
    scale: str = Query("starter"),
    seed: int = Query(20261022)
):
    verifier = ReproducibilityVerifier(seed=seed, scale=scale)
    return verifier.verify()

@router.get("/reproducibility/report")
def get_reproducibility_report_endpoint(scale: str = Query("starter")):
    """Returns the scale-specific reproducibility verification report."""
    from loyalty_ledger.config import BASE_DIR
    import json
    scale_file = BASE_DIR / f"reproducibility_report_{scale}.json"
    if scale_file.exists():
        with open(scale_file, "r", encoding="utf-8") as f:
            return json.load(f)
    rep_file = BASE_DIR / "reproducibility_report.json"
    if rep_file.exists():
        with open(rep_file, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail=f"Reproducibility report for scale '{scale}' not found")

@router.get("/reports/summary")
def get_reports_summary():
    """Aggregates all evaluation, validation, reproducibility, and dataset manifests."""
    import json
    from loyalty_ledger.config import BASE_DIR
    
    summary = {}
    eval_file = BASE_DIR / "evaluation_metrics.json"
    val_file = BASE_DIR / "validation_summary.json"
    rep_file = BASE_DIR / "reproducibility_report.json"
    man_file = BASE_DIR / "dataset_manifest.json"
    
    if eval_file.exists():
        with open(eval_file, "r") as f:
            summary["evaluation"] = json.load(f)
    if val_file.exists():
        with open(val_file, "r") as f:
            summary["validation"] = json.load(f)
    if rep_file.exists():
        with open(rep_file, "r") as f:
            summary["reproducibility"] = json.load(f)
    if man_file.exists():
        with open(man_file, "r") as f:
            summary["dataset_manifest"] = json.load(f)
            
    return summary
