# System Architecture: Loyalty Ledger Intelligence Platform

## 1. Architectural Philosophy
The Loyalty Ledger Intelligence Platform is structured as an enterprise-grade, append-only financial-style ledger for loyalty points. It cleanly separates:
1. Deterministic synthetic data generation
2. Immutable transaction recording
3. Lifecycle application domain services
4. Reconciliation and multi-factor validation
5. Independent anomaly detection and isolated ground-truth evaluation
6. Operational REST APIs and web visualization console

```
+-----------------------------------------------------------------------------------+
|                           Web Console (SPA / Dashboard)                           |
+-----------------------------------------------------------------------------------+
                                        | (HTTP / REST)
+-----------------------------------------------------------------------------------+
|                                 REST API Layer                                    |
|   /health, /dashboard, /customers, /accounts, /orders, /redemptions, /anomalies   |
+-----------------------------------------------------------------------------------+
       |                        |                              |
       v                        v                              v
+---------------+     +--------------------+       +----------------------+
|  Reconciliation|    | Lifecycle Services |       |  Anomaly Detection   |
|   & Validator |     | Accrual, Redeem,   |       |  Engine (Independent)|
|   (20 Checks) |     | Returns, Expiry    |       +----------------------+
+---------------+     +--------------------+                   |
       |                        |                              v
       |              +--------------------+       +----------------------+
       |              | Append-Only Ledger |       | Ground Truth Storage |
       |              | & Point-Lot Engine |       | (Isolated Baseline)  |
       |              +--------------------+       +----------------------+
       |                        |
+-----------------------------------------------------------------------------------+
|                        Relational Persistence Layer                               |
|              SQLite (WAL Mode, Strict FKs) / PostgreSQL Schema                    |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Architectural Layers

### Layer A: Synthetic Data Generator (`src/loyalty_ledger/generator/`)
- Deterministic random engine seeded by default with `20261022`.
- Topological generation sequence ensuring parent records exist before children:
  Tiers & Rules $\to$ Customers & Accounts $\to$ Orders & Order Lines $\to$ Accrual Transactions & Lots $\to$ Redemptions $\to$ Returns & Reversals $\to$ Expiry Batches.
- Scales: `starter` (e.g. 500 customers), `full` (exactly 20,000 customers, 100,000 orders, 300,000 points transactions), or custom.

### Layer B: Ledger & Point-Lot Core (`src/loyalty_ledger/ledger/`)
- Append-only transactional storage. No `UPDATE` or `DELETE` statements on `points_transactions`.
- Signed integer points delta: $+P$ adds points, $-P$ removes points.
- Point lots track individual accruals, remaining points, and timestamps.
- Redemptions, reversals, and expiries allocate from lots via `TransactionLotAllocation`.

### Layer C: Domain Lifecycle Services (`src/loyalty_ledger/services/`)
- `AccrualService`: Computes eligible spend, evaluates tier rules, creates posted transactions and new point lots.
- `RedemptionService`: Atomic points availability check, earliest-expiry-first allocation, concurrency protection, rejection recording.
- `ReturnReversalService`: Proportional points deduction, link to original transaction, handling of negative balance / customer debt.
- `ExpiryService`: Scans lots matching cutoff date, applies lot allocation, ensures batch-level and lot-level idempotency.
- `TierService`: Evaluates rolling 12-month net qualifying spend, records tier transitions in `AccountTierHistory`.

### Layer D: Anomaly Injection & Detection Engine (`src/loyalty_ledger/anomaly_detection/`)
- **Injection Layer**: Injects the 5 mandatory anomaly types (AN-001 through AN-005) into a designated evaluation dataset partition.
- **Ground Truth Isolation**: Saves known labels into `ground_truth.csv`, `ground_truth.json`, and isolated evaluation records.
- **Independent Detector**: Scans raw data without access to ground truth. Computes True Positives, False Positives, False Negatives, Precision, Recall, and F1 scores.

### Layer E: Validation & Reconciliation Engine (`src/loyalty_ledger/validation/`)
- Validates 20 distinct data integrity checks across foreign keys, arithmetic, idempotency, dates, and balances.
- Generates `validation_summary.json` and human-readable `validation_report.md`.

### Layer F: REST API & Web Operations Console (`src/loyalty_ledger/api/`)
- FastAPI endpoints for all operational workflows.
- OpenAPI specification with interactive docs at `/docs`.
- Single Page Operations Console served at `/` and `/dashboard`.

---

## 3. Database Concurrency & Transaction Isolation Architecture

### SQLite Runtime (WAL Mode)
- **Non-blocking Concurrent Reads:** All read operations (`SELECT`) run as standard deferred transactions (`BEGIN DEFERRED`). Under Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), readers read point-in-time snapshots concurrently without taking write reservations or blocking concurrent writers.
- **Selective Immediate Writes:** Balance-changing mutations (redemptions, lot allocations, order return reversals, and expiry batches) invoke `begin_write_transaction(session)`. This sets connection execution options `sqlite_immediate: True`, instructing SQLAlchemy to emit `BEGIN IMMEDIATE` strictly for write workflows, avoiding write-lock upgrade failures.
- **Connection & Busy Timeout:** `PRAGMA busy_timeout = 30000;` and DBAPI connection timeout (`timeout=30.0`) are configured on every SQLite connection, allowing competing writers to serialize smoothly without raising transient lock exceptions.

### PostgreSQL Compatibility
- On PostgreSQL deployments, `bind.dialect.name == "sqlite"` evaluates to `False`, rendering SQLite-specific PRAGMAs and immediate begin statements safe no-ops. PostgreSQL enforces row-level locking natively via `SELECT ... FOR UPDATE` (used in `RedemptionService` and lot allocation queries) within standard MVCC transactions.
