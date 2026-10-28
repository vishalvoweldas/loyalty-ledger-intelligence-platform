"""SQLAlchemy models for all core entities, supporting tables, and ground truth."""
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Text, CheckConstraint, Index
)
from sqlalchemy.orm import relationship
from loyalty_ledger.db import Base

class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String(32), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False, unique=True, index=True)
    region = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False, default="ACTIVE")
    created_at = Column(DateTime, nullable=False)

    account = relationship("LoyaltyAccount", back_populates="customer", uselist=False)
    orders = relationship("Order", back_populates="customer")


class Tier(Base):
    __tablename__ = "tiers"

    tier_id = Column(String(32), primary_key=True)
    tier_name = Column(String(64), nullable=False, unique=True)
    min_qualifying_spend_minor = Column(Integer, nullable=False, default=0)
    spend_per_point_minor = Column(Integer, nullable=False)
    earning_rate_points = Column(Integer, nullable=False)
    effective_from = Column(DateTime, nullable=False)
    effective_to = Column(DateTime, nullable=True)
    status = Column(String(16), nullable=False, default="ACTIVE")


class Rule(Base):
    __tablename__ = "rules"

    rule_id = Column(String(32), primary_key=True)
    rule_type = Column(String(32), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    description = Column(String(255), nullable=False)
    parameters = Column(Text, nullable=False)  # JSON serialized
    effective_from = Column(DateTime, nullable=False)
    effective_to = Column(DateTime, nullable=True)
    status = Column(String(16), nullable=False, default="ACTIVE")


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    account_id = Column(String(32), primary_key=True, index=True)
    customer_id = Column(String(32), ForeignKey("customers.customer_id"), nullable=False, unique=True)
    current_tier_id = Column(String(32), ForeignKey("tiers.tier_id"), nullable=False)
    status = Column(String(16), nullable=False, default="ACTIVE")
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    cached_balance_points = Column(Integer, nullable=False, default=0)

    customer = relationship("Customer", back_populates="account")
    tier = relationship("Tier")
    transactions = relationship("PointsTransaction", back_populates="account")
    lots = relationship("PointLot", back_populates="account")
    redemptions = relationship("Redemption", back_populates="account")
    tier_history = relationship("AccountTierHistory", back_populates="account")


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(32), primary_key=True, index=True)
    customer_id = Column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    order_date = Column(DateTime, nullable=False, index=True)
    status = Column(String(24), nullable=False, default="COMPLETED")
    currency = Column(String(3), nullable=False, default="INR")
    subtotal_minor = Column(Integer, nullable=False, default=0)
    discount_minor = Column(Integer, nullable=False, default=0)
    tax_minor = Column(Integer, nullable=False, default=0)
    shipping_minor = Column(Integer, nullable=False, default=0)
    net_merchandise_minor = Column(Integer, nullable=False, default=0)
    total_minor = Column(Integer, nullable=False, default=0)

    customer = relationship("Customer", back_populates="orders")
    lines = relationship("OrderLine", back_populates="order", cascade="all, delete-orphan")
    returns = relationship("OrderReturn", back_populates="order")


class OrderLine(Base):
    __tablename__ = "order_lines"

    order_line_id = Column(String(48), primary_key=True)
    order_id = Column(String(32), ForeignKey("orders.order_id"), nullable=False, index=True)
    sku = Column(String(32), nullable=False)
    category = Column(String(32), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price_minor = Column(Integer, nullable=False)
    discount_minor = Column(Integer, nullable=False, default=0)
    eligible_spend_minor = Column(Integer, nullable=False, default=0)
    returned_quantity = Column(Integer, nullable=False, default=0)

    order = relationship("Order", back_populates="lines")


class PointsTransaction(Base):
    __tablename__ = "points_transactions"

    transaction_id = Column(String(32), primary_key=True, index=True)
    account_id = Column(String(32), ForeignKey("loyalty_accounts.account_id"), nullable=False, index=True)
    transaction_type = Column(String(24), nullable=False, index=True)
    points_delta = Column(Integer, nullable=False)
    event_at = Column(DateTime, nullable=False, index=True)
    effective_at = Column(DateTime, nullable=False)
    source_type = Column(String(32), nullable=False)
    source_id = Column(String(64), nullable=False, index=True)
    original_transaction_id = Column(String(32), ForeignKey("points_transactions.transaction_id"), nullable=True)
    rule_id = Column(String(32), ForeignKey("rules.rule_id"), nullable=True)
    status = Column(String(16), nullable=False, default="POSTED")
    idempotency_key = Column(String(64), nullable=False, unique=True, index=True)
    reason_code = Column(String(32), nullable=False)
    correlation_id = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False)

    account = relationship("LoyaltyAccount", back_populates="transactions")
    allocations = relationship("TransactionLotAllocation", back_populates="transaction")


class Reward(Base):
    __tablename__ = "rewards"

    reward_id = Column(String(32), primary_key=True)
    reward_name = Column(String(128), nullable=False)
    points_cost = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="ACTIVE")
    effective_from = Column(DateTime, nullable=False)
    effective_to = Column(DateTime, nullable=True)
    inventory_quantity = Column(Integer, nullable=True)


class Redemption(Base):
    __tablename__ = "redemptions"

    redemption_id = Column(String(32), primary_key=True, index=True)
    account_id = Column(String(32), ForeignKey("loyalty_accounts.account_id"), nullable=False, index=True)
    reward_id = Column(String(32), ForeignKey("rewards.reward_id"), nullable=False)
    requested_points = Column(Integer, nullable=False)
    approved_points = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="PENDING")
    requested_at = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(128), nullable=True)
    idempotency_key = Column(String(64), nullable=False, unique=True, index=True)

    account = relationship("LoyaltyAccount", back_populates="redemptions")
    reward = relationship("Reward")


class ExpiryBatch(Base):
    __tablename__ = "expiry_batches"

    expiry_batch_id = Column(String(32), primary_key=True, index=True)
    run_at = Column(DateTime, nullable=False)
    cutoff_at = Column(DateTime, nullable=False)
    status = Column(String(16), nullable=False, default="COMPLETED")
    lots_scanned = Column(Integer, nullable=False, default=0)
    points_expired = Column(Integer, nullable=False, default=0)
    idempotency_key = Column(String(64), nullable=False, unique=True)


class PointLot(Base):
    __tablename__ = "point_lots"

    lot_id = Column(String(48), primary_key=True, index=True)
    account_id = Column(String(32), ForeignKey("loyalty_accounts.account_id"), nullable=False, index=True)
    source_transaction_id = Column(String(32), ForeignKey("points_transactions.transaction_id"), nullable=False, index=True)
    original_points = Column(Integer, nullable=False)
    remaining_points = Column(Integer, nullable=False)
    accrued_at = Column(DateTime, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(16), nullable=False, default="OPEN")  # OPEN, EXHAUSTED, EXPIRED, CLOSED
    rule_id = Column(String(32), ForeignKey("rules.rule_id"), nullable=True)

    account = relationship("LoyaltyAccount", back_populates="lots")
    allocations = relationship("TransactionLotAllocation", back_populates="lot")


class TransactionLotAllocation(Base):
    __tablename__ = "transaction_lot_allocations"

    allocation_id = Column(String(64), primary_key=True)
    transaction_id = Column(String(32), ForeignKey("points_transactions.transaction_id"), nullable=False, index=True)
    lot_id = Column(String(48), ForeignKey("point_lots.lot_id"), nullable=False, index=True)
    allocated_points = Column(Integer, nullable=False)
    allocation_type = Column(String(24), nullable=False)  # REDEMPTION, REVERSAL, EXPIRY
    created_at = Column(DateTime, nullable=False)

    transaction = relationship("PointsTransaction", back_populates="allocations")
    lot = relationship("PointLot", back_populates="allocations")


class AccountTierHistory(Base):
    __tablename__ = "account_tier_history"

    history_id = Column(String(48), primary_key=True)
    account_id = Column(String(32), ForeignKey("loyalty_accounts.account_id"), nullable=False, index=True)
    tier_id = Column(String(32), ForeignKey("tiers.tier_id"), nullable=False)
    qualifying_spend_minor = Column(Integer, nullable=False, default=0)
    effective_from = Column(DateTime, nullable=False)
    effective_to = Column(DateTime, nullable=True)
    reason = Column(String(128), nullable=False)

    account = relationship("LoyaltyAccount", back_populates="tier_history")
    tier = relationship("Tier")


class OrderReturn(Base):
    __tablename__ = "order_returns"

    return_id = Column(String(48), primary_key=True)
    order_id = Column(String(32), ForeignKey("orders.order_id"), nullable=False, index=True)
    return_date = Column(DateTime, nullable=False)
    reason = Column(String(128), nullable=False)
    returned_eligible_spend_minor = Column(Integer, nullable=False, default=0)
    reversal_transaction_id = Column(String(32), ForeignKey("points_transactions.transaction_id"), nullable=True)

    order = relationship("Order", back_populates="returns")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    audit_id = Column(String(48), primary_key=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(String(64), nullable=False, index=True)
    action = Column(String(32), nullable=False)
    actor = Column(String(64), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    details = Column(Text, nullable=True)


class GroundTruthRecord(Base):
    """Isolated ground-truth table. Never joined or queried during normal detection."""
    __tablename__ = "ground_truth_records"

    anomaly_id = Column(String(32), primary_key=True)
    issue_type = Column(String(64), nullable=False, index=True)
    affected_entity = Column(String(32), nullable=False)
    affected_record_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(32), nullable=True)
    account_id = Column(String(32), nullable=True)
    expected_outcome = Column(String(255), nullable=False)
    severity = Column(String(16), nullable=False)
    explanation = Column(Text, nullable=False)
    expected_detector_result = Column(String(64), nullable=False)
    generation_seed = Column(Integer, nullable=False)
    scenario_id = Column(String(64), nullable=False)


class AccountRuleAssignment(Base):
    __tablename__ = "account_rule_assignments"

    assignment_id = Column(String(48), primary_key=True)
    account_id = Column(String(32), ForeignKey("loyalty_accounts.account_id"), nullable=False, index=True)
    rule_id = Column(String(32), ForeignKey("rules.rule_id"), nullable=False, index=True)
    assigned_at = Column(DateTime, nullable=False)
    status = Column(String(16), nullable=False, default="ACTIVE")

    account = relationship("LoyaltyAccount")
    rule = relationship("Rule")


class RedemptionAttempt(Base):
    __tablename__ = "redemption_attempts"

    attempt_id = Column(String(48), primary_key=True)
    account_id = Column(String(32), ForeignKey("loyalty_accounts.account_id"), nullable=False, index=True)
    reward_id = Column(String(32), ForeignKey("rewards.reward_id"), nullable=False)
    requested_points = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False)  # SUCCESS, REJECTED, FAILED
    rejection_reason = Column(String(128), nullable=True)
    attempted_at = Column(DateTime, nullable=False)
    idempotency_key = Column(String(64), nullable=True, index=True)

    account = relationship("LoyaltyAccount")
    reward = relationship("Reward")


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    run_id = Column(String(48), primary_key=True)
    seed = Column(Integer, nullable=False)
    scale = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="COMPLETED")
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    row_counts_json = Column(Text, nullable=False)
    manifest_checksum = Column(String(64), nullable=True)

