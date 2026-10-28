# Configurable Business Rules Specification

## 1. Overview
The Loyalty Ledger Intelligence Platform is governed by a versioned, configuration-driven business rule engine. Business policies are never hardcoded inside individual services. Every rule has an explicit `effective_from` and `effective_to` timestamp, and historical transactions are evaluated against the rule active at the time of the event.

---

## 2. Core Rule Definitions

### BR-01: Points Accrual Calculation
- **Rule Type**: `ACCRUAL`
- **Formula**:
  $$\text{Earned Points} = \left\lfloor \frac{\text{Eligible Net Spend (paise)}}{\text{Spend Per Point (paise)}} \right\rfloor$$
- **Default Parameters**:
  - `tax_eligible`: `false` (Tax charges do not earn points).
  - `shipping_eligible`: `false` (Shipping fees do not earn points).
  - `discount_treatment`: `PROPORTIONAL` (Order-level discounts reduce eligible spend proportionally across lines).
  - `rounding_mode`: `FLOOR` (Strict downward truncation to whole points).
  - `cancelled_orders_earn`: `false` (No points awarded on cancelled orders).
  - `duplicate_accrual_policy`: `IDEMPOTENT_REJECT` (Duplicate accrual calls with the same source order ID or idempotency key return the existing transaction).

### BR-02: Default Tiers & Earning Rates
- **Rule Type**: `TIER`
- **Default Tiers**:
  1. **Bronze**:
     - Qualifying spend: ₹0 – ₹9,999.99 (0 to 999,999 paise).
     - Earning rate: 1 point per ₹100 spend (spend per point = 10,000 paise).
  2. **Silver**:
     - Qualifying spend: ₹10,000 – ₹49,999.99 (1,000,000 to 4,999,999 paise).
     - Earning rate: 2 points per ₹100 spend (spend per point = 5,000 paise).
  3. **Gold**:
     - Qualifying spend: ₹50,000+ (5,000,000+ paise).
     - Earning rate: 3 points per ₹100 spend (spend per point = 3,333 paise).
- **Qualification Window**:
  - Rolling 12 calendar months from the evaluation date.
  - Calculation: $\sum \text{Eligible Net Spend of Completed Orders} - \sum \text{Returned Eligible Spend}$.
  - Excludes cancelled orders, taxes, and shipping fees.
  - Threshold rule: Customer qualifies for the highest tier whose minimum threshold has been met.

### BR-03: Redemption Policy & Lot Allocation
- **Rule Type**: `REDEMPTION`
- **Default Parameters**:
  - `depletion_strategy`: `EARLIEST_EXPIRY_FIRST` (FIFO by lot expiry date).
  - `tie_breaker`: `EARLIEST_ACCRUAL_TIME`, followed by stable `lot_id`.
  - `all_or_nothing`: `true` (Redemption request is rejected if full requested points cannot be satisfied from available points).
  - `available_balance_definition`:
    $$B_{\text{available}} = \sum_{\text{lot} \in \text{OPEN}} \text{remaining\_points}(\text{lot})$$
    where lot is not expired, not exhausted, and belongs to an active account.
  - `concurrency_control`: Strict database-level row lock or atomic update on account / point lots. If competing requests arrive simultaneously, only the request with sufficient points succeeds; the other is rejected with `INSUFFICIENT_BALANCE`.

### BR-04: Returns & Points Reversals
- **Rule Type**: `REVERSAL`
- **Default Parameters**:
  - `reversal_basis`: `ORIGINAL_PROPORTIONAL` (Reversal is calculated in direct proportion to the returned items' eligible spend from the original order).
  - `maximum_reversal_cap`: Cannot reverse more points than originally accrued on the target order/lot.
  - `partial_returns`: Supported. Multiple partial returns are tracked incrementally.
  - `pre_spent_points_handling`: `ALLOW_NEGATIVE_WITH_DEBT_FLAG`. If points were already spent prior to the return, the reversal is still posted to the ledger, creating a negative ledger balance. The account status is tagged with an audit debt flag. The original accrual is never erased.

### BR-05: Point Expiry & Batch Idempotency
- **Rule Type**: `EXPIRY`
- **Default Parameters**:
  - `default_lot_validity_days`: `365` (1 year from accrual date).
  - `expiry_cutoff_policy`: Lots where $\text{expires\_at} \le \text{cutoff\_timestamp}$ and $\text{remaining\_points} > 0$.
  - `partial_spend_expiry`: Only the unspent remainder ($\text{remaining\_points}$) is expired.
  - `idempotency`: An expiry batch or re-run targeting the same cutoff date cannot expire a lot twice. Consecutive runs for the same batch ID or lot check current remaining points and yield 0 additional deductions.

---

## 3. Anomaly Rules & Criteria

| Anomaly ID | Issue Type | Definition | Detection Rule |
| :--- | :--- | :--- | :--- |
| **AN-001** | `BALANCE_MISMATCH` | `cached_balance_points` differs from the sum of signed points deltas $\sum \Delta P_i$ in `points_transactions`. | Flag if `account.cached_balance_points != sum(tx.points_delta)`. |
| **AN-002** | `EXCESSIVE_REDEMPTION` | A redemption was approved where `approved_points > available_balance` at time of execution. | Flag if redemption status is `APPROVED` but available unspent points at execution time were less than requested. |
| **AN-003** | `UNREVERSED_RETURN` | An order was returned (partially or fully) but no corresponding `REVERSAL` transaction was posted against the original accrual. | Flag if `order_returns` exists for an order without matching `points_transactions` of type `REVERSAL` referencing original accrual. |
| **AN-004** | `DUPLICATE_EXPIRY` | The same point lot received multiple expiry allocations or points expired exceed the unspent balance. | Flag if a lot has $>1$ allocation of type `EXPIRY` or total expired points $> \text{original\_points} - \text{redeemed} - \text{reversed}$. |
| **AN-005** | `GROSS_SPEND_TIER` | An account was assigned a higher tier based on gross total spend (including taxes, shipping, or returned goods) instead of qualifying net spend. | Flag if `account.current_tier_id` does not match tier calculated from net qualifying spend. |
