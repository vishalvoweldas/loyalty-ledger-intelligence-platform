1. Product Requirements Document (PRD)
1.1 Product overview
Product name: Loyalty Ledger Intelligence Platform

Product type: End-to-end business workflow application, synthetic data factory, auditable transaction ledger, and data-quality evaluation platform.

Problem being solved: Businesses award loyalty points when customers shop. Those points may subsequently be spent, reversed after a return, or expire. If different systems calculate points differently, the customer's displayed balance can disagree with the actual transaction history.

The product must make every change traceable to its business reason and allow an operations manager to determine whether the loyalty system is working correctly.
1.2 Business objectives
The product must:
- Maintain an accurate, auditable record of every points movement.
- Calculate points from eligible net spending according to configured rules.
- Prevent customers from redeeming more points than they have available.
- Reverse points when an order or part of an order is returned.
- Expire eligible points without expiring them more than once.
- Calculate tier progression from qualifying spending rather than the wrong spending measure.
- Generate large, realistic, reproducible datasets.
- Deliberately introduce known anomalies into a separate evaluation dataset.
- Produce reports that quantify correctness, failures, and data quality.
1.3 Who will use it?
User	What they need to do
Customer	View points balance, earning history, redemptions, returns, and tier status.
Store or warehouse operator	Process orders, returns, refunds, and eligible points adjustments.
Merchandising/e-commerce analyst	Configure earning rules, inspect order eligibility, and analyze customer and tier performance.
Operations manager	Investigate exceptions, review reconciliation reports, and track system health.
Data engineer or evaluator	Generate datasets, run validation, inspect ground truth, and verify reproducibility.

1.4 What is in scope?
Must have

- Data generation at the required scale: 20,000 customers, 100,000 orders, and 300,000 points transactions.
- All ten required business entities, with appropriate primary and foreign keys.
- Points accrual, redemption, returns, reversals, expiry, and tier progression.
- Immutable ledger entries and explicit event history.
- Five named anomaly scenarios with ground-truth labels.
- Reconciliation, validation, reporting, and downloadable exports.
- Fixed-seed reproducibility, automated tests, and documentation.
  
  Should have
- A dashboard for balances, tiers, ledger activity, and anomalies.
- Customer and order search.
- A review queue with anomaly severity and supporting evidence.
- Configurable data-generation scale and business rules.
- A controlled simulation of concurrent redemption requests.

Dashboard and review-queue behavior (required for the first usable release):
- Home dashboard: dataset/run status, ledger health, reconciliation status, tier distribution, points accrued/redeemed/reversed/expired, and anomaly counts by type and severity.
- Customer search/detail: account status, current and historical tiers, stored and ledger-derived balances, point lots, and chronological transaction history.
- Order search/detail: line-level amounts, eligibility, returns, accruals, and reversal links.
- Ledger filters: account, transaction type, date range, status, source reference, and correlation ID.
- Anomaly queue filters: issue type, severity, review status, and affected entity. Each finding shows the affected record, expected versus actual result, evidence, detection time, and related records.
- Dataset-generation controls: seed, scale, anomaly-injection mode, and business-rule configuration; warn before replacing generated outputs.
- Validation, evaluation, reproducibility, and export pages link to generated reports and files.
- Clearly distinguish baseline-valid records from intentionally anomalous evaluation records in the UI and exports.
- Use pagination for large tables and display loading, empty, success, and error states.
- Reviewing or resolving an alert creates an append-only audit event containing actor (or synthetic operator), timestamp, status change, and notes. Do not edit the historical ledger transaction to resolve an alert.
  
  Not required for the first version
- Integration with real payment processors, live e-commerce platforms, or production customer databases.
- Real customer information or external personal data.
- A production deployment with real financial or loyalty liabilities.

1.5 Important design decisions
Before implementation, the build agent needs unambiguous rules. The following defaults make the solution testable. They should be configurable rather than buried in code.
Decision	Recommended default
Currency	INR for demonstration; store amounts in integer paise.
Points precision	Whole-number points.
Earning calculation	Eligible net merchandise spend × tier earning rate, rounded down to whole points.
Returns	Reverse the points originally awarded on the returned lines, proportional to the original allocation.
Redemption	Spend the oldest eligible points first, using earliest-expiry-first ordering.
Expiration	Expire remaining points on their lot's expiry date; never expire a lot twice.
Tier qualification	Sum qualifying, non-returned merchandise spend within a configured qualification window.
Audit history	Append new events; never edit or delete historical ledger entries to correct a mistake.
Anomaly injection	Keep baseline-valid data and intentionally anomalous records distinguishable.
Concurrent redemption	Execute requests against a locked or atomic balance/lot allocation; reject any request that exceeds available points.

Important: These are recommended defaults because the business problem does not specify actual rates, redemption values, expiry duration, or tier thresholds. Antigravity should document them and make them configurable.

Required initial policy defaults (configurable, versioned, and documented):
- Eligible merchandise spend is the line-item amount after line-level and order-level discounts allocated proportionally to eligible lines. Exclude tax and shipping from points accrual and tier qualification unless a versioned rule explicitly says otherwise.
- Use integer paise for money and integer points. Use floor rounding for points; document order-level discount allocation and any fractional-paise handling.
- A return reverses points originally awarded to the returned quantity/eligible line allocation, capped at the remaining un-reversed award for that source accrual. Do not suppress a reversal because points have already been spent; record it and flag resulting debt/exception.
- Redemption order: earliest expiry first, then earliest accrual time, then stable lot ID as deterministic tie-breakers. Default to all-or-nothing; reject if the full amount is unavailable. Partial redemption may be configurable but must be explicit.
- Points are redeemable only when their lot is unexpired, unspent, not reversed, and not reserved. Reservations must be represented explicitly and not deducted twice from the signed ledger balance.
- Default expiry duration: 365 days after accrual. Make it configurable by effective-dated rule and document the business timezone and end-of-day convention.
- Use a fixed simulation clock for generated data. Store timestamps in UTC in the database and exports, and document the business timezone used to interpret date-only events.
- Tier qualification uses qualifying net merchandise spend after discounts and returns, excluding cancelled orders, tax, and shipping by default, over a rolling 12-month window. Define recalculation boundaries and record effective timestamps in tier history.
- Approved redemptions must have negative ledger movements and lot-allocation rows summing exactly to approved points. Rejected attempts remain auditable but must not create successful redemption movements.
- The exact full-dataset transaction count of 300,000 includes anomalous points transactions. Reserve and document a portion for injected transaction anomalies; non-transaction anomalies must not change the count. Report baseline and injected counts separately.
2. End-to-end business workflow
Think of this as the complete journey of loyalty points, from the moment a customer places an order until the points are redeemed, returned, expired, or audited.
Step 1 — Create master data

Customers, accounts, tiers, rules and rewards

Step 2 — Process orders

Orders, line items, discounts, payments and eligibility

Step 3 — Accrue points

Calculate eligible spend and record earning entries

Step 4 — Manage the points lifecycle

Redeem · Return · Reverse · Expire · Upgrade tier

Step 5 — Reconcile and audit

Recalculate balances, verify references and detect violations

Step 6 — Report and export

Dashboard, anomaly queue, ground truth, CSV/JSON/SQL and validation reports


Example: one customer's points lifecycle
Assume a customer purchases eligible merchandise worth ₹5,000, with a rule awarding 1 point per ₹100 of eligible spending.
Event	Points movement	Running balance
Initial balance	0	0
Earn points on purchase	+50	50
Redeem a reward	-20	30
Return half the eligible purchase	-25	5
Remaining points expire	-5	0

This example assumes the return reverses half of the original earned points, and the expiry event targets only the five points remaining in the original lot. Actual return and expiry outcomes depend on the configured rules and event ordering.

Every row should be a separate, traceable ledger entry. The balance should be calculated from the entries, not independently generated or manually overwritten.
3. Functional requirements
FR-01: Master data management
Create the parent records before generating dependent records.
- Customer: A synthetic customer profile.
- LoyaltyAccount: The account holding the customer's points.
- Tier: The membership level and its qualification thresholds.
- Rule: The earning, redemption, reversal, or expiry policy.
- Reward: A benefit that customers can redeem.
Every customer should have one loyalty account in the baseline dataset. A tier or earning rule should be associated with the appropriate account or transaction using explicit IDs and effective dates.
FR-02: Order processing
Generate orders and their order lines only after customers and accounts exist.

An order should contain:
- Order ID, customer ID, order date, status and currency.
- Merchandise subtotal, discounts, tax, shipping, and net amounts.
- One or more order lines, each with quantity, unit price, discount, eligible spend and return quantity.
The order total must equal the sum of its line-level calculations, subject to the documented tax and shipping policy.
FR-03: Points accrual
For each eligible order, calculate points using the applicable earning rule.

Example:
\[
\text{Earned Points}
=
\left\lfloor
\frac{\text{Eligible Net Spend}}{\text{Spend per Point}}
\right\rfloor
\]

For a rule of ₹100 per point and eligible spend of ₹5,099, the customer receives 50 points.

Do not award points on cancelled orders or ineligible items. Avoid double-awarding points when the same order event is processed twice.
FR-04: Redemptions
When a customer redeems a reward:
1. Find the customer's available point lots.
2. Exclude points that have already been spent, reversed, or expired.
3. Verify the requested amount against available points.
4. Allocate the redemption to eligible lots.
5. Record the redemption and the corresponding negative ledger entries.
6. Reject requests that exceed available points, with an explicit reason.
The system must handle two simultaneous redemption requests safely. If a customer has 100 points and two requests attempt to redeem 70 each, at most one may succeed if they compete for the same initial balance. The other must be rejected or limited according to a documented partial-redemption policy.
FR-05: Returns and reversals
Returns must reference the original order and the original accrual entries.

For a partial return, reverse only the earned points attributable to the returned items. For a full return, reverse all remaining earned points attributable to the returned merchandise, while respecting prior reversals.

If the points were already spent before the return, record the reversal even if it creates a negative available balance. Flag the resulting debt or exception instead of rewriting the original history or silently ignoring the reversal.
FR-06: Point expiry
Each accrual creates an identifiable point lot, with an expiry date based on the applicable rule.

When a lot expires:
- Expire only its remaining eligible points.
- Record the expiry event and the points removed.
- Prevent a second expiry from removing the same points again.
- Preserve the original accrual and any previous redemption or reversal records.
FR-07: Tier progression
Tier status must follow configured qualifying-spend thresholds.

Example starter tiers:
Tier	Qualifying spend during the rolling 12-month window	Earning rate
Bronze	₹0–₹9,999.99	1 point per ₹100
Silver	₹10,000–₹49,999.99	2 points per ₹100
Gold	₹50,000 and above	3 points per ₹100

These are illustrative thresholds. Implement them as configurable reference data.

Qualifying spend should be calculated using the documented treatment of discounts, returns, cancelled orders, taxes, shipping, and the qualification period. Tier changes should be recorded as historical events with effective dates.
FR-08: Immutable audit trail
The system must not delete or rewrite historical points transactions when a correction is needed.

For example, if an accrual was incorrect, create a reversal referencing the original accrual and, if appropriate, a separate corrected accrual.

Every ledger entry should include:
- Unique transaction ID.
- Loyalty account ID.
- Transaction type and signed points amount.
- Event timestamp and business-effective timestamp.
- Reference to the source order, redemption, expiry, or original transaction where applicable.
- Applied rule/version.
- Reason code, processing status and correlation ID.
This gives the operations team an explainable answer to: What changed, why did it change, and which business event caused it?
4. Data model and entity relationships
The system must contain all ten entities specified in the problem statement. A relational database is appropriate because relationships and integrity are central to the requirements.
4.1 Required entities

Customer

The synthetic shopper.

Primary key: `customer_id`




LoyaltyAccount

The customer's loyalty membership and current status.

Primary key: `account_id`




Tier

The configured membership levels.

Primary key: `tier_id`




Rule

The versioned earning, expiry, redemption and qualification policies.

Primary key: `rule_id`




Order

The customer purchase and its financial totals.

Primary key: `order_id`




OrderLine

The products and quantities purchased or returned.

Primary key: `order_line_id`




PointsTransaction

The immutable ledger of points movements.

Primary key: `transaction_id`




Reward

A reward available for redemption.

Primary key: `reward_id`




Redemption

A customer's attempt to redeem points for a reward.

Primary key: `redemption_id`




ExpiryBatch

A run that processes eligible point lots reaching expiry.

Primary key: `expiry_batch_id`




4.1.1 Additional implementation entity: PointLot

PointLot is an additional implementation table supporting the lot-based points lifecycle. It does not replace any of the ten required core entities.

A PointLot represents an identifiable allocation of points created by an accrual transaction and supports earliest-expiry-first redemption, partial returns, and expiry of only the unspent remainder.

Primary key: `lot_id`

Required/recommended fields:
- `lot_id` (unique string, required).
- `account_id` (foreign key to LoyaltyAccount).
- `source_transaction_id` (foreign key to the original accrual PointsTransaction).
- `original_points` (positive integer).
- `remaining_points` (integer from zero to original_points).
- `accrued_at` and `expires_at` (timestamps; expires_at must follow accrued_at).
- `status` (OPEN/EXHAUSTED/EXPIRED/CLOSED).
- `rule_id` (foreign key to the applicable versioned Rule, where applicable).

Remaining points must be derivable from the original accrual and linked redemption, reversal, and expiry allocations. If a cached `remaining_points` value is stored for performance, it must be reconciled against those allocations. Do not edit a lot to conceal a ledger discrepancy.

4.2 Relationship rules
Relationship	Cardinality	Meaning
Customer → LoyaltyAccount	1:1 in baseline	Each customer has one account.
Tier → LoyaltyAccount	1:N over time	Many accounts can occupy a tier; an account can have multiple historical tier assignments.
Customer → Order	1:N	A customer can place many orders.
Order → OrderLine	1:N	An order contains one or more lines.
LoyaltyAccount → PointsTransaction	1:N	An account has many ledger entries.
Order → PointsTransaction	1:N, optional	An order can produce accruals and reversals.
Reward → Redemption	1:N	A reward can be redeemed many times.
LoyaltyAccount → Redemption	1:N	An account can have many redemption attempts.
ExpiryBatch → PointsTransaction	1:N, optional	An expiry batch can produce many expiry entries.
PointsTransaction → PointsTransaction	1:N, optional	One original accrual can be referenced by one or more correction or reversal entries.
PointsTransaction → PointLot\t1:N\tAn accrual transaction can create one or more identifiable point lots.
PointLot → TransactionLotAllocation\t1:N\tA lot can fund multiple redemptions, reversals, or expiry movements through allocation records.

For complex relationships, use bridge tables rather than comma-separated IDs. Recommended additional tables include PointLot, AccountTierHistory, AccountRuleAssignment, TransactionLotAllocation, OrderReturn, RedemptionAttempt, and AuditEvent. PointLot is required for the lot-based lifecycle described in this PRD; the other tables should be implemented where needed to preserve history, allocation traceability, and rejected attempts.

These additional tables make it possible to track historical tiers, rule assignments, which point lots funded a redemption, partial returns, rejected attempts, and operational actions.
4.3 ID conventions
Use the exact requested prefixes and zero-padded counters.
Entity	Example
Customer	CUS-000001
Loyalty account	LOY-CUS-000001
Order	ORD-2026-000001
Points transaction	PTS-2026-00000001
Redemption	RDM-2026-000001
Expiry batch	EXP-2026-000001

The LOY-<customer-id> format is mandatory for loyalty accounts. All identifiers must be immutable and identical across the database, CSV files, JSON files, and SQL seed data.

Use an explicit sequence or deterministic ID allocator so that reproducibility does not depend on database-generated IDs or nondeterministic processing order.
4.4 Data dictionary requirements
Every field needs a documented definition, data type, required/optional status, allowed values, units, uniqueness, and validation rule.

The following is the minimum dictionary specification that Antigravity should implement. It is not enough to document only the primary keys.
Entity	Required fields and recommended validations
Customer	customer_id (unique string, required); created_at (timestamp); region (allowed synthetic regions); status (ACTIVE/INACTIVE). No real personal information.
LoyaltyAccount	account_id (unique string, required); customer_id (unique FK); current_tier_id (FK); status (ACTIVE/SUSPENDED/CLOSED); opened_at, closed_at (timestamps); cached_balance_points (integer, reconciles to ledger).
Tier	tier_id (unique string); tier_name (unique); min_qualifying_spend (currency minor units); earning_rate or spend_per_point; effective_from, effective_to; status. Thresholds must be nonnegative and nonoverlapping where required.
Rule	rule_id (unique); rule_type (ACCRUAL/REDEMPTION/EXPIRY/TIER); version; effective_from, effective_to; parameters (validated JSON or typed columns); status. Active versions must be unambiguous for the event date.
Order	order_id (unique); customer_id (FK); order_date; status (PENDING/COMPLETED/CANCELLED/PARTIALLY_RETURNED/RETURNED); currency; subtotal_minor, discount_minor, tax_minor, shipping_minor, net_merchandise_minor, total_minor. All monetary values are integer minor units.
OrderLine	order_line_id (unique); order_id (FK); sku; quantity; unit_price_minor; discount_minor; eligible_spend_minor; returned_quantity. Quantities and monetary values must be valid, and returned quantity cannot exceed ordered quantity.
PointsTransaction	transaction_id (unique); account_id (FK); transaction_type (ACCRUAL/REDEMPTION/REVERSAL/EXPIRY/ADJUSTMENT); points_delta (signed integer); event_at; effective_at; source_type; source_id; original_transaction_id (optional self-FK); rule_id (optional FK where applicable); status; idempotency_key; reason_code; correlation_id. No silent updates or deletes.
Reward	reward_id (unique); reward_name; points_cost (positive integer); status (ACTIVE/INACTIVE); effective_from, effective_to; optional inventory_quantity (nonnegative integer).
Redemption	redemption_id (unique); account_id (FK); reward_id (FK); requested_points; approved_points; status (PENDING/APPROVED/REJECTED/CANCELLED); requested_at; processed_at; rejection_reason; idempotency_key. Approved points must match the associated ledger entries.
ExpiryBatch	expiry_batch_id (unique); run_at; cutoff_at; status (STARTED/COMPLETED/FAILED); lots_scanned; points_expired; idempotency_key. Re-running a batch must not duplicate expiry movements.

Additional documentation rules:
- Store money in integer minor units to avoid floating-point rounding errors.
- Use ISO 8601 timestamps and a documented business timezone.
- Use explicit nullable fields and define which statuses permit them.
- Add effective dates and historical versions for business rules.
- Record state changes as events instead of overwriting previous values.
- Validate every foreign key and every relationship join.
- Ensure all baseline data is valid before inserting deliberately labelled anomalies.
5. Synthetic data generation strategy
The generator should create a realistic business world, not a collection of unrelated random CSV rows.
5.1 Required data volumes
20,000
Customers


100,000
Orders


300,000
Points transactions


5+
Required anomaly types



5.2 Generation sequence
The correct sequence is essential because child records depend on parent records.
1. Generate tiers, rule versions and rewards.
2. Generate customers and their loyalty accounts.
3. Generate 100,000 orders and their order lines.
4. Calculate eligible spending and the applicable tier/rule at the event date.
5. Generate points accrual transactions and lot allocations.
6. Generate redemption requests, including successful and rejected attempts.
7. Generate full and partial returns, then calculate the corresponding reversal entries.
8. Generate expiry batches based on actual lot expiry dates.
9. Recalculate qualifying spend, tier history, and expected balances.
10. Validate the baseline, then inject documented anomalies into designated records.
11. Generate ground truth, exports, metrics, checksums and the final validation report.
5.3 Make the data realistic
The generator should introduce meaningful variation while keeping the underlying logic valid:
- Customers should place different numbers of orders, with a realistic mix of occasional and frequent shoppers.
- Order values should vary, with some large orders and many smaller ones.
- Order statuses should include completed, cancelled, returned and partially returned orders.
- Point balances should vary by customer and account age.
- Redemptions should include successful attempts, insufficient-balance rejections, duplicate requests and competing requests.
- Expiry should vary based on accrual dates and rule versions.
- Tier distribution should reflect customer activity and the configured thresholds.
- Rule changes should have effective dates so historical transactions use the rules that were applicable at the time.
- Returns should include both partial and full returns, and some returned orders should have points that were already redeemed.
- Baseline data should be internally consistent before any anomaly injection takes place.
5.4 Fixed-seed reproducibility
Use 20261022 as the default random seed and expose the scale as a parameter.

Example generator commands:
# Small starter dataset
python -m loyalty_ledger generate \
  --scale starter \
  --seed 20261022

# Full requested dataset
python -m loyalty_ledger generate \
  --scale full \
  --seed 20261022

# Reproducibility verification
python -m loyalty_ledger reproduce \
  --scale starter \
  --seed 20261022


These are proposed command interfaces; Antigravity must implement them and document the actual supported syntax.

The same seed and configuration must produce identical logical records, row counts, and content checksums. Avoid random values derived from uncontrolled execution order, system timestamps, or concurrent processing. Where timestamps are generated, use a fixed simulation clock and deterministic event ordering.
6. Required anomaly and exception scenarios
This is one of the most important parts of the assignment. The product must distinguish between valid business behavior and intentionally incorrect records.
ID	Scenario	Expected detection or decision
AN-001	Stored balance differs from ledger sum	Recompute the balance from ledger entries and flag the mismatch.
AN-002	Redemption exceeds available points	Reject the transaction; flag any injected accepted redemption that violates the balance constraint.
AN-003	Returned order keeps all earned points	Identify missing or insufficient reversals relative to returned eligible merchandise.
AN-004	Points expire twice	Detect duplicate expiry allocations or repeated expiry movements for the same lot and points.
AN-005	Tier uses gross rather than qualifying spend	Recalculate qualifying spend and compare it with the assigned tier.

How to inject anomalies correctly
For each scenario, the generator must:
1. Generate a valid underlying customer, account, order, or transaction.
2. Identify the specific business rule that will be violated.
3. Introduce one controlled defect.
4. Assign a stable anomaly ID and issue_type.
5. Record the affected entity and record ID.
6. Store the expected detector result and ground-truth label separately.
7. Verify that the detector identifies the anomaly.
8. Check that unrelated records remain valid.
For example, AN-001 must not corrupt the customer's orders, account identity, and foreign keys merely to create a balance mismatch. Only the intended balance-related defect should be introduced.

Ground truth must not be used as an input to the detection logic. It is the answer key used to evaluate the detector after detection has run.
Additional exception coverage
Beyond the five mandatory scenarios, include:
- Duplicate accrual attempts for the same order.
- Returns exceeding ordered quantities.
- Reversal transactions referencing nonexistent or invalid original accruals.
- Redemption requests replayed with the same idempotency key.
- Expiry batches rerun after partial failure.
- Tier boundaries at exactly the threshold and just below it.
- Transactions occurring near rule effective-date boundaries.
- Concurrent redemption attempts against the same account.
- Accounts with zero balance and accounts with a negative available balance following a return.
- Cancelled orders that incorrectly receive accruals.
These should have documented expected outcomes. Some should be valid rejected requests rather than corrupted persisted transactions.
7. Validation, acceptance criteria and measurable outputs
7.1 Non-negotiable acceptance criteria
Check	Required outcome
Customer count	Exactly 20,000 in the full dataset.
Order count	Exactly 100,000 in the full dataset.
Points transaction count	Exactly 300,000 in the full dataset.
Primary keys	No duplicates.
Foreign keys	100% valid for baseline records and valid relationships in all records unless a specific FK anomaly is explicitly part of the test.
Baseline balance reconciliation	100% match between expected ledger-derived balance and stored balance.
Reversal traceability	Every reversal references a valid original transaction.
Expiry idempotency	Reprocessing an already completed expiry must not create duplicate point removals.
Redemption safety	No successful redemption exceeds the available points at its atomic processing point.
Tier correctness	Baseline tiers match the configured qualifying-spend rules.
Ground-truth isolation	Ground truth is kept outside model/detector input features.
Reproducibility	Two runs with the same seed and configuration produce matching counts and checksums.
Anomaly coverage	All five required anomaly classes are present, labelled, and tested.

The full dataset's transaction count must be exactly 300,000, including the agreed treatment of anomalous transactions. If an anomaly changes the number of records, the generator should compensate through controlled record allocation or explicitly document the count policy.
7.2 Metrics to display
Data and ledger health
Primary-key uniqueness
100%
Required for all entities

Baseline FK integrity
100%
No orphaned references

Balance reconciliation
100%
All valid baseline accounts

Expiry idempotency
100%
No duplicate expiry movements



Detection and evaluation
- Precision, recall and F1 score for anomaly detection.
- Anomaly counts by issue type and severity.
- False-positive and false-negative counts.
- Successful versus rejected redemption attempts.
- Number and value of points accrued, redeemed, reversed and expired.
- Tier distribution and tier-transition counts.
- Percentage of records with valid joins.
- Dataset generation duration and validation duration.
- Per-file row counts and SHA-256 checksums.

These figures are acceptance targets, not claimed test results. Antigravity must calculate and report the actual results from its executed tests.

For the deliberately labelled test anomalies, target 100% detection on the mandatory scenarios. Report precision, recall, and F1 against the separate ground truth rather than reporting accuracy alone.
7.3 Core accounting equations
For an account, the signed ledger balance is:
\[
B_{\text{ledger}}=\sum_{i=1}^{n}\Delta P_i
\]

where each \(\Delta P_i\) is a signed points movement.

The reconciliation check is:
\[
B_{\text{stored}}=B_{\text{ledger}}
\]

For available points, distinguish the signed ledger balance from the amount that is eligible to redeem:
\[
B_{\text{available}}=
B_{\text{ledger}}-
P_{\text{ineligible or reserved}}
\]

The exact treatment of reservations and negative balances must be documented. Expiry and reversal entries must not be subtracted a second time if they are already included in the signed ledger balance.

For every transaction, the validator should check its source reference, idempotency, applicable business rule, lifecycle status, and effect on the account balance.
8. Desired outputs and deliverables
The finished application is only one deliverable. The full solution must also produce the following files and evidence.
01

Working application

A runnable web dashboard, backend services, database schema, and accessible API endpoints for the loyalty workflow.



02

Synthetic datasets

CSV and JSON exports for all core entities, PointLot, bridge tables, transaction events, and audit history.



03

SQL seed package

DDL/schema migrations, indexes, constraints, and a reproducible SQL seed or import mechanism.



04

Data dictionary

Field-level definitions, types, nullability, enums, units, uniqueness, and validation rules.



05

Ground truth

A separate ground_truth.csv and ground_truth.json with known anomaly labels and expected decisions.



06

Validation reports

Machine-readable validation_summary.json and human-readable validation_report.md with actual pass/fail results.



07

Reproducibility evidence

Two-run manifests with seed, parameters, counts, checksums, and any documented exclusions.



08

Tests

Unit, integration, lifecycle, anomaly detection, database integrity, and reproducibility tests.



09

Documentation

README, architecture diagram, entity-relationship diagram, business rules, API documentation, and run instructions.



10

Source manifest

Manifest of synthetic data provenance, generation version, rule configuration, and any external reference data and licenses.



11

Demo scenarios

A walkthrough demonstrating accrual, redemption, partial return, expiry, tier progression, and all five anomalies.



12

Evaluation metrics

Anomaly detection metrics, reconciliation results, dataset quality statistics, and performance measurements.



API contract requirements (required):
- Publish an OpenAPI specification and interactive API documentation generated from the implemented API.
- Include endpoints for customer/account lookup, order lookup, ledger history, accrual processing, redemption requests, returns, expiry-batch execution/status, tier history, reconciliation, anomaly detection/review, dataset generation, validation, evaluation metrics, and export downloads.
- Document HTTP method and path, access assumptions, request/response schemas, status codes, validation errors, and idempotency/concurrency behavior where relevant.
- Use consistent error responses with a stable error code, human-readable message, and relevant field or resource reference.
- Do not claim an endpoint is implemented unless it is available and covered by an automated test.
- If development-only access controls are used, document the limitation and do not present them as production security.

8.1 Recommended implementation baseline

Unless the project owner explicitly chooses another stack, use this local-first baseline:
- Backend: Python 3.12, FastAPI, Pydantic, SQLAlchemy, and Alembic.
- Database: PostgreSQL through Docker Compose.
- Frontend: React with TypeScript and a maintained component library.
- Testing: pytest for unit, integration, lifecycle, anomaly, and reproducibility tests; frontend tests for critical user flows.
- Packaging: pyproject.toml, .env.example, Docker Compose, database migrations, and documented startup commands.
- No paid cloud service or external production data source is required. The solution must run locally with documented prerequisites.
- If another stack is selected, document the reason and preserve every functional and acceptance requirement.

8.2 Additional acceptance criteria

- PointLot remaining-point totals reconcile to original accruals minus valid lot allocations.
- Every successful redemption is traceable to its negative PointsTransaction entries and TransactionLotAllocation rows.
- Every expiry movement identifies the lot and batch; retrying a completed batch is idempotent.
- Every return is traceable to original order lines and accruals; baseline returned quantities never exceed purchased quantities.
- Dashboard totals reconcile to the same underlying records used by validation reports.
- Required API endpoints have automated tests for successful and representative failure cases.
- Generation, validation, import, and export failures are clearly reported without false success messages.
- README commands cover installation, environment setup, migrations, starter/full generation, tests, startup, export, and reproducibility verification.
- The final completion report marks every acceptance criterion PASS, FAIL, or NOT VERIFIED and links it to test/report evidence.

Suggested output directory
loyalty-ledger-platform/
├── README.md
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── docs/
│   ├── PRD.md
│   ├── architecture.md
│   ├── data_dictionary.md
│   ├── business_rules.md
│   ├── entity_relationships.md
│   └── api.md
├── src/
│   ├── generator/
│   ├── domain/
│   ├── services/
│   ├── ledger/
│   ├── reconciliation/
│   ├── anomaly_detection/
│   ├── validation/
│   └── api/
├── frontend/
├── db/
│   ├── migrations/
│   └── seeds/
├── data/
│   ├── starter/
│   ├── full/
│   ├── ground_truth/
│   └── manifests/
├── exports/
│   ├── csv/
│   ├── json/
│   └── sql/
├── reports/
│   ├── validation_report.md
│   ├── validation_summary.json
│   ├── evaluation_metrics.json
│   └── reproducibility_report.json
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── lifecycle/
│   ├── anomalies/
│   └── reproducibility/
└── scripts/
    ├── generate_data.py
    ├── validate_data.py
    ├── export_data.py
    └── verify_reproducibility.py