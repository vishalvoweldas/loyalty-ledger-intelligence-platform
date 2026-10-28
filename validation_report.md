# Validation Report: Loyalty Ledger Intelligence Platform

- **Validation Timestamp**: 2026-10-28T16:18:43.645255+00:00
- **Validation Mode**: evaluation
- **Overall Status**: **PASSED**
- **Checks Passed**: 20 / 20
- **Checks Failed**: 0

| # | Check Name | Entity | Status | Severity | Details |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | PRIMARY_KEY_UNIQUENESS | Multiple | PASS | NONE | Customer dups: 0, Order dups: 0, Transaction dups: 0 |
| 2 | FOREIGN_KEY_INTEGRITY | Multiple | PASS | NONE | Orphaned orders: 0, Orphaned tx: 0, Orphaned accounts: 0, Orphaned lots: 0 |
| 3 | REQUIRED_FIELDS_AND_NULLABILITY | Multiple | PASS | NONE | Null customer names: 0, Null order totals: 0, Null tx deltas: 0 |
| 4 | ENUM_AND_ALLOWED_VALUES | Multiple | PASS | NONE | Invalid regions: 0, Invalid tx types: 0, Invalid lot statuses: 0 |
| 5 | DATE_ORDERING | PointLot | PASS | NONE | Lots with expires_at <= accrued_at: 0 |
| 6 | RULE_EFFECTIVE_DATE_CONSISTENCY | Rule | PASS | NONE | Rules with valid effective dates: 5/5 verified |
| 7 | ORDER_ARITHMETIC | Order | PASS | NONE | Orders with mismatched arithmetic: 0 (all 2,500 verified) |
| 8 | RETURN_QUANTITY_ARITHMETIC | OrderLine | PASS | NONE | Lines with returned_quantity > quantity: 0 (all 4,941 verified) |
| 9 | POINTS_ACCRUAL_CALCULATIONS | PointsTransaction | PASS | NONE | Points accrual floor calculations verified across all accrual transactions. |
| 10 | REVERSAL_REFERENCES_AND_AMOUNTS | OrderReturn | PASS | WARNING | Evaluation verified: 0 unexpected missing reversals. Exactly 2 intentional AN-003 returns confirmed against ground truth. |
| 11 | BALANCE_RECONCILIATION | LoyaltyAccount | PASS | WARNING | Evaluation verified: 0 unexpected balance discrepancies. Exactly 2 intentional AN-001 accounts confirmed against ground truth. |
| 12 | POINT_LOT_ALLOCATIONS | PointLot | PASS | WARNING | Evaluation verified: 0 unexpected allocation discrepancies. Exactly 8 intentional AN-004 lots confirmed against ground truth. |
| 13 | REDEMPTION_AVAILABILITY_AND_SAFETY | Redemption | PASS | WARNING | Evaluation verified: 0 unexpected overdrawn redemptions. Exactly 2 intentional AN-002 redemptions confirmed against ground truth. |
| 14 | EXPIRY_IDEMPOTENCY | TransactionLotAllocation | PASS | WARNING | Evaluation verified: 0 unexpected duplicate expiries. Exactly 8 intentional AN-004 lots confirmed against ground truth. |
| 15 | TIER_QUALIFICATION_RULES | LoyaltyAccount | PASS | WARNING | Evaluation verified: 0 unexpected tier mismatches. Exactly 2 intentional AN-005 gross spend tier overrides confirmed against ground truth. |
| 16 | LIFECYCLE_TRANSITION_LEGALITY | Order | PASS | NONE | Orders with invalid status: 0 (all 2,500 orders valid) |
| 17 | IDEMPOTENCY_KEY_UNIQUENESS | PointsTransaction | PASS | NONE | Duplicate idempotency keys: 0 (all 7,500 keys unique) |
| 18 | GROUND_TRUTH_INTEGRITY | GroundTruthRecord | PASS | INFO | Total labelled anomalies in ground truth: 16 (all 5 classes AN-001 through AN-005 verified) |
| 19 | ENTITY_ROW_COUNTS | Multiple | PASS | INFO | Profile: STARTER (expected: 500 cus, 2,500 ord, 7,500 tx). Actual: 500 Customers, 2,500 Orders, 7,500 Transactions, 2,500 Lots, 5,024 Allocations |
| 20 | REPRODUCIBILITY_VERIFICATION | System | PASS | INFO | Deterministic seed 20261022 configured; two-run canonical SHA-256 verification verified. |