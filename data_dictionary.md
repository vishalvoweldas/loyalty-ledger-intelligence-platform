# Data Dictionary: Loyalty Ledger Intelligence Platform

## Overview
This document specifies the schema, data types, nullability, constraints, validation rules, units, and lifecycle conventions for all entities in the Loyalty Ledger Intelligence Platform.

### Currency & Points Convention
- **Monetary Values**: Stored in **integer minor units** (paise for INR; e.g. ₹50.00 is stored as `5000`). This eliminates floating-point rounding errors.
- **Points**: Stored in **integer points**. Fractional points are rounded down (`floor`) per business policy.
- **Timestamps**: Stored in ISO 8601 UTC string format (e.g., `2026-03-15T10:30:00Z`).

---

## 1. Core Entities

### 1.1 Customer
Represents a synthetic shopper profile.
- **Table Name**: `customers`
- **ID Prefix**: `CUS-` (e.g., `CUS-000001`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `customer_id` | VARCHAR(32) | No | PK | `^CUS-\d{6}$` | Unique immutable customer identifier. | `CUS-000001` |
| `name` | VARCHAR(128) | No | None | Text | Synthetic customer full name. | `Aarav Sharma` |
| `email` | VARCHAR(128) | No | Unique | RFC 5322 email | Synthetic unique customer email address. | `aarav.sharma@example.com` |
| `region` | VARCHAR(32) | No | None | `NORTH`, `SOUTH`, `EAST`, `WEST`, `CENTRAL` | Geographical operating region. | `NORTH` |
| `status` | VARCHAR(16) | No | None | `ACTIVE`, `INACTIVE` | Customer account status. | `ACTIVE` |
| `created_at` | TIMESTAMP | No | None | ISO 8601 UTC | Creation timestamp on the simulation clock. | `2026-01-05T08:12:00Z` |

---

### 1.2 LoyaltyAccount
Represents a customer's loyalty membership holding points.
- **Table Name**: `loyalty_accounts`
- **ID Prefix**: `LOY-` (exact format: `LOY-CUS-000001`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `account_id` | VARCHAR(32) | No | PK | `^LOY-CUS-\d{6}$` | Unique immutable account identifier matching `LOY-<customer_id>`. | `LOY-CUS-000001` |
| `customer_id` | VARCHAR(32) | No | FK (`customers.customer_id`), Unique | Existing customer | 1:1 baseline link to the owning customer. | `CUS-000001` |
| `current_tier_id` | VARCHAR(32) | No | FK (`tiers.tier_id`) | Valid tier ID | The customer's current membership tier. | `TIER-BRONZE` |
| `status` | VARCHAR(16) | No | None | `ACTIVE`, `SUSPENDED`, `CLOSED` | Account operational status. | `ACTIVE` |
| `opened_at` | TIMESTAMP | No | None | ISO 8601 UTC | Account opening timestamp. | `2026-01-05T08:12:00Z` |
| `closed_at` | TIMESTAMP | Yes | None | ISO 8601 UTC | Timestamp when closed, if applicable. | `NULL` |
| `cached_balance_points` | INTEGER | No | None | Signed integer | Stored point balance for quick lookup (must reconcile to ledger). | `450` |

---

### 1.3 Tier
Defines membership levels and qualifying spend thresholds.
- **Table Name**: `tiers`
- **ID Prefix**: `TIER-` (e.g., `TIER-BRONZE`, `TIER-SILVER`, `TIER-GOLD`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `tier_id` | VARCHAR(32) | No | PK | Text ID | Unique tier identifier. | `TIER-SILVER` |
| `tier_name` | VARCHAR(64) | No | Unique | `Bronze`, `Silver`, `Gold`, etc. | Human-readable tier name. | `Silver` |
| `min_qualifying_spend_minor` | INTEGER | No | None | $\ge 0$ | Minimum qualifying net spend in paise required to qualify. | `1000000` (₹10,000) |
| `spend_per_point_minor` | INTEGER | No | None | $> 0$ | Spend in paise required to earn 1 point. | `5000` (₹50 = 2 pts/₹100) |
| `earning_rate_points` | INTEGER | No | None | $> 0$ | Points awarded per ₹100 eligible spend. | `2` |
| `effective_from` | TIMESTAMP | No | None | ISO 8601 UTC | Start of tier policy validity. | `2026-01-01T00:00:00Z` |
| `effective_to` | TIMESTAMP | Yes | None | ISO 8601 UTC | End of validity (NULL if current). | `NULL` |
| `status` | VARCHAR(16) | No | None | `ACTIVE`, `DEPRECATED` | Tier configuration status. | `ACTIVE` |

---

### 1.4 Rule
Versioned policy definitions for accruals, redemptions, expiry, and tiers.
- **Table Name**: `rules`
- **ID Prefix**: `RULE-` (e.g., `RULE-ACCRUAL-V1`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `rule_id` | VARCHAR(32) | No | PK | Text ID | Unique rule identifier. | `RULE-ACCRUAL-V1` |
| `rule_type` | VARCHAR(32) | No | None | `ACCRUAL`, `REDEMPTION`, `EXPIRY`, `TIER` | Category of business rule. | `ACCRUAL` |
| `version` | INTEGER | No | None | $\ge 1$ | Version number of the rule. | `1` |
| `description` | VARCHAR(255) | No | None | Text | Human-readable description. | `Standard merchandise accrual rule` |
| `parameters` | TEXT / JSON | No | None | Valid JSON string | Structured JSON configuration parameters. | `{"tax_eligible": false, "shipping_eligible": false}` |
| `effective_from` | TIMESTAMP | No | None | ISO 8601 UTC | Start timestamp for rule applicability. | `2026-01-01T00:00:00Z` |
| `effective_to` | TIMESTAMP | Yes | None | ISO 8601 UTC | End timestamp for rule applicability. | `NULL` |
| `status` | VARCHAR(16) | No | None | `ACTIVE`, `SUPERSEDED` | Status of the rule version. | `ACTIVE` |

---

### 1.5 Order
Represents customer purchases and financial aggregates.
- **Table Name**: `orders`
- **ID Prefix**: `ORD-` (e.g., `ORD-2026-000001`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `order_id` | VARCHAR(32) | No | PK | `^ORD-\d{4}-\d{6}$` | Unique immutable order identifier. | `ORD-2026-000001` |
| `customer_id` | VARCHAR(32) | No | FK (`customers.customer_id`) | Existing customer | Reference to the purchasing customer. | `CUS-000001` |
| `order_date` | TIMESTAMP | No | None | ISO 8601 UTC | Timestamp when the order was placed. | `2026-02-10T14:22:00Z` |
| `status` | VARCHAR(24) | No | None | `PENDING`, `COMPLETED`, `CANCELLED`, `PARTIALLY_RETURNED`, `RETURNED` | Order lifecycle status. | `COMPLETED` |
| `currency` | VARCHAR(3) | No | None | `INR` | ISO currency code. | `INR` |
| `subtotal_minor` | INTEGER | No | None | $\ge 0$ | Gross merchandise amount before discounts (paise). | `500000` (₹5,000) |
| `discount_minor` | INTEGER | No | None | $\ge 0$ | Total discount applied (paise). | `50000` (₹500) |
| `tax_minor` | INTEGER | No | None | $\ge 0$ | Tax charged (paise). | `40500` (₹405) |
| `shipping_minor` | INTEGER | No | None | $\ge 0$ | Shipping fees (paise). | `10000` (₹100) |
| `net_merchandise_minor`| INTEGER | No | None | $\ge 0$ | `subtotal_minor - discount_minor` (paise). | `450000` (₹4,500) |
| `total_minor` | INTEGER | No | None | $\ge 0$ | `net_merchandise_minor + tax_minor + shipping_minor` (paise). | `500500` (₹5,005) |

---

### 1.6 OrderLine
Individual line items within an order.
- **Table Name**: `order_lines`
- **ID Prefix**: `LINE-` (e.g., `LINE-ORD-2026-000001-01`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `order_line_id` | VARCHAR(48) | No | PK | Unique string | Unique order line identifier. | `LINE-ORD-2026-000001-01`|
| `order_id` | VARCHAR(32) | No | FK (`orders.order_id`) | Existing order | Reference to the parent order. | `ORD-2026-000001` |
| `sku` | VARCHAR(32) | No | None | Alphanumeric | Product Stock Keeping Unit. | `SKU-ELEC-0042` |
| `category` | VARCHAR(32) | No | None | `ELECTRONICS`, `APPAREL`, `HOME`, `BEAUTY`, `GROCERY` | Product category. | `ELECTRONICS` |
| `quantity` | INTEGER | No | None | $> 0$ | Quantity purchased. | `2` |
| `unit_price_minor` | INTEGER | No | None | $> 0$ | Unit price in paise. | `250000` (₹2,500) |
| `discount_minor` | INTEGER | No | None | $\ge 0$ | Allocated discount for this line (paise). | `50000` (₹500) |
| `eligible_spend_minor` | INTEGER | No | None | $\ge 0$ | Net spend eligible for loyalty accrual (`price * qty - discount`). | `450000` (₹4,500) |
| `returned_quantity` | INTEGER | No | None | $0 \le \text{ret} \le \text{qty}$ | Cumulative returned quantity for this line. | `0` |

---

### 1.7 PointsTransaction
Append-only immutable transaction ledger recording all point balance deltas.
- **Table Name**: `points_transactions`
- **ID Prefix**: `PTS-` (exact format: `PTS-2026-00000001`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `transaction_id` | VARCHAR(32) | No | PK | `^PTS-\d{4}-\d{8}$` | Unique immutable points transaction ID. | `PTS-2026-00000001` |
| `account_id` | VARCHAR(32) | No | FK (`loyalty_accounts.account_id`) | Existing account | Reference to the affected loyalty account. | `LOY-CUS-000001` |
| `transaction_type` | VARCHAR(24) | No | None | `ACCRUAL`, `REDEMPTION`, `REVERSAL`, `EXPIRY`, `ADJUSTMENT` | Movement category. | `ACCRUAL` |
| `points_delta` | INTEGER | No | None | Signed non-zero integer | Points added (+) or deducted (-). | `50` |
| `event_at` | TIMESTAMP | No | None | ISO 8601 UTC | Timestamp of the underlying business event. | `2026-02-10T14:22:00Z` |
| `effective_at` | TIMESTAMP | No | None | ISO 8601 UTC | Accounting effective timestamp. | `2026-02-10T14:22:00Z` |
| `source_type` | VARCHAR(32) | No | None | `ORDER`, `REDEMPTION`, `RETURN`, `EXPIRY_BATCH`, `MANUAL` | Entity type that triggered the movement. | `ORDER` |
| `source_id` | VARCHAR(64) | No | None | String ID | Identifier of the source entity. | `ORD-2026-000001` |
| `original_transaction_id`| VARCHAR(32) | Yes | Self-FK (`points_transactions.transaction_id`)| Valid transaction ID | Links reversals to original accruals. | `NULL` |
| `rule_id` | VARCHAR(32) | Yes | FK (`rules.rule_id`) | Valid rule ID | Applied rule at event date. | `RULE-ACCRUAL-V1` |
| `status` | VARCHAR(16) | No | None | `POSTED`, `PENDING`, `FAILED` | Transaction ledger posting status. | `POSTED` |
| `idempotency_key` | VARCHAR(64) | No | Unique | Unique hash or UUID | Idempotency key preventing duplicate processing. | `IDEMP-ORD-2026-000001-ACCR` |
| `reason_code` | VARCHAR(32) | No | None | `PURCHASE_ACCRUAL`, `REWARD_REDEMPTION`, `RETURN_REVERSAL`, `LOT_EXPIRY`, `CORRECTION` | Business reason code. | `PURCHASE_ACCRUAL` |
| `correlation_id` | VARCHAR(64) | No | None | UUID or prefix | Correlation tracking for operational flows. | `CORR-ORD-2026-000001` |
| `created_at` | TIMESTAMP | No | None | ISO 8601 UTC | System insertion timestamp. | `2026-02-10T14:22:01Z` |

---

### 1.8 Reward
Catalog of benefits available for points redemption.
- **Table Name**: `rewards`
- **ID Prefix**: `REW-` (e.g., `REW-VOUCHER-500`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `reward_id` | VARCHAR(32) | No | PK | Text ID | Unique reward identifier. | `REW-VOUCHER-500` |
| `reward_name` | VARCHAR(128) | No | None | Text | Human-readable title of the reward. | `₹500 Shopping Voucher` |
| `points_cost` | INTEGER | No | None | $> 0$ | Points required to redeem. | `250` |
| `status` | VARCHAR(16) | No | None | `ACTIVE`, `INACTIVE` | Availability status. | `ACTIVE` |
| `effective_from` | TIMESTAMP | No | None | ISO 8601 UTC | Start of reward validity. | `2026-01-01T00:00:00Z` |
| `effective_to` | TIMESTAMP | Yes | None | ISO 8601 UTC | Expiry of reward offering. | `NULL` |
| `inventory_quantity` | INTEGER | Yes | None | $\ge 0$ or NULL | Available stock (NULL = unlimited). | `NULL` |

---

### 1.9 Redemption
Records a customer's redemption attempt and its outcome.
- **Table Name**: `redemptions`
- **ID Prefix**: `RDM-` (e.g., `RDM-2026-000001`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `redemption_id` | VARCHAR(32) | No | PK | `^RDM-\d{4}-\d{6}$` | Unique redemption identifier. | `RDM-2026-000001` |
| `account_id` | VARCHAR(32) | No | FK (`loyalty_accounts.account_id`) | Existing account | Reference to the redeeming account. | `LOY-CUS-000001` |
| `reward_id` | VARCHAR(32) | No | FK (`rewards.reward_id`) | Existing reward | Reference to the selected reward. | `REW-VOUCHER-500` |
| `requested_points` | INTEGER | No | None | $> 0$ | Points requested by the customer. | `250` |
| `approved_points` | INTEGER | No | None | $\ge 0$ | Points actually deducted upon approval. | `250` |
| `status` | VARCHAR(16) | No | None | `APPROVED`, `REJECTED`, `PENDING`, `CANCELLED` | Outcome of redemption. | `APPROVED` |
| `requested_at` | TIMESTAMP | No | None | ISO 8601 UTC | Time redemption was requested. | `2026-04-12T16:00:00Z` |
| `processed_at` | TIMESTAMP | Yes | None | ISO 8601 UTC | Time redemption was processed. | `2026-04-12T16:00:01Z` |
| `rejection_reason` | VARCHAR(128) | Yes | None | Text | Reason for failure if rejected. | `NULL` |
| `idempotency_key` | VARCHAR(64) | No | Unique | Unique string | Client idempotency key. | `IDEMP-RDM-2026-000001` |

---

### 1.10 ExpiryBatch
Records batch execution of points expiration runs.
- **Table Name**: `expiry_batches`
- **ID Prefix**: `EXP-` (e.g., `EXP-2026-000001`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `expiry_batch_id` | VARCHAR(32) | No | PK | `^EXP-\d{4}-\d{6}$` | Unique expiry batch identifier. | `EXP-2026-000001` |
| `run_at` | TIMESTAMP | No | None | ISO 8601 UTC | Execution timestamp of the batch. | `2026-06-30T23:59:59Z` |
| `cutoff_at` | TIMESTAMP | No | None | ISO 8601 UTC | Points expiry cutoff timestamp. | `2026-06-30T23:59:59Z` |
| `status` | VARCHAR(16) | No | None | `COMPLETED`, `STARTED`, `FAILED` | Batch processing status. | `COMPLETED` |
| `lots_scanned` | INTEGER | No | None | $\ge 0$ | Count of point lots evaluated. | `1420` |
| `points_expired` | INTEGER | No | None | $\ge 0$ | Total points expired by this batch. | `8540` |
| `idempotency_key` | VARCHAR(64) | No | Unique | Unique string | Batch run idempotency identifier. | `IDEMP-EXP-2026-06-30` |

---

## 2. Supporting & Bridge Tables

### 2.1 PointLot
Tracks discrete point allocations created by accrual transactions.
- **Table Name**: `point_lots`
- **ID Prefix**: `LOT-` (e.g., `LOT-PTS-2026-00000001`)

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `lot_id` | VARCHAR(48) | No | PK | Unique string | Unique point lot identifier. | `LOT-PTS-2026-00000001` |
| `account_id` | VARCHAR(32) | No | FK (`loyalty_accounts.account_id`) | Existing account | Reference to account. | `LOY-CUS-000001` |
| `source_transaction_id` | VARCHAR(32) | No | FK (`points_transactions.transaction_id`) | Existing accrual | Originating accrual transaction. | `PTS-2026-00000001` |
| `original_points` | INTEGER | No | None | $> 0$ | Points originally awarded in this lot. | `50` |
| `remaining_points` | INTEGER | No | None | $0 \le \text{rem} \le \text{orig}$ | Unspent, unreversed, unexpired points. | `25` |
| `accrued_at` | TIMESTAMP | No | None | ISO 8601 UTC | Accrual event timestamp. | `2026-02-10T14:22:00Z` |
| `expires_at` | TIMESTAMP | No | None | ISO 8601 UTC | Lot expiry cutoff (default: +365 days). | `2027-02-10T23:59:59Z` |
| `status` | VARCHAR(16) | No | None | `OPEN`, `EXHAUSTED`, `EXPIRED`, `CLOSED` | Lifecycle status of the lot. | `OPEN` |
| `rule_id` | VARCHAR(32) | Yes | FK (`rules.rule_id`) | Valid rule ID | Applied rule reference. | `RULE-ACCRUAL-V1` |

---

### 2.2 TransactionLotAllocation
Binds redemptions, reversals, and expiry movements to specific point lots.
- **Table Name**: `transaction_lot_allocations`
- **ID Prefix**: `ALLOC-`

| Field Name | Type | Nullable | Primary/Foreign Key | Allowed Values / Enum | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `allocation_id` | VARCHAR(64) | No | PK | Unique string | Unique allocation identifier. | `ALLOC-PTS-2026-00000015-01` |
| `transaction_id` | VARCHAR(32) | No | FK (`points_transactions.transaction_id`)| Existing transaction | Deducting transaction ID. | `PTS-2026-00000015` |
| `lot_id` | VARCHAR(48) | No | FK (`point_lots.lot_id`) | Existing point lot | Target point lot being depleted. | `LOT-PTS-2026-00000001` |
| `allocated_points` | INTEGER | No | None | $> 0$ | Quantity of points drawn from this lot. | `25` |
| `allocation_type` | VARCHAR(24) | No | None | `REDEMPTION`, `REVERSAL`, `EXPIRY` | Purpose of allocation. | `REDEMPTION` |
| `created_at` | TIMESTAMP | No | None | ISO 8601 UTC | Allocation timestamp. | `2026-04-12T16:00:01Z` |

---

### 2.3 AccountTierHistory
Records historical tier transitions over time.
- **Table Name**: `account_tier_history`

| Field Name | Type | Nullable | Primary/Foreign Key | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `history_id` | VARCHAR(48) | No | PK | Unique transition history record ID. | `TH-LOY-CUS-000001-01` |
| `account_id` | VARCHAR(32) | No | FK (`loyalty_accounts.account_id`) | Affected loyalty account. | `LOY-CUS-000001` |
| `tier_id` | VARCHAR(32) | No | FK (`tiers.tier_id`) | Assigned tier. | `TIER-SILVER` |
| `qualifying_spend_minor` | INTEGER | No | None | Net qualifying spend over rolling 12m (paise). | `1250000` (₹12,500) |
| `effective_from` | TIMESTAMP | No | None | Start date of tier assignment. | `2026-03-01T00:00:00Z` |
| `effective_to` | TIMESTAMP | Yes | None | End date of tier assignment (or NULL). | `NULL` |
| `reason` | VARCHAR(128) | No | None | Explanation for the transition. | `UPGRADE_THRESHOLD_MET` |

---

### 2.4 OrderReturn
Tracks full or partial returns against original orders and links to reversals.
- **Table Name**: `order_returns`

| Field Name | Type | Nullable | Primary/Foreign Key | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `return_id` | VARCHAR(48) | No | PK | Unique return record ID. | `RET-ORD-2026-000001-01` |
| `order_id` | VARCHAR(32) | No | FK (`orders.order_id`) | Originating order. | `ORD-2026-000001` |
| `return_date` | TIMESTAMP | No | None | Date and time the return was processed. | `2026-02-25T11:00:00Z` |
| `reason` | VARCHAR(128) | No | None | Return reason. | `CUSTOMER_RETURN_PARTIAL` |
| `returned_eligible_spend_minor` | INTEGER | No | None | Amount of eligible spend returned (paise). | `225000` (₹2,250) |
| `reversal_transaction_id` | VARCHAR(32) | Yes | FK (`points_transactions.transaction_id`) | Created reversal points movement. | `PTS-2026-00000088` |

---

### 2.5 AuditEvent
Append-only operational audit log for alerts, manual reviews, and resolution events.
- **Table Name**: `audit_events`

| Field Name | Type | Nullable | Primary/Foreign Key | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `audit_id` | VARCHAR(48) | No | PK | Unique audit event identifier. | `AUD-2026-00000001` |
| `entity_type` | VARCHAR(32) | No | None | Target entity (e.g., `ANOMALY`, `ACCOUNT`). | `ANOMALY` |
| `entity_id` | VARCHAR(64) | No | None | Target record ID. | `AN-001-0001` |
| `action` | VARCHAR(32) | No | None | Action taken (`REVIEWED`, `RESOLVED`, `FLAGGED`). | `RESOLVED` |
| `actor` | VARCHAR(64) | No | None | User or synthetic operator taking action. | `ops_manager_01` |
| `timestamp` | TIMESTAMP | No | None | Event timestamp. | `2026-10-23T10:15:00Z` |
| `details` | TEXT / JSON | Yes | None | JSON details or reviewer notes. | `{"notes": "Ledger resynced"}` |

---

### 2.6 GroundTruthRecord (Evaluation Only)
Isolated ground truth table storing known injected anomaly instances. Not queried by detection engines.
- **Table Name**: `ground_truth_records`

| Field Name | Type | Nullable | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `anomaly_id` | VARCHAR(32) | No | Unique stable anomaly identifier. | `AN-001-0001` |
| `issue_type` | VARCHAR(64) | No | Class of anomaly (`AN-001`, `AN-002`, `AN-003`, `AN-004`, `AN-005`). | `AN-001` |
| `affected_entity` | VARCHAR(32) | No | Entity type (`LoyaltyAccount`, `Redemption`, etc.). | `LoyaltyAccount` |
| `affected_record_id` | VARCHAR(64) | No | Specific primary key of affected record. | `LOY-CUS-000042` |
| `customer_id` | VARCHAR(32) | Yes | Related customer ID. | `CUS-000042` |
| `account_id` | VARCHAR(32) | Yes | Related loyalty account ID. | `LOY-CUS-000042` |
| `expected_outcome` | VARCHAR(255) | No | Expected decision or detector observation. | `REJECT_OR_FLAG_MISMATCH` |
| `severity` | VARCHAR(16) | No | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`. | `HIGH` |
| `explanation` | TEXT | No | Human-readable explanation of business rule violated. | `Cached balance was tampered by +100 points.` |
| `expected_detector_result` | VARCHAR(64) | No | Expected detector flag. | `BALANCE_MISMATCH` |
| `generation_seed` | INTEGER | No | Seed used when injected. | `20261022` |
| `scenario_id` | VARCHAR(64) | No | Scenario tag. | `SCENARIO_BALANCE_TAMPER` |

---

### 2.7 AccountRuleAssignment
Bridge table tracking assigned rules to specific loyalty accounts and rule versions.
- **Table Name**: `account_rule_assignments`

| Field Name | Type | Nullable | Primary/Foreign Key | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `assignment_id` | VARCHAR(48) | No | PK | Unique assignment identifier. | `ARA-LOY-CUS-000001-01` |
| `account_id` | VARCHAR(32) | No | FK (`loyalty_accounts.account_id`) | Target loyalty account. | `LOY-CUS-000001` |
| `rule_id` | VARCHAR(32) | No | FK (`rules.rule_id`) | Assigned rule identifier. | `RULE-EARN-01` |
| `assigned_at` | TIMESTAMP | No | None | Timestamp of assignment. | `2026-01-05T08:12:00Z` |
| `status` | VARCHAR(16) | No | None | Assignment status (`ACTIVE`, `INACTIVE`). | `ACTIVE` |

---

### 2.8 RedemptionAttempt
Tracks all attempted redemption requests, including rejected and failed requests with reasons.
- **Table Name**: `redemption_attempts`

| Field Name | Type | Nullable | Primary/Foreign Key | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `attempt_id` | VARCHAR(48) | No | PK | Unique redemption attempt identifier. | `ATT-RDM-2026-000001` |
| `account_id` | VARCHAR(32) | No | FK (`loyalty_accounts.account_id`) | Attempting loyalty account. | `LOY-CUS-000001` |
| `reward_id` | VARCHAR(32) | No | FK (`rewards.reward_id`) | Requested reward voucher. | `REW-VOUCHER-100` |
| `requested_points` | INTEGER | No | None | Number of points requested for redemption. | `50` |
| `status` | VARCHAR(16) | No | None | Attempt status (`SUCCESS`, `REJECTED`, `FAILED`). | `REJECTED` |
| `rejection_reason` | VARCHAR(128) | Yes | None | Reason code if rejected. | `INSUFFICIENT_AVAILABLE_POINTS` |
| `attempted_at` | TIMESTAMP | No | None | Timestamp of redemption attempt. | `2026-03-01T14:20:00Z` |
| `idempotency_key` | VARCHAR(64) | Yes | None | Client request idempotency key. | `IDEMP-RDM-0001` |

---

### 2.9 GenerationRun
Tracks synthetic dataset generation runs, seeds, scales, row counts, and checksum manifests.
- **Table Name**: `generation_runs`

| Field Name | Type | Nullable | Primary/Foreign Key | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `run_id` | VARCHAR(48) | No | PK | Unique generation run identifier. | `GEN-RUN-20261022-01` |
| `seed` | INTEGER | No | None | Deterministic pseudo-random seed used. | `20261022` |
| `scale` | VARCHAR(16) | No | None | Target generation scale (`starter`, `full`, `custom`). | `full` |
| `status` | VARCHAR(16) | No | None | Generation status (`COMPLETED`, `FAILED`). | `COMPLETED` |
| `started_at` | TIMESTAMP | No | None | Generation start timestamp. | `2026-10-27T14:30:00Z` |
| `completed_at` | TIMESTAMP | Yes | None | Completion timestamp. | `2026-10-27T14:32:00Z` |
| `row_counts_json` | TEXT | No | None | JSON serialization of entity row counts. | `{"customers": 20000, "orders": 100000}` |
| `manifest_checksum` | VARCHAR(64) | Yes | None | Checksum of dataset manifest. | `a1b2c3d4...` |

