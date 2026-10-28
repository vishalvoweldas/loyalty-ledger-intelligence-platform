# REST API Documentation

The Loyalty Ledger Intelligence Platform exposes a versioned REST API at `/api/v1`. Interactive Swagger/OpenAPI documentation is served at `/docs` and `/redoc`.

## 1. System & Health Endpoints

### `GET /api/v1/health`
Checks backend and database connectivity.
- **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "timestamp": "2026-10-26T14:30:00Z",
    "database": "connected",
    "version": "1.0.0"
  }
  ```

### `GET /api/v1/dashboard/summary`
Retrieves aggregated statistics for the executive dashboard.
- **Response `200 OK`**:
  ```json
  {
    "total_customers": 20000,
    "total_orders": 100000,
    "total_points_transactions": 300000,
    "total_points_accrued": 2540000,
    "total_points_redeemed": 820000,
    "total_points_reversed": 45000,
    "total_points_expired": 120000,
    "total_outstanding_points": 1555000,
    "reconciliation_mismatches_count": 0,
    "tier_distribution": {
      "Bronze": 14200,
      "Silver": 4300,
      "Gold": 1500
    },
    "anomalies_by_type": {
      "AN-001": 2,
      "AN-002": 2,
      "AN-003": 2,
      "AN-004": 2,
      "AN-005": 2
    }
  }
  ```

---

## 2. Customers & Accounts

### `GET /api/v1/customers`
Paginated search of customers.
- **Query Params**: `page` (default: 1), `page_size` (default: 50), `search` (name or email), `region`.
- **Response `200 OK`**: List of customer profiles.

### `GET /api/v1/customers/{customer_id}`
Detailed customer profile including account ID.

### `GET /api/v1/accounts/{account_id}`
Detailed account status, current tier, cached balance, and open point lots.

### `GET /api/v1/accounts/{account_id}/ledger`
Chronological transaction history for the specified loyalty account.
- **Query Params**: `transaction_type`, `from_date`, `to_date`, `page`, `page_size`.

### `GET /api/v1/accounts/{account_id}/reconciliation`
On-demand reconciliation check computing $\sum \Delta P$ vs `cached_balance_points`.
- **Response `200 OK`**:
  ```json
  {
    "account_id": "LOY-CUS-000001",
    "cached_balance": 450,
    "ledger_derived_balance": 450,
    "is_reconciled": true,
    "difference": 0,
    "transaction_count": 8
  }
  ```

---

## 3. Orders & Lifecycle Workflows

### `GET /api/v1/orders`
Paginated list of orders with status, customer, subtotal, discounts, and total.

### `GET /api/v1/orders/{order_id}`
Order details with individual order lines and accrual/reversal links.

### `POST /api/v1/orders/{order_id}/accrue`
Manually or system-triggered accrual for an eligible order.
- **Headers**: `Idempotency-Key` (required).
- **Response `200 OK` / `201 Created`**: Returns created `PointsTransaction`.

### `POST /api/v1/orders/{order_id}/returns`
Processes a full or partial return and posts proportional reversals.
- **Request Body**:
  ```json
  {
    "reason": "CUSTOMER_RETURN_PARTIAL",
    "returned_lines": [
      { "order_line_id": "LINE-ORD-2026-000001-01", "quantity": 1 }
    ],
    "idempotency_key": "IDEMP-RET-ORD-2026-000001-01"
  }
  ```
- **Response `200 OK`**: Created `OrderReturn` and corresponding `PointsTransaction` of type `REVERSAL`.

---

## 4. Redemptions & Expiry

### `POST /api/v1/redemptions`
Submits a redemption request. Concurrency-safe and atomic.
- **Request Body**:
  ```json
  {
    "account_id": "LOY-CUS-000001",
    "reward_id": "REW-VOUCHER-500",
    "requested_points": 250,
    "idempotency_key": "IDEMP-RDM-2026-04-12-001"
  }
  ```
- **Response `200 OK`**:
  - If approved: status `APPROVED`, `PointsTransaction` generated.
  - If insufficient points: status `REJECTED`, `rejection_reason`: `INSUFFICIENT_AVAILABLE_POINTS`.

### `POST /api/v1/expiry-batches`
Executes an expiry run up to the given cutoff timestamp.
- **Request Body**:
  ```json
  {
    "cutoff_at": "2026-06-30T23:59:59Z",
    "idempotency_key": "IDEMP-EXP-2026-06-30"
  }
  ```

---

## 5. Tiers, Rules & Anomaly Review

### `GET /api/v1/tiers`
List configured tiers, spend thresholds, and earning rates.

### `GET /api/v1/rules`
List active and historical business rules.

### `GET /api/v1/anomalies`
Search anomaly review queue with filters: `issue_type`, `severity`, `review_status`.

### `GET /api/v1/anomalies/{anomaly_id}`
Detailed anomaly investigation report showing affected record, expected value, observed value, and supporting evidence.

### `POST /api/v1/anomalies/{anomaly_id}/review`
Post an operational review or resolution note, appending to the immutable `AuditEvent` log.

---

## 6. Datasets, Validation & Reproducibility

### `POST /api/v1/datasets/generate`
Generates synthetic data with parameters: `scale` (`starter` | `full`), `seed` (default `20261022`), `inject_anomalies` (`true` | `false`).

### `POST /api/v1/validation/run`
Executes the 20-check validation engine and returns findings.

### `POST /api/v1/reproducibility/verify`
Runs two identical generations, computes SHA-256 hashes for all exported tables, and reports any variance.

### `POST /api/v1/datasets/export`
Exports dataset to CSV, JSON, and SQL formats.
