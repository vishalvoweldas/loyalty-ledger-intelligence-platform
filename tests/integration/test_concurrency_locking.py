"""Regression tests for SQLite concurrency, non-blocking reads, and serialized write atomicity."""
import pytest
import concurrent.futures
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from loyalty_ledger.api.main import app
from loyalty_ledger.db import SessionFactory, begin_write_transaction
from loyalty_ledger.domain.models import (
    Customer, LoyaltyAccount, PointLot, PointsTransaction, Reward, Redemption, TransactionLotAllocation, RedemptionAttempt
)
from loyalty_ledger.services.redemption_service import RedemptionService

@pytest.fixture(scope="module")
def api_client():
    return TestClient(app)

def test_concurrent_read_smoke_test(api_client):
    """
    Issues multiple simultaneous read requests to critical read endpoints:
    - /api/v1/customers
    - /api/v1/orders
    - /api/v1/accounts/LOY-CUS-000001/ledger
    - /api/v1/dashboard/summary
    - /api/v1/anomalies
    Verifies that zero 500 errors, zero database-locked errors, and zero timeouts occur.
    """
    endpoints = [
        "/api/v1/customers?limit=20",
        "/api/v1/orders?limit=20",
        "/api/v1/accounts/LOY-CUS-000001/ledger",
        "/api/v1/dashboard/summary",
        "/api/v1/anomalies"
    ]

    total_rounds = 3
    workers_per_round = 10
    total_requests = 0
    successful_requests = 0
    errors = []

    for round_num in range(total_rounds):
        # 5 endpoints * 3 repetitions = 15 requests per round
        urls_to_request = endpoints * 3
        total_requests += len(urls_to_request)

        def make_request(url):
            try:
                resp = api_client.get(url)
                return (url, resp.status_code, None)
            except Exception as e:
                return (url, 500, str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers_per_round) as executor:
            results = list(executor.map(make_request, urls_to_request))

        for url, status_code, err in results:
            if status_code == 200:
                successful_requests += 1
            else:
                errors.append((round_num, url, status_code, err))

    assert len(errors) == 0, f"Encountered {len(errors)} errors during concurrent read smoke test: {errors}"
    assert successful_requests == total_requests
    assert total_requests == total_rounds * len(endpoints) * 3

def test_mixed_workload_concurrent_reads_and_writes(api_client):
    """
    Simulates a mixed workload where multiple concurrent readers query ledger and dashboard
    while competing write transactions attempt points redemptions against the same account.
    Verifies:
    1. Zero HTTP 500 / database locked exceptions.
    2. Overspending prevention: points are never double-spent.
    3. Account balance and lot allocations remain mathematically exact.
    """
    # 1. Setup a dedicated test account with 100 points in 1 lot
    session = SessionFactory()
    begin_write_transaction(session)
    test_cus_id = "CUS-CONC-TEST-001"
    test_acc_id = "LOY-CONC-TEST-001"
    existing_acc = session.query(LoyaltyAccount).filter_by(account_id=test_acc_id).first()
    if existing_acc:
        alloc_ids = [lot.lot_id for lot in session.query(PointLot).filter_by(account_id=test_acc_id).all()]
        if alloc_ids:
            session.query(TransactionLotAllocation).filter(TransactionLotAllocation.lot_id.in_(alloc_ids)).delete(synchronize_session=False)
        session.query(Redemption).filter_by(account_id=test_acc_id).delete()
        session.query(RedemptionAttempt).filter_by(account_id=test_acc_id).delete()
        session.query(PointLot).filter_by(account_id=test_acc_id).delete()
        session.query(PointsTransaction).filter_by(account_id=test_acc_id).delete()
        session.query(LoyaltyAccount).filter_by(account_id=test_acc_id).delete()
        session.query(Customer).filter_by(customer_id=test_cus_id).delete()
        session.commit()

    test_cus = Customer(
        customer_id=test_cus_id,
        name="Concurrency Tester",
        email="conc_tester@example.com",
        region="NORTH",
        status="ACTIVE",
        created_at=datetime.now(timezone.utc)
    )
    test_acc = LoyaltyAccount(
        account_id=test_acc_id,
        customer_id=test_cus_id,
        current_tier_id="TIER-BRONZE",
        opened_at=datetime.now(timezone.utc),
        cached_balance_points=100,
        status="ACTIVE"
    )
    init_tx = PointsTransaction(
        transaction_id="PTS-CONC-INIT",
        account_id=test_acc_id,
        transaction_type="ACCRUAL",
        points_delta=100,
        event_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        effective_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_type="MANUAL",
        source_id="INIT",
        status="POSTED",
        idempotency_key="IDEMP-CONC-INIT",
        reason_code="ACCRUAL",
        correlation_id="CORR-CONC-INIT",
        created_at=datetime.now(timezone.utc)
    )
    test_lot = PointLot(
        lot_id=f"LOT-{test_acc_id}-01",
        account_id=test_acc_id,
        source_transaction_id="PTS-CONC-INIT",
        original_points=100,
        remaining_points=100,
        accrued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        status="OPEN"
    )
    session.add(test_cus)
    session.add(test_acc)
    session.add(init_tx)
    session.flush()
    session.add(test_lot)
    session.commit()
    session.close()

    # 2. Fire 10 concurrent redemption requests for 60 points each (only 1 can succeed, remainder rejected)
    # AND 20 concurrent read requests at the same time.
    results = {"reads_ok": 0, "reads_failed": 0, "approved_rdm": 0, "rejected_rdm": 0, "write_errors": 0}

    read_endpoints = [
        "/api/v1/customers?limit=10",
        "/api/v1/orders?limit=10",
        "/api/v1/accounts/LOY-CUS-000001/ledger",
        "/api/v1/dashboard/summary"
    ]

    def run_reader(idx):
        try:
            url = read_endpoints[idx % len(read_endpoints)]
            resp = api_client.get(url)
            if resp.status_code == 200:
                results["reads_ok"] += 1
            else:
                results["reads_failed"] += 1
        except Exception:
            results["reads_failed"] += 1

    def run_writer(idx):
        s = SessionFactory()
        svc = RedemptionService(s)
        try:
            rdm = svc.process_redemption(
                account_id=test_acc_id,
                reward_id="REW-VOUCHER-100",
                requested_points=60,
                idempotency_key=f"IDEMP-CONC-{idx:03d}",
                redemption_id=f"RDM-CONC-{idx:03d}"
            )
            s.commit()
            if rdm.status == "APPROVED":
                results["approved_rdm"] += 1
            elif rdm.status == "REJECTED":
                results["rejected_rdm"] += 1
        except Exception as e:
            s.rollback()
            results["write_errors"] += 1
            print(f"Writer {idx} failed: {e}")
        finally:
            s.close()

    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        for i in range(20):
            tasks.append(executor.submit(run_reader, i))
        for i in range(10):
            tasks.append(executor.submit(run_writer, i))
        concurrent.futures.wait(tasks)

    # 3. Assert zero read failures and zero write lock crashes
    assert results["reads_failed"] == 0, f"Read failures: {results['reads_failed']}"
    assert results["write_errors"] == 0, f"Write errors: {results['write_errors']}"
    assert results["reads_ok"] == 20
    # Exactly 1 redemption can be approved for 60 points out of 100 available!
    assert results["approved_rdm"] == 1, f"Expected 1 approved redemption, got {results['approved_rdm']}"
    assert results["rejected_rdm"] == 9, f"Expected 9 rejected redemptions, got {results['rejected_rdm']}"

    # 4. Verify post-workload ledger and lot integrity
    verify_session = SessionFactory()
    acc = verify_session.query(LoyaltyAccount).filter_by(account_id=test_acc_id).first()
    lot = verify_session.query(PointLot).filter_by(lot_id=f"LOT-{test_acc_id}-01").first()

    assert acc.cached_balance_points == 40, f"Expected remaining 40 points, got {acc.cached_balance_points}"
    assert lot.remaining_points == 40, f"Expected lot remaining 40 points, got {lot.remaining_points}"
    assert lot.status == "OPEN"

    # Clean up test records
    alloc_ids = [lot.lot_id for lot in verify_session.query(PointLot).filter_by(account_id=test_acc_id).all()]
    if alloc_ids:
        verify_session.query(TransactionLotAllocation).filter(TransactionLotAllocation.lot_id.in_(alloc_ids)).delete(synchronize_session=False)
    verify_session.query(Redemption).filter_by(account_id=test_acc_id).delete()
    verify_session.query(RedemptionAttempt).filter_by(account_id=test_acc_id).delete()
    verify_session.query(PointLot).filter_by(account_id=test_acc_id).delete()
    verify_session.query(PointsTransaction).filter_by(account_id=test_acc_id).delete()
    verify_session.query(LoyaltyAccount).filter_by(account_id=test_acc_id).delete()
    verify_session.query(Customer).filter_by(customer_id=test_cus_id).delete()
    verify_session.commit()
    verify_session.close()
