# AI Disclosure Statement: Loyalty Ledger Intelligence Platform

## Project Overview
- **Project Name**: Loyalty Ledger Intelligence Platform
- **Version**: 1.0.0
- **Author / Submitter**: Vishal Voweldas
- **Email**: vishalvoweldas67@gmail.com
- **Repository**: https://github.com/vishalvoweldas/loyalty-ledger-intelligence-platform.git
- **Submission Date**: 28 October 2026

---

## 1. Declarations of AI Tool Usage

In accordance with academic and project submission guidelines, this project utilized Artificial Intelligence tools during system development.

| AI Tool / Model | Interface / Platform | Primary Role & Scope | Human Review & Oversight |
| :--- | :--- | :--- | :--- |
| **Google DeepMind Antigravity (Gemini)** | Agentic IDE / Pair Programmer | Scaffolding domain models, drafting test suites, implementing initial service layer, generating synthetic data algorithms, and formatting documentation. | 100% of generated code, mathematical reconciliation formulas, and database transaction boundaries were inspected, audited, and debugged by human engineers. |

---

## 2. Specific Areas of AI Assistance

### A. Architectural Scaffolding & Domain Entities
- **AI Contribution**: Scaffolding SQLAlchemy 2.0 ORM models for the 19 domain and lifecycle tables based on `PRD.md`.
- **Human Verification**: Verified relational cardinalities, foreign key cascades, integer minor unit monetary fields (paise), signed points ledger delta conventions, and SQLite WAL pragmas.

### B. Business Rules & Financial Accounting Math
- **AI Contribution**: Drafting initial accrual, redemption, return reversal, and tier progression calculations.
- **Human Verification**: Fixed mathematical edge cases including floor division ($\lfloor \text{eligible\_spend} / 10000 \rfloor$), exclusion of non-merchandise fees (taxes, shipping, gift cards), and FIFO lot-splitting arithmetic across multiple lots.

### C. Concurrency & SQLite Transaction Isolation
- **AI Contribution**: Identified initial `sqlite3.OperationalError: database is locked` exceptions during concurrent API read benchmarks.
- **Human Verification**: Architected the selective write transaction pattern (`begin_write_transaction`) using `sqlite_immediate: True`, eliminating premature commits, and configuring `PRAGMA busy_timeout = 30000` to guarantee serialized writes alongside non-blocking WAL reads.

### D. Anomaly Detection & Ground-Truth Isolation
- **AI Contribution**: Implemented detector rules for AN-001 through AN-005 and evaluation metric computation (Precision, Recall, F1).
- **Human Verification**: Enforced strict ground-truth isolation, ensuring `AnomalyDetector` operates purely on operational tables without reading `ground_truth_records` or ground-truth export files.

### E. Automated Test Suite
- **AI Contribution**: Scaffolding unit and integration tests across `tests/unit/`, `tests/integration/`, `tests/reproducibility/`, and `tests/anomalies/`.
- **Human Verification**: Executed and validated all 26 automated tests, resolving test client database state isolation and FK constraint order issues.

---

## 3. Human Verification Checklist

- [x] All 26 automated test cases pass (`pytest tests/ -v`).
- [x] All 20 validation checks pass in both baseline and evaluation modes (`ValidationEngine`).
- [x] Two-run reproducibility verification verified at both Starter and Full scales (`seed=20261022`).
- [x] Mathematical reconciliation of all 201,086 lot allocation rows against source business movements verified.
- [x] Ground-truth isolation confirmed via code audit of `AnomalyDetector`.
- [x] SQLite WAL non-blocking reads and serialized write safety benchmarked under concurrent load.
- [x] Submission metadata verified: Author Vishal Voweldas (vishalvoweldas67@gmail.com), Repository: https://github.com/vishalvoweldas/loyalty-ledger-intelligence-platform.git
