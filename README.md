# Loyalty Ledger Intelligence Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Passed](https://img.shields.io/badge/Validation-20%2F20%20Passed-brightgreen.svg)](reports/validation_report.md)
[![Tests: 26 Passed](https://img.shields.io/badge/Tests-26%2F26%20Passed-brightgreen.svg)](tests/)
[![Evaluation: 1.00 F1](https://img.shields.io/badge/Anomaly%20F1-1.00%20(100%25)-success.svg)](evaluation_metrics.json)

An auditable, double-entry-style loyalty ledger and analytics platform built with Python, FastAPI, and SQLAlchemy. The platform provides mathematical balance reconciliation, FIFO point-lot lifecycle tracking, deterministic synthetic dataset generation, independent rule-based anomaly detection with ground-truth isolation, automated validation suites, and an interactive operational web dashboard.

---

## Table of Contents

- [Quick Start (Fresh Checkout)](#quick-start-fresh-checkout)
- [Configuration and Database Reset](#configuration-and-database-reset)
- [Architecture and Data Model](#architecture-and-data-model)
- [Dataset Specifications & Scale](#dataset-specifications-scale)
- [Reproducibility Guarantee](#reproducibility-guarantee)
- [Evaluation Methodology](#evaluation-methodology)
- [Validation Suite (20 Checks)](#validation-suite-20-checks)
- [Concurrency & Transaction Safety](#concurrency-transaction-safety)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Submission and AI Use](#submission-and-ai-use)
- [Command Line Interface (CLI)](#command-line-interface-cli)
- [Interactive Operations Dashboard](#interactive-operations-dashboard)
- [REST API Endpoints](#rest-api-endpoints)
- [Automated Testing Suite (26 Tests)](#automated-testing-suite-26-tests)
- [Deliverable Documentation & Exports](#deliverable-documentation-exports)
- [Project Directory Structure](#project-directory-structure)
- [License](#license)

---

## Quick Start (Fresh Checkout)

Follow this minimal, verified procedure to inspect and run the platform from a fresh repository checkout.

### 1. Prerequisites
- **Python**: Supported versions are Python 3.11, 3.12, or 3.13 (`pyproject.toml` requires `>=3.11`).
- **Operating System**: Windows (PowerShell), macOS, or Linux.
- **Git** and standard shell tools.

### 2. Clone the Repository
Clone the repository and enter the project directory:

```bash
git clone https://github.com/vishalvoweldas/loyalty-ledger-intelligence-platform.git
cd "loyalty-ledger-intelligence-platform"
```

> [!NOTE]
> All subsequent commands should be executed from the repository root directory.

### 3. Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
Install the package in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

### 5. Generate Starter-Scale Dataset
Generate a lightweight starter dataset (500 customers, 2,500 orders, 7,500 points transactions + 16 injected ground-truth anomalies). This takes approximately 2–3 seconds and initializes `data/loyalty_ledger.db`:

```bash
python -m loyalty_ledger.cli generate --scale starter --seed 20261022
```

> [!TIP]
> **Starter Scale Scope:** Starter scale is optimized for rapid local inspection, smoke tests, and UI verification. It does not replace the full 20,000 customer / 100,000 order / 300,000 transaction dataset used for the official full release verification report.

### 6. Validate the Dataset
Execute the 20-check automated data integrity suite in evaluation mode:

```bash
python -m loyalty_ledger.cli validate --mode evaluation
```
**Expected outcome:**
```
=== Running Validation Suite (mode=evaluation) ===
Validation finished: 20/20 checks passed.
Saved reports to .../reports/validation_summary.json and .../reports/validation_report.md
```

### 7. Start the API Server & Operations Dashboard
Launch the server on localhost port 8000:

```bash
python -m loyalty_ledger.cli serve --host 127.0.0.1 --port 8000
```

### 8. Access the Web Dashboard and API Docs
- **Web Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/) or [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
- **Interactive OpenAPI / Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 9. Verify Server Health
In a separate terminal, test the real health endpoint:

**Windows (PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health"
```

**macOS / Linux:**
```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

**Expected JSON Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "engine": "sqlite",
  "version": "1.0.0"
}
```

### 10. Run the Automated Tests
Run the fast unit test suite (< 1 second):
```bash
pytest tests/unit/ -v
```

To run the complete 26-test regression and integration suite (~2.5 minutes):
```bash
pytest tests/ -v
```

---

## Configuration and Database Reset

### 1. Configuration Resolution & Defaults
The application is configured through environment variables with sensible defaults defined in [src/loyalty_ledger/config.py](src/loyalty_ledger/config.py):

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///<PROJECT_ROOT>/data/loyalty_ledger.db` | SQLAlchemy connection URI. |
| `DEFAULT_SEED` | `20261022` | Deterministic random seed for synthetic data generation. |
| `DEFAULT_TIMEZONE`| `UTC` | Simulation clock timezone. |
| `SIMULATION_START_DATE` | `2026-01-01T00:00:00Z` | Simulation timeline start timestamp. |
| `SIMULATION_END_DATE` | `2026-10-22T23:59:59Z` | Simulation timeline end timestamp. |
| `APP_HOST` | `0.0.0.0` | Default listening host for `loyalty-ledger serve`. |
| `APP_PORT` | `8000` | Default listening port for `loyalty-ledger serve`. |
| `LOG_LEVEL` | `INFO` | Console logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `LOYALTY_DISABLE_FK` | *(unset)* | Internal generator optimization flag used during bulk generation. |

### 2. Output File Locations
- **Database**: `data/loyalty_ledger.db` (with companion `-wal` and `-shm` files during operation).
- **Exports**: Written to `exports/csv/`, `exports/json/`, `exports/sql/`, and `exports/starter/`.
- **Reports**: Machine-readable summaries and Markdown reports are written to `reports/` and mirrored to the repository root.

### 3. Generation Replacement Policy
When running `python -m loyalty_ledger.cli generate`:
- The CLI option `--clean` defaults to **`True`**.
- Running generation against an existing database **drops all existing tables and replaces them** with the newly generated dataset.
- Generation **does not append** to existing tables; it completely recreates the schema and initial data.

### 4. Safe Backup and Database Reset Procedure

> [!CAUTION]
> **Destructive Operation**: Running `generate` overwrites `data/loyalty_ledger.db`. Always back up your active database before regenerating.

**Step 1: Stop Running Processes**  
Ensure that the web server (`loyalty-ledger serve`), background tests, or SQLite browser tools are completely stopped (`Ctrl+C`). Never copy or remove database files while active connections exist.

**Step 2: Create a Backup**  
**Windows (PowerShell):**
```powershell
Copy-Item data/loyalty_ledger.db data/loyalty_ledger.db.backup
if (Test-Path data/loyalty_ledger.db-wal) { Copy-Item data/loyalty_ledger.db-wal data/loyalty_ledger.db-wal.backup }
if (Test-Path data/loyalty_ledger.db-shm) { Copy-Item data/loyalty_ledger.db-shm data/loyalty_ledger.db-shm.backup }
```

**macOS / Linux:**
```bash
cp data/loyalty_ledger.db data/loyalty_ledger.db.backup
[ -f data/loyalty_ledger.db-wal ] && cp data/loyalty_ledger.db-wal data/loyalty_ledger.db-wal.backup
[ -f data/loyalty_ledger.db-shm ] && cp data/loyalty_ledger.db-shm data/loyalty_ledger.db-shm.backup
```

**Step 3: Safe Manual Reset & Regeneration**  
To regenerate the full canonical dataset from scratch:
```bash
python -m loyalty_ledger.cli generate --scale full --seed 20261022 --clean
```

### 5. SQLite WAL Companion Files (`-wal` and `-shm`)
In SQLite Write-Ahead Logging mode (`PRAGMA journal_mode=WAL;`), changes are initially written to `data/loyalty_ledger.db-wal`, indexed by `data/loyalty_ledger.db-shm`.
- These companion files are normal and managed automatically by SQLite.
- Upon clean application shutdown, SQLite checkpoints transactions from `-wal` back into `loyalty_ledger.db`.
- **Do not delete `-wal` or `-shm` while the application is running**, as this will corrupt uncheckpointed transactions and cause immediate `database is locked` or `file is not a database` exceptions.

---

## Architecture and Data Model

The platform is designed around an append-only, double-entry style financial ledger with strict separation of concerns:

```
┌───────────────────────────────────────────────────────────┐
│             Web Dashboard & REST API (FastAPI)            │
│         (10 Operations Views / OpenAPI / Swagger)         │
└─────────────────────────────┬─────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│          Domain Lifecycle Services & Rule Engine          │
│   (Accrual, FIFO Redemption, Returns, Expiry, Tiers)      │
└─────────────────────────────┬─────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│            Append-Only Points Ledger & Lots Core          │
│   (Signed Points Deltas, PointLots, Balance Reconciliation)│
└─────────────────────────────┬─────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│           Persistence Layer (SQLAlchemy 2.0 ORM)          │
│   (SQLite WAL + Foreign Keys / PostgreSQL DDL & Seed)     │
└─────────────────────────────▲─────────────────────────────┘
                              │
┌─────────────────────────────┴─────────────────────────────┐
│        Independent Anomaly Detection & Validation         │
│   (Isolated Detector, Ground Truth, 20-Check Validator)   │
└───────────────────────────────────────────────────────────┘
```

### 1. Data Flow
1. **Synthetic Data Generation**: The deterministic generator (`seed=20261022`) creates entities in topological order: Tiers/Rules $\to$ Customers/Accounts $\to$ Orders/Order Lines $\to$ Accrual Transactions/Lots $\to$ Redemptions $\to$ Returns/Reversals $\to$ Expiry Batches.
2. **Persistence**: Ingested via SQLAlchemy 2.0 into SQLite (with `PRAGMA foreign_keys=ON;` and WAL mode) for local execution, or PostgreSQL 16 schema via DDL.
3. **Domain Services**: Manage operational events (accruing points, allocating lots, reversing returns, expiring lots, promoting tiers).
4. **Validation Engine**: Executes 20 distinct data integrity checks across balances, arithmetic, foreign keys, and idempotency.
5. **Independent Anomaly Detection**: Anomaly detector scans raw operational tables without ground truth access; evaluator compares findings against isolated ground truth.
6. **API & Dashboard**: Exposes REST endpoints and an interactive single-page dashboard for operators.

### 2. Principal Entities & Relational Schema
The platform defines **19 tables** in SQLAlchemy ORM and [docs/data_dictionary.md](docs/data_dictionary.md):
- **Core Domain Entities (10)**: `Customer`, `LoyaltyAccount`, `Tier`, `Rule`, `Reward`, `Order`, `OrderLine`, `PointsTransaction`, `PointLot`, `TransactionLotAllocation`.
- **Supporting Lifecycle Entities (5)**: `Redemption`, `OrderReturn`, `ExpiryBatch`, `AccountTierHistory`, `AuditEvent`.
- **Isolated Ground Truth Entity (1)**: `GroundTruthRecord` (used only for evaluation).
- **Supporting / Operational Metadata (3)**: `account_rule_assignments`, `redemption_attempts`, `generation_runs`.

Full field specifications, types, nullability, and constraints are documented in [docs/data_dictionary.md](docs/data_dictionary.md) and [docs/entity_relationships.md](docs/entity_relationships.md).

### 3. Ledger Core: PointsTransaction, PointLot, and Allocations
- **`PointsTransaction`**: The immutable, append-only transaction ledger. Records signed point movements (`points_delta`): $+P$ for `ACCRUAL`, $-P$ for `REDEMPTION`, `REVERSAL`, and `EXPIRY`. Transactions are never updated or deleted.
- **`PointLot`**: Represents a discrete positive earning event with `original_points`, `remaining_points`, `accrued_at`, `expires_at` (365-day expiry), and `status` (`OPEN`, `EXHAUSTED`, `EXPIRED`).
- **`TransactionLotAllocation`**: The many-to-many bridge mapping debit transactions to specific lots. Enforces the fundamental lot conservation invariant:
  $$\text{original\_points} = \text{remaining\_points} + \sum(\text{allocated\_points})$$

### 4. Accounting Invariants & Lifecycle Rules
- **Mathematical Balance Reconciliation**: Account balance is not an independent authoritative number; it reconciles to the signed ledger sum:
  $$\text{Balance} = \sum_{\text{account}} \text{points\_delta}$$
- **FIFO Lot Allocation**: Redemptions consume lots ordered strictly by `expires_at ASC, lot_id ASC` (earliest-expiry-first). When a redemption exceeds a single lot's remaining points, it splits across multiple lots.
- **Proportional Return Reversals**: Line-item merchandise returns claw back points proportionally based on returned eligible spend:
  $$\text{reversed\_points} = \left\lfloor \frac{\text{returned\_spend\_minor} \times \text{accrued\_points}}{\text{original\_eligible\_spend\_minor}} \right\rfloor$$
  If a customer has already redeemed points, the account enters a negative balance (customer debt) rather than silently ignoring the reversal.
- **Expiry Batch Idempotency**: Periodic expiry batches evaluate lots with `expires_at \le \text{cutoff}` using deterministic idempotency keys (`IDEMP-EXP-...`), ensuring repeated runs produce 0 additional expiries.
- **Tier Qualification**: Evaluated dynamically based on rolling 12-month qualifying net spend (deducting returns and excluding non-merchandise fees such as taxes, shipping, gift cards, and warranties).
- **Transaction Boundaries & Concurrency**: Mutations invoke `begin_write_transaction(session)`, using `sqlite_immediate: True` on SQLite to serialize balance mutations and prevent overspending.

---

## Dataset Specifications & Scale

### Scope Definitions
To eliminate ambiguity across different documentation contexts, table and entity counts reflect four distinct, precisely defined scopes:
1. **14 Verified Domain Entities**: The core entities deterministically verified in the two-run reproducibility verification (`reproducibility_report_full.json`).
2. **15 Exported Tables**: All business tables exported to `exports/csv/` and `exports/json/` (the 14 domain entities + `audit_events`).
3. **16 Ground Truth Records**: Isolated anomaly records in `ground_truth.csv` and `ground_truth.json` (intentionally isolated from business exports).
4. **19 Data Dictionary Tables**: Complete schema in [docs/data_dictionary.md](docs/data_dictionary.md) (the 15 exported tables + `ground_truth_records` + 3 internal tables: `account_rule_assignments`, `redemption_attempts`, `generation_runs`).

### Full-Scale Dataset Inventory (Seed: `20261022`)
Directly measured from the verified production database `data/loyalty_ledger.db` and [dataset_manifest.json](dataset_manifest.json):

| Entity / Table | Count | ID Format | Description |
| :--- | :---: | :--- | :--- |
| **Customers** | **20,000** | `CUS-000001` .. `CUS-020000` | Retail loyalty customers across 5 geographical regions |
| **Loyalty Accounts** | **20,000** | `LOY-CUS-000001` .. | 1:1 baseline account per customer with cached balance |
| **Tiers** | **3** | `TIER-BRONZE`, `SILVER`, `GOLD` | Tier thresholds and earning multipliers |
| **Rules** | **5** | `RULE-ACCRUAL-V1`, etc. | Configurable business rules with effective dates |
| **Orders** | **100,000** | `ORD-2026-000001` .. | Orders with monetary totals and status tracking |
| **Order Lines** | **199,822** | `LINE-ORD-...` | Merchandise lines with category eligibility |
| **Points Transactions** | **300,000** | `PTS-2026-00000001` .. | **Exactly 300,000 immutable ledger records** |
| **Point Lots** | **100,000** | `LOT-PTS-...` | FIFO point lots with 365-day expiry tracking |
| **Lot Allocations** | **201,086** | `ALLOC-...` | Reconciled lot allocations (Redemptions, Expiries & Reversals) |
| **Redemptions** | **98,996** | `RDM-2026-000001` .. | Approved catalog reward redemptions (98,994 baseline + 2 AN-002) |
| **Order Returns** | **20,002** | `RET-ORD-...` | Returns linked to original order (20,000 baseline + 2 AN-003) |
| **Account Tier History** | **20,000** | `ATH-000001` .. | Historical tier transitions with reason codes |
| **Expiry Batches** | **1** | `EXP-2026-000001` | Periodic expiry execution batch record |
| **Rewards Catalog** | **4** | `RWD-VOUCHER-100` .. | Catalog reward vouchers (₹100 to ₹1,000) |
| **Audit Events** | **0** | `AUD-...` | Populated via console operator actions |
| **Ground Truth Records** | **16** | `GT-AN001-01` .. | Isolated evaluation answer key |

### Transaction Ledger Breakdown (300,000 Total)
- **ACCRUAL**: 100,000 (Positive delta)
- **EXPIRY**: 81,004 (Negative delta; 80,996 baseline + 8 duplicate expiries in AN-004)
- **REDEMPTION**: 98,996 (Negative delta; 98,994 baseline + 2 unbacked redemptions in AN-002)
- **REVERSAL**: 20,000 (Negative delta; 20,000 partial returns; 2 unreversed returns in AN-003 post 0 reversal transactions)
- **Total Points Transactions**: **300,000**

### Reconciled Lot Allocations Breakdown (201,086 Rows)
Every single row in `transaction_lot_allocations` reconciles to source business movements:
- **Redemption Allocations ($100,082$)**:
  - $97,906$ redemptions satisfied by exactly 1 lot: $97,906 \times 1 = 97,906$ rows
  - $1,088$ redemptions split across 2 lots (FIFO): $1,088 \times 2 = 2,176$ rows
  - $2$ intentional unbacked AN-002 redemptions: $2 \times 0 = 0$ rows
  - *Subtotal*: $97,906 + 2,176 + 0 = \mathbf{100,082}$ rows
- **Expiry Allocations ($81,004$)**:
  - $80,988$ expired lots with 1 expiry allocation: $80,988 \times 1 = 80,988$ rows
  - $8$ duplicate-expiry lots in AN-004: $8 \times 2 = 16$ rows
  - *Subtotal*: $80,988 + 16 = \mathbf{81,004}$ rows
- **Return Reversal Allocations ($20,000$)**:
  - $20,000$ partial returns reversing points from original accrual lots: $20,000 \times 1 = 20,000$ rows
  - $2$ unreversed returns in AN-003: $2 \times 0 = 0$ rows
  - *Subtotal*: $\mathbf{20,000}$ rows
- **Total Reconciled Allocations**: $100,082 + 81,004 + 20,000 = \mathbf{201,086}\text{ rows}$ (CSV file: 201,087 physical lines including header; JSON file: 201,086 objects).

---

## Reproducibility Guarantee

The generator is deterministic. Running generation twice with the fixed seed `20261022` into isolated temporary databases produces identical row counts and 100% matching canonical SHA-256 hashes across **all 14 domain entities**:

### Canonical Full-Scale Checksums (Seed: `20261022`, 100,000 Orders)
Source: [reports/reproducibility_report_full.json](reports/reproducibility_report_full.json) (Run 1: `RUN-FULL-RUN1-1793112654`, Run 2: `RUN-FULL-RUN2-1793112730`):

| Entity Name | Run 1 Rows | Run 2 Rows | Canonical Full-Content SHA-256 Checksum | Match Status |
| :--- | :---: | :---: | :--- | :---: |
| `customers` | 20,000 | 20,000 | `e10d5088a6939852701b86dd7a430fb4ad5e50a8bc2fcdcdeba6bc507f646432` | **IDENTICAL** |
| `loyalty_accounts` | 20,000 | 20,000 | `972edd62e87c94babf296669d051575feb3f92bd824a6566f9354521f990c801` | **IDENTICAL** |
| `tiers` | 3 | 3 | `d01f7731e0c62840ca112a1ded818ccfc03792a07be5a54454ae923bb7f15592` | **IDENTICAL** |
| `rules` | 5 | 5 | `9e8b90937443dea4e068bc29df16ec31760c2add32baae87472bfc53faaa05d3` | **IDENTICAL** |
| `orders` | 100,000 | 100,000 | `87007c23f7949f2fef60031d0d5891ee6f9f277d8c2f6e6159757516aab70927` | **IDENTICAL** |
| `order_lines` | 199,822 | 199,822 | `4afbd233f283b7c9809a77efc49472dffced8a1972d16d0f19611d095b777b12` | **IDENTICAL** |
| `points_transactions` | 300,000 | 300,000 | `bd16f575be8b5031d955662381d72aee94e9de7619f6986c10d91156e6221192` | **IDENTICAL** |
| `rewards` | 4 | 4 | `1550df9815b533b02056f64eae96aa4c1dfd47b7488627390b2d2d10e67740b0` | **IDENTICAL** |
| `redemptions` | 98,996 | 98,996 | `f97772e5e8685818af2a4a1d516be6c6ff0297c2e3850e5d09b90694e9bf96dd` | **IDENTICAL** |
| `expiry_batches` | 1 | 1 | `62c0cdc6376fae247a9eea8068e34db6d2a9693e776b9da864a9770f563c5bfc` | **IDENTICAL** |
| `point_lots` | 100,000 | 100,000 | `5cb189f67e806029c6efb29792045e57906640c71c75da2a8fd78cab3c22133a` | **IDENTICAL** |
| `transaction_lot_allocations` | 201,086 | 201,086 | `5d7ca1295b04126a6b2b2c26ad95ea40e476e18fb350c9e1ee8649f5220a31f9` | **IDENTICAL** |
| `account_tier_history` | 20,000 | 20,000 | `b8d31c8a0121c599440281c398a150b037470f9eb2bc4adacf635759a8925b34` | **IDENTICAL** |
| `order_returns` | 20,002 | 20,002 | `6f875c65bccd29e8d1a5be73ffc18d4ff672fa1dabf8581458d4eded4b735424` | **IDENTICAL** |

Both **Starter Scale** ([reports/reproducibility_report_starter.json](reports/reproducibility_report_starter.json)) and **Full Scale** ([reports/reproducibility_report_full.json](reports/reproducibility_report_full.json)) maintain scale-isolated reports with explicit run IDs, start/end timestamps, and 0 checksum discrepancies.

To execute the reproducibility verification:
```bash
python -m loyalty_ledger.cli reproduce --scale full --seed 20261022
```

---

## Evaluation Methodology

### 1. Mandatory Anomaly Scenarios
The platform implements all five required anomaly scenarios defined in PRD §6:

| Anomaly Class | Canonical Description | Injection Mechanism | Ground Truth Records |
| :--- | :--- | :--- | :---: |
| **AN-001** | Stored balance differs from ledger sum | `cached_balance_points` is tampered (+250 on `LOY-CUS-000010`, -150 on `LOY-CUS-000020`) without modifying ledger rows. | 2 |
| **AN-002** | Excessive redemption accepted beyond balance | Approved redemptions (`RDM-AN002-0001`, `RDM-AN002-0002`) accepted on accounts with 0 balance, posting unbacked negative transactions. | 2 |
| **AN-003** | Returned order retains unreversed points | Returns processed (`RET-ORD-...`) with `reversal_transaction_id` left NULL and 0 points reversed. | 2 |
| **AN-004** | Duplicate point lot expiry movements | Expired point lots receive duplicate expiry transactions and double lot allocations. | 8 |
| **AN-005** | Tier calculated on gross spend instead of net | Accounts upgraded to Gold based on gross spend, while net spend qualifies only for Bronze. | 2 |
| **TOTAL** | **All Injected Anomaly Classes** | Controlled injection into evaluation dataset | **16** |

### 2. Ground-Truth Isolation
Ground-truth isolation is verified by design in the codebase:
- **Injector** (`src/loyalty_ledger/anomaly_detection/anomaly_injector.py`): Injects anomalies and writes ground-truth labels directly to `ground_truth_records` table and export files (`ground_truth.csv`, `ground_truth.json`).
- **Detector** (`src/loyalty_ledger/anomaly_detection/detector.py`): Queries **only raw operational business tables** (`loyalty_accounts`, `points_transactions`, `point_lots`, `transaction_lot_allocations`, `order_returns`, `orders`). The detector has no references, imports, or queries touching `GroundTruthRecord` or ground truth files.
- **Evaluator** (`src/loyalty_ledger/anomaly_detection/evaluator.py`): An independent component that compares the detector's findings against `GroundTruthRecord` to compute True Positives ($TP$), False Positives ($FP$), False Negatives ($FN$), Precision, Recall, and F1 score:
  $$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}, \quad F1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

### 3. Evaluation Results (Measured)
Executed via `python -m loyalty_ledger.cli evaluate` and saved in [evaluation_metrics.json](evaluation_metrics.json):

| Anomaly Class | Ground Truth | Detected | True Positives | False Positives | False Negatives | Precision | Recall | F1 Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **AN-001** | 2 | 2 | 2 | 0 | 0 | **1.00** | **1.00** | **1.00** |
| **AN-002** | 2 | 2 | 2 | 0 | 0 | **1.00** | **1.00** | **1.00** |
| **AN-003** | 2 | 2 | 2 | 0 | 0 | **1.00** | **1.00** | **1.00** |
| **AN-004** | 8 | 8 | 8 | 0 | 0 | **1.00** | **1.00** | **1.00** |
| **AN-005** | 2 | 2 | 2 | 0 | 0 | **1.00** | **1.00** | **1.00** |
| **OVERALL** | **16** | **16** | **16** | **0** | **0** | **1.00** | **1.00** | **1.00** |

> [!IMPORTANT]
> **Synthetic Evaluation Scope Notice:** Perfect metrics ($F1 = 1.00$) on a finite synthetic dataset demonstrate that the detector accurately identifies the specific rule-violation signatures modeled in this project. They do **not** imply generalization to unseen real-world production environments where data corruption patterns, distributed race conditions, and fraud behaviors are unconstrained.

### 4. Validation Modes: Baseline vs. Evaluation
The validation suite supports two explicit modes:
- **`baseline` Mode**: Evaluates baseline business records excluding injected anomaly IDs. Confirms 100% accounting compliance across all 19,998 baseline accounts, 20,000 returns, 99,992 lots, and 98,994 redemptions.
- **`evaluation` Mode**: Validates the full operational database including injected anomalies. Confirms that all 16 anomalies match expected signatures with zero unexplained defects.

Both modes pass **20 / 20 checks** (`PASSED`).

---

## Validation Suite (20 Checks)

The validation suite (`src/loyalty_ledger/validation/validator.py`) implements 20 integrity checks:

- **Status vs. Severity Separation**: Check `status` (`PASS` / `FAIL`) indicates empirical rule compliance. Check `severity` (`NONE`, `INFO`, `WARNING`, `ERROR`) conveys finding criticality. Passing checks are assigned `NONE` or informational badges, preventing false error alerts in reports and UI.
- **Ground-Truth Aware Validation**: Baseline mode isolates baseline operational records from anomaly fixtures. Evaluation mode verifies that detected discrepancies match ground-truth signatures.

1. `PRIMARY_KEY_UNIQUENESS`: 0 duplicate PKs across all 14 canonical tables.
2. `FOREIGN_KEY_INTEGRITY`: 0 orphaned records across all relations.
3. `REQUIRED_FIELDS_AND_NULLABILITY`: 0 unexpected NULL values in required columns.
4. `ENUM_AND_ALLOWED_VALUES`: 100% compliant status, region, and transaction type codes.
5. `DATE_ORDERING`: Chronological ordering enforced across orders, transactions, and expirations.
6. `RULE_EFFECTIVE_DATE_CONSISTENCY`: All transactions align with rules active at event date.
7. `ORDER_ARITHMETIC`: `net_merchandise + tax + shipping - discount = gross_total`.
8. `RETURN_QUANTITY_ARITHMETIC`: `returned_quantity <= quantity` across all 199,822 order lines.
9. `POINTS_ACCRUAL_CALCULATIONS`: Accurate floor rounding $\lfloor\text{eligible\_spend} / \text{spend\_per\_point}\rfloor$ and tier multipliers.
10. `REVERSAL_REFERENCES_AND_AMOUNTS`: Valid link to original accrual and order (2 unreversed returns isolated to AN-003).
11. `BALANCE_RECONCILIATION`: 100% baseline balance reconciliation (2 mismatches isolated to AN-001).
12. `POINT_LOT_ALLOCATIONS`: $\text{original\_points} = \text{remaining\_points} + \sum(\text{allocations})$ (8 duplicate expiries isolated to AN-004).
13. `REDEMPTION_AVAILABILITY_AND_SAFETY`: Redemptions backed by valid open lot allocations (2 unbacked redemptions isolated to AN-002).
14. `EXPIRY_IDEMPOTENCY`: Idempotent batch and lot-level allocations (0 duplicate expiries in baseline).
15. `TIER_QUALIFICATION_RULES`: Tiers correctly assigned based on rolling 12m net spend (2 gross spend misclassifications isolated to AN-005).
16. `LIFECYCLE_TRANSITION_LEGALITY`: All orders and accounts hold valid lifecycle states.
17. `IDEMPOTENCY_KEY_UNIQUENESS`: 300,000 unique idempotency keys in `points_transactions` (0 duplicates).
18. `GROUND_TRUTH_INTEGRITY`: 16 labeled ground-truth records verified across all 5 anomaly classes.
19. `ENTITY_ROW_COUNTS`: Exactly 20,000 customers, 100,000 orders, 300,000 transactions, 100,000 lots, 201,086 allocations verified.
20. `REPRODUCIBILITY_VERIFICATION`: Deterministic seed `20261022` configured and verified.

Summary report: [validation_summary.json](validation_summary.json) | Detailed report: [reports/validation_report.md](reports/validation_report.md).

---

## Concurrency & Transaction Safety

The platform incorporates a SQLite concurrency architecture engineered to prevent `database is locked` runtime failures while guaranteeing strict ACID consistency, FIFO lot conservation, and overspending prevention:

### 1. SQLite WAL & Transaction Boundary Implementation
- **Non-Blocking WAL Snapshot Reads**: SQLite Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) enables concurrent readers to read point-in-time snapshots simultaneously without taking locks or blocking writers. Read queries execute in standard deferred transactions (`BEGIN DEFERRED`).
- **Selective Write Serialization (`begin_write_transaction`)**: Balance-changing services (`RedemptionService`, `ReturnReversalService`, `ExpiryService`, `AccrualService`, `LedgerService`, `TierService`) invoke `begin_write_transaction(session)`. This sets execution options `sqlite_immediate: True`, instructing SQLAlchemy to emit `BEGIN IMMEDIATE` strictly for write workflows, acquiring the write lock upfront and preventing lock-upgrade deadlocks.
- **Clean Transaction Boundaries**: `begin_write_transaction` verifies that no uncommitted ORM changes are pending (`not (session.dirty or session.new or session.deleted)`) and rolls back prior read snapshots before acquiring the immediate lock, eliminating premature commits and dirty writes.
- **Busy Timeout & Pragmas**: Every SQLite connection is configured with `PRAGMA busy_timeout = 30000;`, `PRAGMA foreign_keys = ON;`, and `PRAGMA synchronous = NORMAL;` via connection event listeners.

### 2. Measured Concurrency Benchmark Evidence
The concurrency model was validated under specific measured workloads:
- **Concurrent Read Smoke Test**: 25 simultaneous queries across 5 distinct endpoints (`/customers`, `/orders`, `/ledger`, `/dashboard/summary`, `/anomalies`) repeated over 3 rounds (75 total requests) achieved **100% HTTP 200 responses with 0 lock errors and 0 HTTP 500s**.
- **Mixed Read/Write Workload Test**: 20 concurrent readers issuing queries alongside 10 concurrent threads competing for redemptions (60 points requested each on an account holding 100 points). Exactly **1 redemption succeeded** and **9 were rejected** with `INSUFFICIENT_AVAILABLE_POINTS`. The final balance remained exactly 40 points, FIFO lot conservation was preserved, and 0 database lock errors occurred.

---

## Known Limitations

This section documents verified limitations based on the current implementation:

1. **Local SQLite Execution Verified**: Local execution is verified using SQLite 3 in WAL mode. While suitable for single-node local execution, evaluation, and CI testing, SQLite is a file-based database and not intended for distributed, multi-region web deployments.
2. **PostgreSQL Integration Status**:
   - ANSI-compliant DDL ([exports/sql/schema.sql](exports/sql/schema.sql)), SQL seed data ([exports/sql/seed.sql](exports/sql/seed.sql)), and container configuration ([docker-compose.yml](docker-compose.yml)) are provided.
   - However, **live runtime integration, automated Alembic migrations against PostgreSQL, and multi-client PostgreSQL concurrency benchmarks have not been verified in a live PostgreSQL cluster**.
3. **Synthetic Dataset Scope**: All customer behaviors, orders, and anomaly scenarios are synthetic, generated deterministically from seed `20261022`. They do not capture real-world traffic variance, organic fraud patterns, network partition latency, or distributed race conditions.
4. **Authentication & Authorization**: Authentication and role-based access control (RBAC) are **not implemented**. Endpoints do not enforce JWT or OAuth tokens. The web console and API operate with open access in the local environment.
5. **Unimplemented Production Controls**: The platform does not implement production controls such as automated backup/restore orchestration, secrets management (e.g., HashiCorp Vault), distributed tracing, rate limiting, or TLS termination.
6. **No Live Streaming Ingestion**: The system processes batches and discrete REST requests. It does not include streaming ingestion connectors (e.g., Apache Kafka, RabbitMQ).

---

## Troubleshooting

### 1. `ModuleNotFoundError: No module named 'loyalty_ledger'`
- **Likely Cause**: The virtual environment is not activated, or the package was not installed in editable mode.
- **Diagnostic Command**: `python -c "import loyalty_ledger; print(loyalty_ledger.__file__)"`
- **Corrective Action**:
  ```bash
  pip install -e .
  ```

### 2. Python Version Incompatibility
- **Likely Cause**: Running Python < 3.11.
- **Diagnostic Command**: `python --version`
- **Corrective Action**: Install Python 3.11, 3.12, or 3.13 and recreate the virtual environment.

### 3. Port 8000 Already in Use
- **Likely Cause**: Another server instance or background process is listening on port 8000.
- **Diagnostic Command**:
  - Windows: `Get-NetTCPConnection -LocalPort 8000`
  - Linux/macOS: `lsof -i :8000`
- **Corrective Action**: Stop the conflicting process or start the server on a different port:
  ```bash
  python -m loyalty_ledger.cli serve --host 127.0.0.1 --port 8080
  ```

### 4. Database Not Found or `OperationalError: no such table`
- **Likely Cause**: The database was not initialized or generated before starting the server.
- **Diagnostic Command**: `python -c "from loyalty_ledger.db import SessionFactory; s = SessionFactory(); s.execute('SELECT count(*) FROM customers'); s.close()"`
- **Corrective Action**: Run starter-scale or full-scale generation:
  ```bash
  python -m loyalty_ledger.cli generate --scale starter --seed 20261022
  ```

### 5. `sqlite3.OperationalError: database is locked`
- **Likely Cause**: An external SQLite client (e.g., DB Browser for SQLite) has an uncommitted write lock, or an old server process is holding a transaction open.
- **Diagnostic Command**: Check for background Python processes holding `data/loyalty_ledger.db`.
- **Corrective Action**: Close external database viewers, terminate hanging server processes, and verify that WAL mode is enabled:
  ```bash
  python -c "from loyalty_ledger.db import engine; c = engine.connect(); print(c.exec_driver_sql('PRAGMA journal_mode').scalar()); c.close()"
  ```
  Expected output: `wal`.

### 6. Validation Suite Reports `FINDINGS_DETECTED`
- **Likely Cause**: Running in `baseline` mode on a database containing injected evaluation anomalies (AN-001 through AN-005), or operational data was modified manually.
- **Diagnostic Command**: Run validation in evaluation mode:
  ```bash
  python -m loyalty_ledger.cli validate --mode evaluation
  ```
- **Corrective Action**: If intentional anomalies were modified or test records were left behind, regenerate the database using `python -m loyalty_ledger.cli generate --scale full --seed 20261022 --clean`.

### 7. Reproducibility Checksum Discrepancy
- **Likely Cause**: Running reproducibility verification with a different seed, custom scale, or non-deterministic changes.
- **Diagnostic Command**: `python -m loyalty_ledger.cli reproduce --scale starter --seed 20261022`
- **Corrective Action**: Ensure seed `20261022` is supplied and no background process is writing to the database.

### 8. Pytest Takes Too Long or Times Out
- **Likely Cause**: Running integration and concurrency tests while the database is locked by an active web server.
- **Diagnostic Command**: Run fast unit tests first: `pytest tests/unit/ -v`.
- **Corrective Action**: Stop the running `loyalty-ledger serve` instance before executing the complete test suite.

### 9. Browser Cannot Connect to `http://127.0.0.1:8000`
- **Likely Cause**: Server was not started or bound to an inaccessible address.
- **Diagnostic Command**: Verify output from `python -m loyalty_ledger.cli serve`.
- **Corrective Action**: Ensure the server is running on `127.0.0.1` and port `8000`.

---

## Submission and AI Use

### 1. Project Provenance & Repository Metadata
- **Author / Submitter**: Vishal Voweldas (<vishalvoweldas67@gmail.com>)
- **Public Repository URL**: `https://github.com/vishalvoweldas/loyalty-ledger-intelligence-platform.git`
- **Git Commit History**: The repository was developed iteratively. Development phases, architectural decisions, and verification audits are documented in [reports/final_release_verification.md](reports/final_release_verification.md).

### 2. Prompt History & AI Disclosure Documentation
- [docs/PROMPT_HISTORY.md](docs/PROMPT_HISTORY.md): Detailed record of the prompt progression across system scaffolding, domain implementation, anomaly injection, validation, and release hardening.
- [docs/AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md): Formal AI disclosure statement detailing tools used, AI assistance boundaries, human review, and verification checklists.

### 3. Transparent Statement of AI Assistance
This project was developed with the assistance of **Google DeepMind Antigravity (Gemini)** as an agentic AI pair programmer:
- **AI-Assisted Work**: ORM schema scaffolding from `PRD.md`, initial service-layer boilerplate, synthetic data generator algorithms, validation check scaffolding, and documentation drafting.
- **Human Review & Modification**: Mathematical proofs of balance reconciliation ($\sum \text{points\_delta} = \text{balance}$), FIFO lot allocation conservation arithmetic, resolution of SQLite locking via `begin_write_transaction` and WAL pragmas, strict separation of ground truth from anomaly detection, and verification of all 26 automated tests.
- **Independent Testing**: All 26 automated tests, 20 validation checks, two-run reproducibility verifications, and concurrency benchmarks were independently executed and verified.

### 4. Verification Reports & Audit Deliverables
- [reports/final_release_verification.md](reports/final_release_verification.md): Comprehensive release verification and acceptance audit report.
- [reports/validation_report.md](reports/validation_report.md): 20-check validation results.
- [validation_summary.json](validation_summary.json): Machine-readable validation results.
- [evaluation_metrics.json](evaluation_metrics.json): Anomaly detection precision, recall, and F1 scores.
- [reports/reproducibility_report_full.json](reports/reproducibility_report_full.json): Full-scale reproducibility report.
- [reports/reproducibility_report_starter.json](reports/reproducibility_report_starter.json): Starter-scale reproducibility report.

---

## Command Line Interface (CLI)

The package provides a unified CLI:

```bash
# Display help and available commands
python -m loyalty_ledger.cli --help

# Generate dataset (starter: 500 cus / 2.5k ord / 7.5k tx; full: 20k cus / 100k ord / 300k tx)
python -m loyalty_ledger.cli generate --scale starter --seed 20261022
python -m loyalty_ledger.cli generate --scale full --seed 20261022 --clean

# Run 20-check validation suite (mode: baseline | evaluation)
python -m loyalty_ledger.cli validate --mode evaluation

# Verify two-run reproducibility (scale: starter | full)
python -m loyalty_ledger.cli reproduce --scale full --seed 20261022

# Export all datasets to CSV, JSON, SQL with SHA-256 manifests
python -m loyalty_ledger.cli export --scale full --seed 20261022

# Evaluate anomaly detection against ground truth
python -m loyalty_ledger.cli evaluate

# Launch web server and dashboard
python -m loyalty_ledger.cli serve --host 127.0.0.1 --port 8000
```

---

## Interactive Operations Dashboard

The single-page web console (`http://127.0.0.1:8000/`) provides 10 operational views:

1. **Executive Dashboard**: Aggregate KPIs (Customers, Orders, Transactions, Accruals, Redemptions, Reversals, Expiries, Outstanding Balance, Reconciliation Status, Tier Distribution). Includes a **Refresh Dashboard** button that bypasses the 15-second anomaly cache (`?force_refresh=true`) and displays a cache freshness badge.
2. **Customer & Account Explorer**: Fast debounced server-side search across all 20,000 customers by Customer ID, Name, or Email; region dropdown filtering; full server-side pagination (Previous, Next, Page Size 25/50/100, page indicator, total count header `X-Total-Count`). Includes a 1-click **Ledger** button navigating directly to that customer's transaction history.
3. **Transaction Ledger**: Dynamic Account ID input (e.g. `LOY-CUS-000001`), transaction type filtering (`ACCRUAL`, `REDEMPTION`, `REVERSAL`, `EXPIRY`), and server-side pagination controls.
4. **Order & Returns Operations**: Integrated **Process Return Simulation Modal** allowing operators to select any Order ID, fetch its line items, choose return quantities ($0 \le \text{return\_qty} \le \text{ordered} - \text{already\_returned}$), select reason codes, provide an idempotency key, and execute atomic point reversals with real-time feedback.
5. **Redemptions Management**: Simulate catalog reward redemptions with instant balance check, FIFO lot allocation, double-spending prevention, and competing request stress simulations.
6. **Expiry Operations**: Inspect expiring lots and trigger batch expiry runs with real-time audit feedback and idempotency enforcement.
7. **Tier & Business Rules**: View active tier thresholds, earning rates, and rule effective dates.
8. **Anomaly Investigation**: Inspect detected anomalies with issue type, severity, observed vs. expected state, append operator audit review notes, and evaluate Precision/Recall/F1 against ground truth.
9. **Validation & Integrity**: Trigger the 20-check validation suite in Baseline or Evaluation mode; dynamic badge styling ensures passing checks display neutral badges rather than error badges.
10. **Reproducibility & Dataset Export**: Toggle between Full Scale and Starter Scale for deterministic reproducibility verification and manifest inspection.

---

## REST API Endpoints

The API is fully documented via OpenAPI at `/docs`. Primary endpoints include:

- `GET  /api/v1/health`: System health and database connectivity.
- `GET  /api/v1/dashboard/summary`: Executive metrics and transaction sums (supports `?force_refresh=true` and returns `X-Cache: HIT|MISS`).
- `GET  /api/v1/customers`: Server-side search across name, ID, and email with `X-Total-Count` header and pagination (`page`, `page_size`, `region`).
- `GET  /api/v1/customers/{customer_id}`: Customer profile with order history.
- `GET  /api/v1/accounts/{account_id}`: Loyalty account balance and tier.
- `GET  /api/v1/accounts/{account_id}/ledger`: Paginated immutable ledger entries with `X-Total-Count` header.
- `GET  /api/v1/accounts/{account_id}/reconciliation`: Balance reconciliation audit.
- `GET  /api/v1/orders`: Paginated orders with `X-Total-Count` header.
- `GET  /api/v1/orders/{order_id}`: Order details including line items, ordered quantities, and returned quantities.
- `POST /api/v1/orders/{order_id}/accrue`: Idempotent accrual calculation.
- `POST /api/v1/orders/{order_id}/returns`: Process return, validate returnable quantities, calculate proportional reversals, and prevent duplicate reversals.
- `POST /api/v1/redemptions`: Submit redemption request with FIFO lot allocation and overspending prevention.
- `POST /api/v1/expiry-batches`: Trigger batch point lot expiry.
- `GET  /api/v1/tiers`: View active tiers and qualifying thresholds.
- `GET  /api/v1/rules`: View active business rules and effective dates.
- `GET  /api/v1/anomalies`: List detected anomalies by severity/type.
- `GET  /api/v1/anomalies/evaluation`: Compute Precision, Recall, and F1 against ground truth.
- `POST /api/v1/anomalies/{anomaly_id}/review`: Record operator audit note.
- `POST /api/v1/validation/run`: Execute 20-check validation suite (`mode=baseline|evaluation`).
- `POST /api/v1/reproducibility/verify`: Run two-run reproducibility verification (`scale=full|starter`).
- `GET  /api/v1/reproducibility/report`: Retrieve scale-specific reproducibility verification report (`scale=full|starter`).
- `POST /api/v1/datasets/export`: Trigger CSV, JSON, and SQL export (`scale=full|starter`).
- `GET  /api/v1/datasets/manifest`: Retrieve scale-specific dataset manifest (`scale=full|starter`).

---

## Automated Testing Suite (26 Tests)

The platform includes an automated regression and lifecycle test suite executed via `pytest`:

```bash
pytest tests/ -v
```

**Results: 26 passed in ~165s (100% pass rate)**:
- **Unit Tests (`tests/unit/`)**:
  - `test_accrual_floor_rounding`: Verifies floor division and exclusion of non-merchandise fees.
  - `test_tier_threshold_boundaries`: Boundary tests for Bronze, Silver, and Gold qualifications.
  - `test_return_reversal_proportional`: Verifies proportional clawback calculations and cap at awarded points.
  - `test_rule_effective_date_boundaries`: Verifies rule activation windows.
  - `test_ledger_reconciliation_math`: Mathematical proof of $\sum(\text{points\_delta}) = \text{balance}$.
- **Integration Tests (`tests/integration/`)**:
  - `test_api_endpoints.py`: End-to-end API coverage for health, dashboard, customers, orders, validation runs, anomaly evaluation, reports, tiers, and rules.
  - `test_concurrency_locking.py`: 25 simultaneous concurrent read requests across 5 endpoints without database locks; mixed concurrent read/write workloads proving double-spending prevention under SQLite WAL mode.
  - `test_ledger_and_services.py`: Accrual idempotency, insufficient points rejection, expiry batch idempotency, excluded category filtering, full/partial returns with reversal references, competing redemptions against the same account, concurrent redemption & expiry lot safety.
- **Reproducibility Tests (`tests/reproducibility/`)**:
  - `test_fixed_seed_reproducibility`: Two-run generation comparison verifying identical row counts and canonical checksums.
- **Anomaly Tests (`tests/anomalies/`)**:
  - `test_mandatory_anomalies_injection`: Verifies injection of AN-001 through AN-005.
  - `test_independent_detection_and_evaluation`: Independent evaluation achieving 1.00 Precision, 1.00 Recall, and 1.00 F1 score.

---

## Deliverable Documentation & Exports

- **Documentation**:
  - [docs/PRD.md](docs/PRD.md): Product Requirements Document.
  - [docs/data_dictionary.md](docs/data_dictionary.md): Field-level specification for all 19 schema tables.
  - [docs/business_rules.md](docs/business_rules.md): Configurable rules, formulas, and anomaly definitions.
  - [docs/architecture.md](docs/architecture.md): Layered architecture, concurrency control, and data flow.
  - [docs/entity_relationships.md](docs/entity_relationships.md): ER diagram, cardinality, and foreign-key constraints.
  - [docs/api.md](docs/api.md): REST API specification and request/response models.
  - [docs/AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md): Formal AI tool usage and assistance disclosure statement.
  - [docs/PROMPT_HISTORY.md](docs/PROMPT_HISTORY.md): Chronological engineering prompt history.
- **Evaluation & Manifests**:
  - [ground_truth.csv](ground_truth.csv) & [ground_truth.json](ground_truth.json): Isolated evaluation ground truth (16 records).
  - [evaluation_metrics.json](evaluation_metrics.json): Anomaly detection precision, recall, and F1 scores.
  - [validation_summary.json](validation_summary.json) & [reports/validation_report.md](reports/validation_report.md): 20-check validation results.
  - [reproducibility_report.json](reproducibility_report.json): Two-run reproducibility comparison and checksums.
  - [reports/reproducibility_report_full.json](reports/reproducibility_report_full.json) & [reports/reproducibility_report_starter.json](reports/reproducibility_report_starter.json): Scale-specific reproducibility reports.
  - [reports/final_release_verification.md](reports/final_release_verification.md): Comprehensive release verification and acceptance audit report.
  - [source_manifest.json](source_manifest.json) & [dataset_manifest.json](dataset_manifest.json): Generator parameters and SHA-256 file hashes.
- **Exports**:
  - `exports/csv/`: 15 tables in CSV format.
  - `exports/json/`: 15 tables in JSON format.
  - `exports/sql/`: Full PostgreSQL DDL (`schema.sql`) and insert seeds (`seed.sql`).

---

## Project Directory Structure

```
Loyalty Ledger Intelligence Platform/
├── data/
│   └── loyalty_ledger.db       # SQLite WAL database (Full 20k/100k/300k dataset)
├── docs/
│   ├── PRD.md                  # Authoritative Product Requirements
│   ├── architecture.md         # System architecture & layers
│   ├── business_rules.md       # Configurable rules & formulas
│   ├── data_dictionary.md      # Field-level dictionary (19 tables)
│   ├── entity_relationships.md # ER diagrams & constraints
│   ├── api.md                  # API documentation
│   ├── AI_DISCLOSURE.md        # Formal AI tool usage declaration
│   └── PROMPT_HISTORY.md       # Chronological development prompt history
├── exports/
│   ├── csv/                    # CSV exports for all 15 business tables
│   ├── json/                   # JSON exports for all 15 business tables
│   └── sql/                    # PostgreSQL schema DDL & seed scripts
├── frontend/
│   └── public/
│       └── index.html          # Single-page operations console
├── reports/
│   ├── evaluation_metrics.json      # Anomaly evaluation scores (100% F1)
│   ├── final_release_verification.md# Comprehensive release verification report
│   ├── reproducibility_report.json  # Latest reproducibility report
│   ├── reproducibility_report_full.json
│   ├── reproducibility_report_starter.json
│   ├── validation_report.md
│   └── validation_summary.json
├── scripts/
│   ├── generate_data.py        # Data generator script
│   ├── validate_data.py        # Validation runner script
│   ├── export_data.py          # Exporter script
│   └── verify_reproducibility.py
├── src/loyalty_ledger/
│   ├── anomaly_detection/     # Anomaly injector, detector & evaluator
│   ├── api/                    # FastAPI routes, schemas & main app
│   ├── domain/                 # SQLAlchemy models & rule engine
│   ├── generator/              # Deterministic synthetic data generator
│   ├── ledger/                 # Append-only transaction ledger & lots
│   ├── reports/                # Manifests, exporters & reproducibility
│   ├── services/               # Accrual, redemption, returns, expiry, tier services
│   ├── validation/             # 20-check validation suite
│   ├── cli.py                  # CLI command implementation
│   ├── config.py               # Paths, ports & seed defaults
│   └── db.py                   # Engine, session factory & pragmas
├── tests/
│   ├── anomalies/              # Anomaly detection & evaluation tests
│   ├── integration/            # API & service integration tests
│   ├── reproducibility/        # Two-run determinism tests
│   └── unit/                   # Rule calculations & boundary tests
├── dataset_manifest.json       # Dataset metadata & SHA-256 hashes
├── docker-compose.yml          # Containerized deployment config
├── evaluation_metrics.json     # Anomaly evaluation metrics
├── ground_truth.csv            # Anomaly ground truth (CSV)
├── ground_truth.json           # Anomaly ground truth (JSON)
├── pyproject.toml              # Build & dependency configuration
├── README.md                   # Project documentation
├── reproducibility_report.json # Reproducibility report
├── source_manifest.json        # Generator source manifest
├── validation_report.md        # Validation markdown report
└── validation_summary.json     # Validation JSON report
```

---

## License

This project is licensed under the MIT License.\n