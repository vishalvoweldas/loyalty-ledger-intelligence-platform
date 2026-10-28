# Validation Report: Loyalty Ledger Intelligence Platform

- **Validation Timestamp**: 2026-10-28T11:41:10.140586+00:00
- **Validation Mode**: baseline
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
| 7 | ORDER_ARITHMETIC | Order | PASS | NONE | Orders with mismatched arithmetic: 0 (all 100,000 verified) |
| 8 | RETURN_QUANTITY_ARITHMETIC | OrderLine | PASS | NONE | Lines with returned_quantity > quantity: 0 (all 199,822 verified) |
| 9 | POINTS_ACCRUAL_CALCULATIONS | PointsTransaction | PASS | NONE | Points accrual floor calculations verified across all accrual transactions. |
| 10 | REVERSAL_REFERENCES_AND_AMOUNTS | OrderReturn | PASS | NONE | Baseline verified: 20,000 returns checked, 0 missing reversals. (2 intentional AN-003 returns isolated in ground truth). |
| 11 | BALANCE_RECONCILIATION | LoyaltyAccount | PASS | NONE | Baseline verified: 19,998 accounts checked, 0 balance discrepancies. (2 intentional AN-001 anomalies isolated in ground truth). |
| 12 | POINT_LOT_ALLOCATIONS | PointLot | PASS | NONE | Baseline verified: 99,992 point lots checked, 0 allocation math discrepancies. (8 intentional AN-004 lots isolated in ground truth). |
| 13 | REDEMPTION_AVAILABILITY_AND_SAFETY | Redemption | PASS | NONE | Baseline verified: 98,994 redemptions checked, 0 overdrawn attempts. (2 intentional AN-002 redemptions isolated in ground truth). |
| 14 | EXPIRY_IDEMPOTENCY | TransactionLotAllocation | PASS | NONE | Baseline verified: 99,992 point lots checked, 0 duplicate expiry allocations. (8 intentional AN-004 lots isolated in ground truth). |
| 15 | TIER_QUALIFICATION_RULES | LoyaltyAccount | PASS | NONE | Baseline verified: Tier qualifying spend rules verified across all baseline accounts. (2 intentional AN-005 accounts isolated in ground truth). |
| 16 | LIFECYCLE_TRANSITION_LEGALITY | Order | PASS | NONE | Orders with invalid status: 0 (all 100,000 orders valid) |
| 17 | IDEMPOTENCY_KEY_UNIQUENESS | PointsTransaction | PASS | NONE | Duplicate idempotency keys: 0 (all 300,000 keys unique) |
| 18 | GROUND_TRUTH_INTEGRITY | GroundTruthRecord | PASS | INFO | Total labelled anomalies in ground truth: 16 (all 5 classes AN-001 through AN-005 verified) |
| 19 | ENTITY_ROW_COUNTS | Multiple | PASS | INFO | Customers: 20000, Orders: 100000, Transactions: 300000, Lots: 100000, Allocations: 201086 |
| 20 | REPRODUCIBILITY_VERIFICATION | System | PASS | INFO | Deterministic seed 20261022 configured; two-run canonical SHA-256 verification verified. |