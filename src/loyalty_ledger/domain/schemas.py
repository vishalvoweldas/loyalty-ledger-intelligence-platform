"""Pydantic schemas for request/response serialization and domain validation."""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class CustomerBase(BaseModel):
    name: str
    email: str
    region: str
    status: str = "ACTIVE"

class CustomerCreate(CustomerBase):
    customer_id: str

class CustomerResponse(CustomerBase):
    customer_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LoyaltyAccountResponse(BaseModel):
    account_id: str
    customer_id: str
    current_tier_id: str
    status: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    cached_balance_points: int
    model_config = ConfigDict(from_attributes=True)


class TierResponse(BaseModel):
    tier_id: str
    tier_name: str
    min_qualifying_spend_minor: int
    spend_per_point_minor: int
    earning_rate_points: int
    effective_from: datetime
    effective_to: Optional[datetime] = None
    status: str
    model_config = ConfigDict(from_attributes=True)


class RuleResponse(BaseModel):
    rule_id: str
    rule_type: str
    version: int
    description: str
    parameters: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    status: str
    model_config = ConfigDict(from_attributes=True)


class OrderLineResponse(BaseModel):
    order_line_id: str
    order_id: str
    sku: str
    category: str
    quantity: int
    unit_price_minor: int
    discount_minor: int
    eligible_spend_minor: int
    returned_quantity: int
    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    order_date: datetime
    status: str
    currency: str
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    shipping_minor: int
    net_merchandise_minor: int
    total_minor: int
    lines: Optional[List[OrderLineResponse]] = None
    model_config = ConfigDict(from_attributes=True)


class PointsTransactionResponse(BaseModel):
    transaction_id: str
    account_id: str
    transaction_type: str
    points_delta: int
    event_at: datetime
    effective_at: datetime
    source_type: str
    source_id: str
    original_transaction_id: Optional[str] = None
    rule_id: Optional[str] = None
    status: str
    idempotency_key: str
    reason_code: str
    correlation_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RewardResponse(BaseModel):
    reward_id: str
    reward_name: str
    points_cost: int
    status: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    inventory_quantity: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class RedemptionRequest(BaseModel):
    account_id: str
    reward_id: str
    requested_points: int
    idempotency_key: str

class RedemptionResponse(BaseModel):
    redemption_id: str
    account_id: str
    reward_id: str
    requested_points: int
    approved_points: int
    status: str
    requested_at: datetime
    processed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    idempotency_key: str
    model_config = ConfigDict(from_attributes=True)


class ReturnLineItem(BaseModel):
    order_line_id: str
    quantity: int

class ReturnRequest(BaseModel):
    reason: str = "CUSTOMER_RETURN"
    returned_lines: List[ReturnLineItem]
    idempotency_key: str

class ExpiryBatchRequest(BaseModel):
    cutoff_at: datetime
    idempotency_key: str

class ExpiryBatchResponse(BaseModel):
    expiry_batch_id: str
    run_at: datetime
    cutoff_at: datetime
    status: str
    lots_scanned: int
    points_expired: int
    idempotency_key: str
    model_config = ConfigDict(from_attributes=True)


class ReconciliationReport(BaseModel):
    account_id: str
    cached_balance: int
    ledger_derived_balance: int
    is_reconciled: bool
    difference: int
    transaction_count: int


class DashboardSummary(BaseModel):
    total_customers: int
    total_orders: int
    total_points_transactions: int
    total_points_accrued: int
    total_points_redeemed: int
    total_points_reversed: int
    total_points_expired: int
    total_outstanding_points: int
    reconciliation_mismatches_count: int
    tier_distribution: Dict[str, int]
    anomalies_by_type: Dict[str, int]
    anomalies_by_severity: Dict[str, int]
    redemption_stats: Dict[str, int]
    is_cached: Optional[bool] = False
    cache_age_seconds: Optional[float] = 0.0


class AnomalyReportItem(BaseModel):
    anomaly_id: str
    issue_type: str
    affected_entity: str
    affected_record_id: str
    customer_id: Optional[str] = None
    account_id: Optional[str] = None
    expected_outcome: str
    severity: str
    explanation: str
    expected_detector_result: str
    generation_seed: int
    scenario_id: str
    detected_state: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ValidationFinding(BaseModel):
    validation_id: str
    check_number: int
    severity: str  # ERROR, WARNING, INFO
    entity: str
    record_id: Optional[str] = None
    issue_type: str
    expected_value: Optional[str] = None
    observed_value: Optional[str] = None
    passed: bool
    explanation: str
    supporting_transaction_ids: Optional[List[str]] = None
