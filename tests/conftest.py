"""Pytest session configuration ensuring complete database isolation for test runs."""
import os
from pathlib import Path
import pytest

# Isolate all tests to a dedicated test database to protect production/starter datasets
_BASE_DIR = Path(__file__).resolve().parent.parent
_TEST_DB = _BASE_DIR / "data" / "test_loyalty_ledger.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

@pytest.fixture(scope="session", autouse=True)
def isolate_test_database():
    """Initializes and seeds an isolated test database if empty."""
    from loyalty_ledger.db import init_db, SessionFactory
    from loyalty_ledger.domain.models import Customer
    from loyalty_ledger.generator.data_generator import SyntheticDataGenerator
    from loyalty_ledger.anomaly_detection.anomaly_injector import AnomalyInjector

    init_db()
    session = SessionFactory()
    try:
        if session.query(Customer).count() == 0:
            gen = SyntheticDataGenerator(seed=20261022)
            res = gen.generate_dataset(session=session, scale="starter")
            inj = AnomalyInjector(session=session, seed=20261022)
            inj.inject_anomalies(start_tx_idx=res["transactions_count"] + 1)
    finally:
        session.close()

    yield
