"""Integration tests for ledger movements, services, concurrency, and reconciliation."""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loyalty_ledger.db import Base, _sqlite_on_connect
from loyalty_ledger.domain.models import (
    Customer, LoyaltyAccount, Tier, Reward, Order, OrderLine, PointsTransaction, PointLot
)
from loyalty_ledger.services.accrual_service import AccrualService
from loyalty_ledger.services.redemption_service import RedemptionService
from loyalty_ledger.services.returns_service import ReturnsService
from loyalty_ledger.services.expiry_service import ExpiryService
from loyalty_ledger.ledger.ledger import LedgerService

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine)
    session = SessionFactory()

    # Seed initial tier and reward
    tier = Tier(
        tier_id="TIER-BRONZE",
        tier_name="Bronze",
        min_qualifying_spend_minor=0,
        spend_per_point_minor=10000,
        earning_rate_points=1,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="ACTIVE"
    )
    session.add(tier)

    reward = Reward(
        reward_id="REW-VOUCHER-100",
        reward_name="₹100 Voucher",
        points_cost=50,
        status="ACTIVE",
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    session.add(reward)

    cus = Customer(
        customer_id="CUS-999001",
        name="Test Shopper",
        email="shopper@test.com",
        region="NORTH",
        status="ACTIVE",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    session.add(cus)

    acc = LoyaltyAccount(
        account_id="LOY-CUS-999001",
        customer_id=cus.customer_id,
        current_tier_id="TIER-BRONZE",
        status="ACTIVE",
        opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        cached_balance_points=0
    )
    session.add(acc)
    session.commit()

    yield session
    session.close()

def test_accrual_and_idempotency(test_db):
    accrual_svc = AccrualService(test_db)
    ord_id = "ORD-2026-999001"
    ord_date = datetime(2026, 2, 1, tzinfo=timezone.utc)

    order = Order(
        order_id=ord_id,
        customer_id="CUS-999001",
        order_date=ord_date,
        status="COMPLETED",
        subtotal_minor=500000,   # ₹5,000
        discount_minor=0,
        tax_minor=45000,
        shipping_minor=0,
        net_merchandise_minor=500000,
        total_minor=545000
    )
    line = OrderLine(
        order_line_id=f"LINE-{ord_id}-01",
        order_id=ord_id,
        sku="SKU-TEST-01",
        category="ELECTRONICS",
        quantity=1,
        unit_price_minor=500000,
        discount_minor=0,
        eligible_spend_minor=500000
    )
    test_db.add(order)
    test_db.add(line)
    test_db.commit()

    # First accrual: ₹5,000 / ₹100 = 50 pts
    tx = accrual_svc.accrue_points_for_order(ord_id, transaction_id="PTS-2026-00000001")
    assert tx is not None
    assert tx.points_delta == 50

    # Verify cached balance updated
    acc = test_db.query(LoyaltyAccount).filter_by(account_id="LOY-CUS-999001").first()
    assert acc.cached_balance_points == 50

    # Idempotent re-run: returns identical transaction without extra points
    tx2 = accrual_svc.accrue_points_for_order(ord_id)
    assert tx2.transaction_id == tx.transaction_id
    assert acc.cached_balance_points == 50

def test_redemption_insufficient_vs_success(test_db):
    accrual_svc = AccrualService(test_db)
    rdm_svc = RedemptionService(test_db)

    # Order giving 100 points
    ord_id = "ORD-2026-999002"
    order = Order(
        order_id=ord_id,
        customer_id="CUS-999001",
        order_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        status="COMPLETED",
        subtotal_minor=1000000,
        discount_minor=0,
        tax_minor=0,
        shipping_minor=0,
        net_merchandise_minor=1000000,
        total_minor=1000000
    )
    line = OrderLine(
        order_line_id=f"LINE-{ord_id}-01",
        order_id=ord_id,
        sku="SKU-TEST-02",
        category="HOME",
        quantity=1,
        unit_price_minor=1000000,
        eligible_spend_minor=1000000
    )
    test_db.add(order)
    test_db.add(line)
    test_db.commit()
    accrual_svc.accrue_points_for_order(ord_id, transaction_id="PTS-2026-00000002")

    # 1. Attempt redeeming 150 points (exceeds balance of 100) -> Rejected
    rdm_fail = rdm_svc.process_redemption(
        account_id="LOY-CUS-999001",
        reward_id="REW-VOUCHER-100",
        requested_points=150,
        idempotency_key="IDEMP-RDM-FAIL-01",
        requested_at=datetime(2026, 2, 5, tzinfo=timezone.utc)
    )
    assert rdm_fail.status == "REJECTED"
    assert rdm_fail.approved_points == 0
    assert rdm_fail.rejection_reason == "INSUFFICIENT_AVAILABLE_POINTS"

    # 2. Redeem exactly 100 points -> Approved
    rdm_ok = rdm_svc.process_redemption(
        account_id="LOY-CUS-999001",
        reward_id="REW-VOUCHER-100",
        requested_points=100,
        idempotency_key="IDEMP-RDM-OK-01",
        transaction_id="PTS-2026-00000003",
        requested_at=datetime(2026, 2, 6, tzinfo=timezone.utc)
    )
    assert rdm_ok.status == "APPROVED"
    assert rdm_ok.approved_points == 100

    # Verify balance is now 0
    ledger = LedgerService(test_db)
    assert ledger.get_ledger_balance("LOY-CUS-999001") == 0

def test_expiry_batch_idempotency(test_db):
    accrual_svc = AccrualService(test_db)
    expiry_svc = ExpiryService(test_db)

    # Order giving 50 points
    ord_id = "ORD-2026-999003"
    order = Order(
        order_id=ord_id,
        customer_id="CUS-999001",
        order_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="COMPLETED",
        subtotal_minor=500000,
        net_merchandise_minor=500000,
        total_minor=500000
    )
    line = OrderLine(
        order_line_id=f"LINE-{ord_id}-01",
        order_id=ord_id,
        sku="SKU-EXP-01",
        category="BEAUTY",
        quantity=1,
        unit_price_minor=500000,
        eligible_spend_minor=500000
    )
    test_db.add(order)
    test_db.add(line)
    test_db.commit()
    accrual_svc.accrue_points_for_order(ord_id, transaction_id="PTS-2026-00000004")

    # Cutoff after 366 days -> lot expires
    cutoff = datetime(2027, 1, 5, tzinfo=timezone.utc)
    batch1 = expiry_svc.run_expiry_batch(cutoff_at=cutoff, idempotency_key="EXP-BATCH-TEST-01")
    assert batch1.status == "COMPLETED"
    assert batch1.points_expired == 50

    # Re-run same batch -> idempotent, 0 extra deductions
    batch2 = expiry_svc.run_expiry_batch(cutoff_at=cutoff, idempotency_key="EXP-BATCH-TEST-01")
    assert batch2.expiry_batch_id == batch1.expiry_batch_id
    assert batch2.points_expired == 50

def test_order_eligibility_and_excluded_categories(test_db):
    accrual_svc = AccrualService(test_db)
    ord_id = "ORD-2026-999004"
    
    # Order with one eligible line (₹2,000) and one excluded GIFT_CARD line (₹3,000)
    order = Order(
        order_id=ord_id,
        customer_id="CUS-999001",
        order_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        status="COMPLETED",
        subtotal_minor=500000,
        net_merchandise_minor=500000,
        total_minor=500000
    )
    line1 = OrderLine(
        order_line_id=f"LINE-{ord_id}-01",
        order_id=ord_id,
        sku="SKU-PHONE",
        category="ELECTRONICS",
        quantity=1,
        unit_price_minor=200000,
        eligible_spend_minor=200000
    )
    line2 = OrderLine(
        order_line_id=f"LINE-{ord_id}-02",
        order_id=ord_id,
        sku="SKU-GIFTCARD",
        category="GIFT_CARD",
        quantity=1,
        unit_price_minor=300000,
        eligible_spend_minor=0  # Excluded category
    )
    test_db.add(order)
    test_db.add(line1)
    test_db.add(line2)
    test_db.commit()

    # Points earned only on eligible spend ₹2,000 (200,000 paise) = 20 points
    tx = accrual_svc.accrue_points_for_order(ord_id)
    assert tx.points_delta == 20

def test_full_and_partial_returns_with_reversal_references(test_db):
    accrual_svc = AccrualService(test_db)
    returns_svc = ReturnsService(test_db)
    
    ord_id = "ORD-2026-999005"
    order = Order(
        order_id=ord_id,
        customer_id="CUS-999001",
        order_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        status="COMPLETED",
        subtotal_minor=1000000,
        net_merchandise_minor=1000000,
        total_minor=1000000
    )
    line = OrderLine(
        order_line_id=f"LINE-{ord_id}-01",
        order_id=ord_id,
        sku="SKU-CHAIR",
        category="FURNITURE",
        quantity=4,
        unit_price_minor=250000,
        eligible_spend_minor=1000000
    )
    test_db.add(order)
    test_db.add(line)
    test_db.commit()

    # Accrue 100 points
    tx = accrual_svc.accrue_points_for_order(ord_id)
    assert tx.points_delta == 100

    # 1. Partial return: return 1 of 4 chairs (25% = 25 points reversed)
    ret1 = returns_svc.process_order_return(
        order_id=ord_id,
        returned_lines=[{"order_line_id": f"LINE-{ord_id}-01", "quantity": 1}],
        reason="COLOR_MISMATCH"
    )
    assert ret1.reversal_transaction_id is not None
    rev_tx1 = test_db.query(PointsTransaction).filter_by(transaction_id=ret1.reversal_transaction_id).first()
    assert rev_tx1.points_delta == -25
    assert rev_tx1.original_transaction_id == tx.transaction_id
    assert order.status == "PARTIALLY_RETURNED"

    # 2. Exceeding return quantity raises ValueError
    with pytest.raises(ValueError, match="exceeds ordered quantity"):
        returns_svc.process_order_return(
            order_id=ord_id,
            returned_lines=[{"order_line_id": f"LINE-{ord_id}-01", "quantity": 5}]
        )

    # 3. Return remaining 3 chairs (75 points reversed) -> Full return
    ret2 = returns_svc.process_order_return(
        order_id=ord_id,
        returned_lines=[{"order_line_id": f"LINE-{ord_id}-01", "quantity": 3}],
        reason="RETURN_REMAINING"
    )
    rev_tx2 = test_db.query(PointsTransaction).filter_by(transaction_id=ret2.reversal_transaction_id).first()
    assert rev_tx2.points_delta == -75
    assert order.status == "RETURNED"

def test_competing_redemptions_against_same_account(test_db):
    accrual_svc = AccrualService(test_db)
    rdm_svc = RedemptionService(test_db)
    
    # Give account exactly 50 points
    ord_id = "ORD-2026-999006"
    order = Order(
        order_id=ord_id,
        customer_id="CUS-999001",
        order_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        status="COMPLETED",
        subtotal_minor=500000,
        net_merchandise_minor=500000,
        total_minor=500000
    )
    line = OrderLine(
        order_line_id=f"LINE-{ord_id}-01",
        order_id=ord_id,
        sku="SKU-COMPETE-01",
        category="BOOKS",
        quantity=1,
        unit_price_minor=500000,
        eligible_spend_minor=500000
    )
    test_db.add(order)
    test_db.add(line)
    test_db.commit()
    accrual_svc.accrue_points_for_order(ord_id)

    # First request: requests 50 points -> APPROVED
    rdm1 = rdm_svc.process_redemption(
        account_id="LOY-CUS-999001",
        reward_id="REW-VOUCHER-100",
        requested_points=50,
        idempotency_key="IDEMP-COMPETE-01"
    )
    assert rdm1.status == "APPROVED"

    # Competing request immediately after: requests 50 points -> REJECTED
    rdm2 = rdm_svc.process_redemption(
        account_id="LOY-CUS-999001",
        reward_id="REW-VOUCHER-100",
        requested_points=50,
        idempotency_key="IDEMP-COMPETE-02"
    )
    assert rdm2.status == "REJECTED"
    assert rdm2.rejection_reason == "INSUFFICIENT_AVAILABLE_POINTS"

def test_concurrent_redemption_and_expiry_lot_safety(test_db):
    accrual_svc = AccrualService(test_db)
    rdm_svc = RedemptionService(test_db)
    expiry_svc = ExpiryService(test_db)

    # Order accrued points
    ord_id = "ORD-2026-999007"
    order = Order(
        order_id=ord_id,
        customer_id="CUS-999001",
        order_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="COMPLETED",
        subtotal_minor=500000,
        net_merchandise_minor=500000,
        total_minor=500000
    )
    line = OrderLine(
        order_line_id=f"LINE-{ord_id}-01",
        order_id=ord_id,
        sku="SKU-EXP-SAFE",
        category="CLOTHING",
        quantity=1,
        unit_price_minor=500000,
        eligible_spend_minor=500000
    )
    test_db.add(order)
    test_db.add(line)
    test_db.commit()
    tx = accrual_svc.accrue_points_for_order(ord_id)

    # Redeem all 50 points first
    rdm = rdm_svc.process_redemption(
        account_id="LOY-CUS-999001",
        reward_id="REW-VOUCHER-100",
        requested_points=50,
        idempotency_key="IDEMP-RDM-EXPSAFE"
    )
    assert rdm.status == "APPROVED"

    # Now run expiry batch for date past expiration:
    # Because points were already redeemed, remaining_points == 0 -> Expiry cannot expire them again!
    cutoff = datetime(2027, 2, 1, tzinfo=timezone.utc)
    batch = expiry_svc.run_expiry_batch(cutoff_at=cutoff, idempotency_key="EXP-BATCH-SAFE-01")
    # This lot should NOT be expired again
    lot = test_db.query(PointLot).filter_by(source_transaction_id=tx.transaction_id).first()
    assert lot is not None
    assert lot.remaining_points == 0

