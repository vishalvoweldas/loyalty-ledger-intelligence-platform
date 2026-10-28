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

- [x] All 30 automated test cases pass (`pytest tests/ -v`) in the final reviewed repository snapshot.
- [x] All 20 validation checks pass in both baseline and evaluation modes (`ValidationEngine`).
- [x] Two-run reproducibility verification completed at both Starter and Full scales (`seed=20261022`).
- [x] Mathematical reconciliation of all 201,086 lot allocation rows against source business movements verified.
- [x] Ground-truth isolation confirmed via code audit of `AnomalyDetector`.
- [x] SQLite WAL non-blocking reads and serialized write safety benchmarked under concurrent load.
- [x] Personally performed a feature-by-feature, point-by-point manual walkthrough of the dashboard.
- [x] Checked the available dashboard sections, features, controls, and interactions, and verified whether they behaved as expected.
- [x] Reviewed the dashboard from a user's perspective in addition to running automated tests and backend validation.
- [x] Used manual dashboard verification to complement automated testing, since UI behavior and user-facing issues may not be fully covered by unit and integration tests.
- [x] Submission metadata verified: Author Vishal Voweldas, Repository: https://github.com/vishalvoweldas/loyalty-ledger-intelligence-platform.git

---

## 4. Dashboard Manual Verification

In addition to automated testing and backend validation, I personally performed a feature-by-feature, point-by-point walkthrough of the dashboard.

During this walkthrough, I checked the available dashboard sections, features, controls, and interactions and verified whether they behaved as expected. I reviewed the dashboard from the perspective of an end user to identify potential user-facing issues that might not be detected by automated unit or integration tests alone.

This manual verification was performed alongside the automated test suite, data validation checks, and other project verification activities. These are complementary forms of evidence: automated tests verify programmed test scenarios, validation checks assess data integrity, and manual dashboard testing checks the behavior and usability of the user-facing interface.

The verification statements above reflect the checks performed during development. Any known issues, limitations, or behaviors that could not be verified should be documented explicitly rather than described as passing.
