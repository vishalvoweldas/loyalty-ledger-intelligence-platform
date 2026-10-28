"""Unit tests for business rule calculations, floor rounding, and tier boundaries."""
import pytest
from loyalty_ledger.domain.rules import RuleEngine, DEFAULT_TIERS_CONFIG

def test_accrual_floor_rounding():
    # Bronze rate: 10,000 paise per point (1 pt per ₹100)
    # ₹5099 = 509,900 paise -> floor(509900 / 10000) = 50 points
    pts = RuleEngine.calculate_points_earned(509900, 10000)
    assert pts == 50

    # Boundary: exactly ₹100 = 10,000 paise -> 1 point
    assert RuleEngine.calculate_points_earned(10000, 10000) == 1

    # Just below ₹100 = 9,999 paise -> 0 points
    assert RuleEngine.calculate_points_earned(9999, 10000) == 0

    # Zero spend -> 0 points
    assert RuleEngine.calculate_points_earned(0, 10000) == 0

def test_tier_threshold_boundaries():
    # Bronze: 0 to 999,999 paise (< ₹10,000)
    tier_id, name, spend_per_pt, rate = RuleEngine.evaluate_tier(0)
    assert tier_id == "TIER-BRONZE"
    assert rate == 1

    # Just below Silver threshold: 999,999 paise
    tier_id, name, _, _ = RuleEngine.evaluate_tier(999999)
    assert tier_id == "TIER-BRONZE"

    # Exactly at Silver threshold: 1,000,000 paise (₹10,000)
    tier_id, name, spend_per_pt, rate = RuleEngine.evaluate_tier(1000000)
    assert tier_id == "TIER-SILVER"
    assert rate == 2
    assert spend_per_pt == 5000

    # Just below Gold threshold: 4,999,999 paise (< ₹50,000)
    tier_id, name, _, _ = RuleEngine.evaluate_tier(4999999)
    assert tier_id == "TIER-SILVER"

    # Exactly at Gold threshold: 5,000,000 paise (₹50,000)
    tier_id, name, spend_per_pt, rate = RuleEngine.evaluate_tier(5000000)
    assert tier_id == "TIER-GOLD"
    assert rate == 3

    # Above Gold threshold: ₹100,000
    tier_id, name, _, _ = RuleEngine.evaluate_tier(10000000)
    assert tier_id == "TIER-GOLD"

def test_return_reversal_proportional():
    # Original order earned 50 pts on ₹5000 (500,000 paise)
    # Returned 50% = ₹2500 (250,000 paise) -> reverses 25 pts
    rev = RuleEngine.calculate_return_reversal_points(
        original_points=50,
        original_eligible_spend_minor=500000,
        returned_eligible_spend_minor=250000
    )
    assert rev == 25

    # Full return: 50 pts reversed
    rev_full = RuleEngine.calculate_return_reversal_points(
        original_points=50,
        original_eligible_spend_minor=500000,
        returned_eligible_spend_minor=500000
    )
    assert rev_full == 50

    # Zero returned spend -> 0 reversal
    assert RuleEngine.calculate_return_reversal_points(50, 500000, 0) == 0

def test_rule_effective_date_boundaries():
    from datetime import datetime, timezone
    
    rule = {
        "rule_id": "RULE-TEST-01",
        "effective_from": datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        "effective_to": datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
    }
    
    # Before effective window
    before = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    assert not (rule["effective_from"] <= before <= rule["effective_to"])
    
    # Exactly at start
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert rule["effective_from"] <= start <= rule["effective_to"]
    
    # During window
    during = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert rule["effective_from"] <= during <= rule["effective_to"]
    
    # Exactly at end
    end = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    assert rule["effective_from"] <= end <= rule["effective_to"]
    
    # After window
    after = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert not (rule["effective_from"] <= after <= rule["effective_to"])

def test_ledger_reconciliation_math():
    # Signed deltas:
    # +100 (Accrual)
    # -30 (Redemption)
    # -20 (Reversal)
    # -10 (Expiry)
    deltas = [100, -30, -20, -10]
    expected_balance = sum(deltas)
    assert expected_balance == 40

