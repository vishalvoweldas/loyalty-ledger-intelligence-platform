"""Configurable business rule engine for accrual, redemption, reversal, expiry, and tiers."""
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

DEFAULT_TIERS_CONFIG = [
    {
        "tier_id": "TIER-BRONZE",
        "tier_name": "Bronze",
        "min_qualifying_spend_minor": 0,          # INR 0
        "spend_per_point_minor": 10000,           # 1 pt per INR 100 (10,000 paise)
        "earning_rate_points": 1,
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "status": "ACTIVE"
    },
    {
        "tier_id": "TIER-SILVER",
        "tier_name": "Silver",
        "min_qualifying_spend_minor": 1000000,    # INR 10,000 (1,000,000 paise)
        "spend_per_point_minor": 5000,            # 2 pts per INR 100 (5,000 paise)
        "earning_rate_points": 2,
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "status": "ACTIVE"
    },
    {
        "tier_id": "TIER-GOLD",
        "tier_name": "Gold",
        "min_qualifying_spend_minor": 5000000,    # INR 50,000 (5,000,000 paise)
        "spend_per_point_minor": 3333,            # 3 pts per INR 100 (~3,333 paise per pt)
        "earning_rate_points": 3,
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "status": "ACTIVE"
    }
]

DEFAULT_RULES_CONFIG = [
    {
        "rule_id": "RULE-ACCRUAL-V1",
        "rule_type": "ACCRUAL",
        "version": 1,
        "description": "Standard merchandise spend accrual rule",
        "parameters": json.dumps({
            "tax_eligible": False,
            "shipping_eligible": False,
            "discount_treatment": "PROPORTIONAL",
            "rounding_mode": "FLOOR",
            "cancelled_orders_earn": False
        }),
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "status": "ACTIVE"
    },
    {
        "rule_id": "RULE-REDEMPTION-V1",
        "rule_type": "REDEMPTION",
        "version": 1,
        "description": "Earliest-expiry-first redemption policy",
        "parameters": json.dumps({
            "depletion_strategy": "EARLIEST_EXPIRY_FIRST",
            "all_or_nothing": True
        }),
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "status": "ACTIVE"
    },
    {
        "rule_id": "RULE-REVERSAL-V1",
        "rule_type": "REVERSAL",
        "version": 1,
        "description": "Proportional accrual reversal on return",
        "parameters": json.dumps({
            "reversal_basis": "ORIGINAL_PROPORTIONAL",
            "allow_negative_balance": True
        }),
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "status": "ACTIVE"
    },
    {
        "rule_id": "RULE-EXPIRY-V1",
        "rule_type": "EXPIRY",
        "version": 1,
        "description": "365-day point lot validity rule",
        "parameters": json.dumps({
            "validity_days": 365,
            "end_of_day_convention": True
        }),
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "status": "ACTIVE"
    },
    {
        "rule_id": "RULE-TIER-V1",
        "rule_type": "TIER",
        "version": 1,
        "description": "Rolling 12-month net qualifying merchandise spend",
        "parameters": json.dumps({
            "rolling_window_days": 365,
            "tax_eligible": False,
            "shipping_eligible": False,
            "deduct_returns": True
        }),
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "status": "ACTIVE"
    }
]

DEFAULT_REWARDS_CONFIG = [
    {
        "reward_id": "REW-VOUCHER-100",
        "reward_name": "₹100 Shopping Voucher",
        "points_cost": 50,
        "status": "ACTIVE",
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "inventory_quantity": None
    },
    {
        "reward_id": "REW-VOUCHER-250",
        "reward_name": "₹250 Shopping Voucher",
        "points_cost": 125,
        "status": "ACTIVE",
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "inventory_quantity": None
    },
    {
        "reward_id": "REW-VOUCHER-500",
        "reward_name": "₹500 Shopping Voucher",
        "points_cost": 250,
        "status": "ACTIVE",
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "inventory_quantity": None
    },
    {
        "reward_id": "REW-VOUCHER-1000",
        "reward_name": "₹1,000 Shopping Voucher",
        "points_cost": 500,
        "status": "ACTIVE",
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
        "inventory_quantity": None
    }
]


class RuleEngine:
    """Evaluates configurable business rules."""

    @staticmethod
    def calculate_eligible_line_spend(
        unit_price_minor: int,
        quantity: int,
        discount_minor: int = 0
    ) -> int:
        """Calculates eligible spend for an order line."""
        gross = unit_price_minor * quantity
        net = max(0, gross - discount_minor)
        return net

    @staticmethod
    def calculate_points_earned(
        eligible_spend_minor: int,
        spend_per_point_minor: int
    ) -> int:
        """Calculates earned points using floor division."""
        if spend_per_point_minor <= 0 or eligible_spend_minor <= 0:
            return 0
        return eligible_spend_minor // spend_per_point_minor

    @staticmethod
    def evaluate_tier(
        qualifying_spend_minor: int,
        tiers_list: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, str, int, int]:
        """
        Determines the highest qualifying tier for a given net spend.
        Returns: (tier_id, tier_name, spend_per_point_minor, earning_rate_points)
        """
        tiers = tiers_list or DEFAULT_TIERS_CONFIG
        # Sort descending by min qualifying spend
        sorted_tiers = sorted(
            tiers,
            key=lambda t: t["min_qualifying_spend_minor"],
            reverse=True
        )
        for t in sorted_tiers:
            if qualifying_spend_minor >= t["min_qualifying_spend_minor"]:
                return (
                    t["tier_id"],
                    t["tier_name"],
                    t["spend_per_point_minor"],
                    t["earning_rate_points"]
                )
        # Fallback to lowest tier
        lowest = sorted_tiers[-1]
        return (
            lowest["tier_id"],
            lowest["tier_name"],
            lowest["spend_per_point_minor"],
            lowest["earning_rate_points"]
        )

    @staticmethod
    def calculate_return_reversal_points(
        original_points: int,
        original_eligible_spend_minor: int,
        returned_eligible_spend_minor: int
    ) -> int:
        """Calculates reversal points proportional to original eligible spend."""
        if original_eligible_spend_minor <= 0 or original_points <= 0 or returned_eligible_spend_minor <= 0:
            return 0
        # If full return or greater
        if returned_eligible_spend_minor >= original_eligible_spend_minor:
            return original_points
        # Proportional calculation with floor rounding
        ratio = returned_eligible_spend_minor / original_eligible_spend_minor
        reversal = math.floor(original_points * ratio)
        return min(original_points, max(0, reversal))
