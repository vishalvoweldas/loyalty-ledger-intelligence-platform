-- Loyalty Ledger Intelligence Platform Schema (ANSI SQL Reference Export)
CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    email VARCHAR(128) NOT NULL UNIQUE,
    region VARCHAR(32) NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS tiers (
    tier_id VARCHAR(32) PRIMARY KEY,
    tier_name VARCHAR(64) NOT NULL UNIQUE,
    min_qualifying_spend_minor INTEGER NOT NULL,
    spend_per_point_minor INTEGER NOT NULL,
    earning_rate_points INTEGER NOT NULL,
    effective_from TIMESTAMP NOT NULL,
    effective_to TIMESTAMP,
    status VARCHAR(16) NOT NULL
);

CREATE TABLE IF NOT EXISTS loyalty_accounts (
    account_id VARCHAR(32) PRIMARY KEY,
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    current_tier_id VARCHAR(32) NOT NULL REFERENCES tiers(tier_id),
    status VARCHAR(16) NOT NULL,
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    cached_balance_points INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS points_transactions (
    transaction_id VARCHAR(32) PRIMARY KEY,
    account_id VARCHAR(32) NOT NULL REFERENCES loyalty_accounts(account_id),
    transaction_type VARCHAR(24) NOT NULL,
    points_delta INTEGER NOT NULL,
    event_at TIMESTAMP NOT NULL,
    effective_at TIMESTAMP NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    original_transaction_id VARCHAR(32),
    rule_id VARCHAR(32),
    status VARCHAR(16) NOT NULL,
    idempotency_key VARCHAR(64) NOT NULL UNIQUE,
    reason_code VARCHAR(32) NOT NULL,
    correlation_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL
);
