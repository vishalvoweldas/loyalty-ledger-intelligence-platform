"""Automated tests for mandatory anomaly scenarios, independent detector, and ground-truth evaluation."""
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loyalty_ledger.db import Base
from loyalty_ledger.generator.data_generator import SyntheticDataGenerator
from loyalty_ledger.anomaly_detection.anomaly_injector import AnomalyInjector
from loyalty_ledger.anomaly_detection.detector import AnomalyDetector
from loyalty_ledger.anomaly_detection.evaluator import AnomalyEvaluator

@pytest.fixture
def test_dataset_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()

    # Generate small starter scale
    gen = SyntheticDataGenerator(seed=20261022)
    res = gen.generate_dataset(session=session, scale="starter")

    # Inject anomalies
    inj = AnomalyInjector(session=session, seed=20261022)
    gt_records, _ = inj.inject_anomalies(start_tx_idx=res["transactions_count"] + 1)

    yield session
    session.close()

def test_mandatory_anomalies_injection(test_dataset_db):
    """Verifies that all 5 mandatory anomaly types are present in Ground Truth."""
    from loyalty_ledger.domain.models import GroundTruthRecord
    gts = test_dataset_db.query(GroundTruthRecord).all()
    types_found = {gt.issue_type for gt in gts}
    assert "AN-001" in types_found
    assert "AN-002" in types_found
    assert "AN-003" in types_found
    assert "AN-004" in types_found
    assert "AN-005" in types_found

def test_independent_detection_and_evaluation(test_dataset_db):
    """Verifies that the independent detector achieves 100% detection on mandatory test cases."""
    detector = AnomalyDetector(test_dataset_db)
    detected_findings = detector.detect_all()

    # Check detector detected each class
    detected_types = {d["issue_type"] for d in detected_findings}
    assert "AN-001" in detected_types
    assert "AN-002" in detected_types
    assert "AN-003" in detected_types
    assert "AN-004" in detected_types
    assert "AN-005" in detected_types

    # Evaluate against ground truth
    evaluator = AnomalyEvaluator(test_dataset_db)
    metrics = evaluator.evaluate(detected_findings)

    # Acceptance criteria: Target 100% detection (Recall = 1.0, Precision = 1.0, F1 = 1.0)
    assert metrics["overall"]["recall"] == 1.0
    assert metrics["overall"]["precision"] == 1.0
    assert metrics["overall"]["f1_score"] == 1.0
    assert metrics["overall"]["false_negatives"] == 0
