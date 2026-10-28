"""Deterministic synthetic data generator producing realistic, reproducible loyalty datasets."""
import random
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from loyalty_ledger.domain.models import (
    Customer, LoyaltyAccount, Tier, Rule, Reward, Order, OrderLine,
    PointsTransaction, PointLot, TransactionLotAllocation,
    AccountTierHistory, OrderReturn, Redemption, ExpiryBatch
)
from loyalty_ledger.domain.rules import (
    DEFAULT_TIERS_CONFIG, DEFAULT_RULES_CONFIG, DEFAULT_REWARDS_CONFIG, RuleEngine
)

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Diya", "Saanvi", "Ananya", "Aadhya", "Pari", "Chiara", "Myra", "Riya", "Anvi", "Sneha",
    "Rohan", "Pooja", "Vikram", "Neha", "Rahul", "Priya", "Amit", "Kavita", "Suresh", "Sunita",
    "Deepak", "Anjali", "Manish", "Swati", "Rajesh", "Meera", "Sanjay", "Preeti", "Karan", "Shreya"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Gupta", "Singh", "Kumar", "Mehta", "Shah", "Reddy", "Nair",
    "Chopra", "Joshi", "Bhatia", "Malhotra", "Kapoor", "Saxena", "Iyer", "Rao", "Das", "Mukherjee",
    "Banerjee", "Chatterjee", "Mishra", "Pandey", "Trivedi", "Deshmukh", "Kulkarni", "Patil", "Pawar", "Shinde"
]

REGIONS = ["NORTH", "SOUTH", "EAST", "WEST", "CENTRAL"]
CATEGORIES = ["ELECTRONICS", "APPAREL", "HOME", "BEAUTY", "GROCERY"]

SCALE_CONFIGS = {
    "starter": {
        "customers": 500,
        "orders": 2500,
        "transactions": 7500,
        "anomalous_tx_budget": 10
    },
    "full": {
        "customers": 20000,
        "orders": 100000,
        "transactions": 300000,
        "anomalous_tx_budget": 10
    }
}

class SyntheticDataGenerator:
    def __init__(self, seed: int = 20261022):
        self.seed = seed
        self.rng = random.Random(seed)
        self.sim_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.sim_end = datetime(2026, 10, 22, 23, 59, 59, tzinfo=timezone.utc)
        self.sim_duration_seconds = int((self.sim_end - self.sim_start).total_seconds())

    def random_timestamp(self, start_sec: int = 0, end_sec: Optional[int] = None) -> datetime:
        end = end_sec or self.sim_duration_seconds
        sec = self.rng.randint(start_sec, end)
        return self.sim_start + timedelta(seconds=sec)

    def generate_master_data(self, session: Session):
        """Creates Tiers, Rules, and Rewards."""
        # Tiers
        for t_cfg in DEFAULT_TIERS_CONFIG:
            tier = Tier(
                tier_id=t_cfg["tier_id"],
                tier_name=t_cfg["tier_name"],
                min_qualifying_spend_minor=t_cfg["min_qualifying_spend_minor"],
                spend_per_point_minor=t_cfg["spend_per_point_minor"],
                earning_rate_points=t_cfg["earning_rate_points"],
                effective_from=datetime.fromisoformat(t_cfg["effective_from"]),
                effective_to=None,
                status=t_cfg["status"]
            )
            session.merge(tier)

        # Rules
        for r_cfg in DEFAULT_RULES_CONFIG:
            rule = Rule(
                rule_id=r_cfg["rule_id"],
                rule_type=r_cfg["rule_type"],
                version=r_cfg["version"],
                description=r_cfg["description"],
                parameters=r_cfg["parameters"],
                effective_from=datetime.fromisoformat(r_cfg["effective_from"]),
                effective_to=None,
                status=r_cfg["status"]
            )
            session.merge(rule)

        # Rewards
        for rew_cfg in DEFAULT_REWARDS_CONFIG:
            reward = Reward(
                reward_id=rew_cfg["reward_id"],
                reward_name=rew_cfg["reward_name"],
                points_cost=rew_cfg["points_cost"],
                status=rew_cfg["status"],
                effective_from=datetime.fromisoformat(rew_cfg["effective_from"]),
                effective_to=None,
                inventory_quantity=rew_cfg["inventory_quantity"]
            )
            session.merge(reward)

        session.flush()

    def generate_dataset(
        self,
        session: Session,
        scale: str = "starter",
        custom_customers: Optional[int] = None,
        custom_orders: Optional[int] = None,
        custom_transactions: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generates full synthetic dataset meeting exact row count requirements.
        """
        # Re-seed RNG for deterministic generation
        self.rng = random.Random(self.seed)

        if scale in SCALE_CONFIGS:
            cfg = SCALE_CONFIGS[scale]
            num_customers = cfg["customers"]
            num_orders = cfg["orders"]
            num_tx_target = cfg["transactions"]
            tx_budget = cfg["anomalous_tx_budget"]
        else:
            num_customers = custom_customers or 500
            num_orders = custom_orders or 2500
            num_tx_target = custom_transactions or 7500
            tx_budget = 10

        baseline_tx_target = num_tx_target - tx_budget



        print(f"Generating master data...")
        self.generate_master_data(session)

        print(f"Generating {num_customers} customers and loyalty accounts in memory...")
        customers = []
        customer_ids = []
        account_ids = []
        account_opened_dates = {}

        for i in range(1, num_customers + 1):
            cus_id = f"CUS-{i:06d}"
            acc_id = f"LOY-CUS-{i:06d}"
            customer_ids.append(cus_id)
            account_ids.append(acc_id)

            fname = self.rng.choice(FIRST_NAMES)
            lname = self.rng.choice(LAST_NAMES)
            name = f"{fname} {lname}"
            email = f"{fname.lower()}.{lname.lower()}{i}@example.com"
            region = self.rng.choice(REGIONS)
            created_at = self.sim_start + timedelta(seconds=self.rng.randint(0, self.sim_duration_seconds // 3))
            account_opened_dates[acc_id] = created_at

            cus = {
                "customer_id": cus_id,
                "name": name,
                "email": email,
                "region": region,
                "status": "ACTIVE",
                "created_at": created_at
            }
            customers.append(cus)

        print(f"Generating {num_orders} orders and order lines...")
        orders = []
        order_lines = []

        # Exact target transaction allocation:
        num_accruals = num_orders
        num_reversals = int(num_orders * 0.20)
        num_redemptions = int((baseline_tx_target - num_accruals - num_reversals) * 0.55)
        num_expiries = baseline_tx_target - num_accruals - num_reversals - num_redemptions

        print(f"Target transaction plan: {num_accruals} accruals, {num_redemptions} redemptions, {num_reversals} reversals, {num_expiries} expiries (+{tx_budget} anomaly txs) = {num_tx_target} total.")

        tx_counter = 1
        points_transactions = []
        point_lots = []
        order_eligible_spends = {}
        order_dates = {}
        order_accrual_tx_ids = {}

        # 1. Orders & Accruals
        for i in range(1, num_orders + 1):
            ord_id = f"ORD-2026-{i:06d}"
            cus_idx = self.rng.randint(0, num_customers - 1)
            cus_id = customer_ids[cus_idx]
            acc_id = account_ids[cus_idx]

            # Order date between customer created_at and sim_end
            ord_date = self.sim_start + timedelta(seconds=self.rng.randint(self.sim_duration_seconds // 4, self.sim_duration_seconds))
            order_dates[ord_id] = ord_date

            # 1 to 3 lines per order
            num_lines = self.rng.randint(1, 3)
            order_subtotal = 0
            order_discount = 0
            order_eligible = 0

            for l_idx in range(1, num_lines + 1):
                line_id = f"LINE-{ord_id}-{l_idx:02d}"
                sku = f"SKU-{self.rng.choice(CATEGORIES)[:4]}-{self.rng.randint(100, 999)}"
                category = self.rng.choice(CATEGORIES)
                qty = self.rng.randint(1, 3)
                unit_price = self.rng.randint(200, 5000) * 100  # in paise (₹200 to ₹5,000)
                disc = self.rng.randint(0, 20) * 100 * qty if self.rng.random() > 0.5 else 0
                line_subtotal = unit_price * qty
                net_line = max(0, line_subtotal - disc)

                order_subtotal += line_subtotal
                order_discount += disc
                order_eligible += net_line

                ol = {
                    "order_line_id": line_id,
                    "order_id": ord_id,
                    "sku": sku,
                    "category": category,
                    "quantity": qty,
                    "unit_price_minor": unit_price,
                    "discount_minor": disc,
                    "eligible_spend_minor": net_line,
                    "returned_quantity": 0
                }
                order_lines.append(ol)

            tax = int(order_eligible * 0.09)
            shipping = 10000 if order_eligible < 100000 else 0  # ₹100 if < ₹1,000
            net_merch = max(0, order_subtotal - order_discount)
            total = net_merch + tax + shipping
            order_eligible_spends[ord_id] = order_eligible

            ord_obj = {
                "order_id": ord_id,
                "customer_id": cus_id,
                "order_date": ord_date,
                "status": "COMPLETED",
                "currency": "INR",
                "subtotal_minor": order_subtotal,
                "discount_minor": order_discount,
                "tax_minor": tax,
                "shipping_minor": shipping,
                "net_merchandise_minor": net_merch,
                "total_minor": total
            }
            orders.append(ord_obj)

            # Generate Accrual Transaction (Bronze rate: 1 pt per ₹100 = 10,000 paise)
            pts_earned = max(10, order_eligible // 10000)
            tx_id = f"PTS-2026-{tx_counter:08d}"
            order_accrual_tx_ids[ord_id] = tx_id
            tx_counter += 1

            tx = {
                "transaction_id": tx_id,
                "account_id": acc_id,
                "transaction_type": "ACCRUAL",
                "points_delta": pts_earned,
                "event_at": ord_date,
                "effective_at": ord_date,
                "source_type": "ORDER",
                "source_id": ord_id,
                "original_transaction_id": None,
                "rule_id": "RULE-ACCRUAL-V1",
                "status": "POSTED",
                "idempotency_key": f"IDEMP-ACCR-{ord_id}",
                "reason_code": "PURCHASE_ACCRUAL",
                "correlation_id": f"CORR-{ord_id}",
                "created_at": ord_date
            }
            points_transactions.append(tx)

            # Create PointLot
            lot_id = f"LOT-{tx_id}"
            lot = {
                "lot_id": lot_id,
                "account_id": acc_id,
                "source_transaction_id": tx_id,
                "original_points": pts_earned,
                "remaining_points": pts_earned,
                "accrued_at": ord_date,
                "expires_at": ord_date + timedelta(days=365),
                "status": "OPEN",
                "rule_id": "RULE-ACCRUAL-V1"
            }
            point_lots.append(lot)

        # Index lots by account for strict FIFO tracking
        account_open_lots = {acc_id: [] for acc_id in account_ids}
        lot_by_id = {}
        for lot in point_lots:
            account_open_lots[lot["account_id"]].append(lot)
            lot_by_id[lot["lot_id"]] = lot
        account_unspent = {acc_id: sum(l["remaining_points"] for l in lots) for acc_id, lots in account_open_lots.items()}

        # Index lots by account for strict FIFO tracking
        account_open_lots = {acc_id: [] for acc_id in account_ids}
        lot_by_id = {}
        for lot in point_lots:
            account_open_lots[lot["account_id"]].append(lot)
            lot_by_id[lot["lot_id"]] = lot
        account_unspent = {acc_id: sum(l["remaining_points"] for l in lots) for acc_id, lots in account_open_lots.items()}

        allocations = []
        alloc_counter = 1

        print(f"Generating {num_reversals} returns & reversals...")
        # 2. Returns & Reversals (occur 3-14 days after purchase, reversing partial accruals)
        order_returns = []
        for ret_i in range(1, num_reversals + 1):
            ret_id = f"RET-ORD-2026-{ret_i:06d}"
            orig_ord_id = f"ORD-2026-{ret_i:06d}"
            orig_tx_id = order_accrual_tx_ids[orig_ord_id]
            ord_date = order_dates[orig_ord_id]
            ret_date = ord_date + timedelta(days=self.rng.randint(3, 14))
            orig_eligible = order_eligible_spends[orig_ord_id]
            returned_eligible = orig_eligible // 2  # 50% partial return

            tx_id = f"PTS-2026-{tx_counter:08d}"
            tx_counter += 1

            orig_lot = lot_by_id[f"LOT-{orig_tx_id}"]
            orig_pts = orig_lot["original_points"]
            rev_pts = max(1, orig_pts // 3)  # Partial return reverses 1/3 of points
            orig_lot["remaining_points"] -= rev_pts
            if orig_lot["remaining_points"] == 0:
                orig_lot["status"] = "EXHAUSTED"

            tx = {
                "transaction_id": tx_id,
                "account_id": orig_lot["account_id"],
                "transaction_type": "REVERSAL",
                "points_delta": -rev_pts,
                "event_at": ret_date,
                "effective_at": ret_date,
                "source_type": "RETURN",
                "source_id": ret_id,
                "original_transaction_id": orig_tx_id,
                "rule_id": "RULE-REVERSAL-V1",
                "status": "POSTED",
                "idempotency_key": f"IDEMP-REV-{ret_id}",
                "reason_code": "RETURN_REVERSAL",
                "correlation_id": f"CORR-{orig_ord_id}",
                "created_at": ret_date
            }
            points_transactions.append(tx)

            ret = {
                "return_id": ret_id,
                "order_id": orig_ord_id,
                "return_date": ret_date,
                "reason": "CUSTOMER_RETURN_PARTIAL",
                "returned_eligible_spend_minor": returned_eligible,
                "reversal_transaction_id": tx_id
            }
            order_returns.append(ret)

            alloc_id = f"ALLOC-{alloc_counter:08d}"
            alloc_counter += 1
            alloc = {
                "allocation_id": alloc_id,
                "transaction_id": tx_id,
                "lot_id": f"LOT-{orig_tx_id}",
                "allocated_points": rev_pts,
                "allocation_type": "REVERSAL",
                "created_at": ret_date
            }
            allocations.append(alloc)
            account_unspent[orig_lot["account_id"]] -= rev_pts

        print(f"Generating {num_expiries} expiries...")
        # 3. Expiries & ExpiryBatches
        expiry_batch_id = "EXP-2026-000001"
        batch_cutoff = self.sim_start + timedelta(days=200)
        exp_batch = {
            "expiry_batch_id": expiry_batch_id,
            "run_at": batch_cutoff,
            "cutoff_at": batch_cutoff,
            "status": "COMPLETED",
            "lots_scanned": num_expiries,
            "points_expired": num_expiries * 2,
            "idempotency_key": f"IDEMP-{expiry_batch_id}"
        }

        # Each expiry targets a distinct lot from point_lots (1:1 allocation)
        for exp_i in range(1, num_expiries + 1):
            tx_id = f"PTS-2026-{tx_counter:08d}"
            tx_counter += 1

            target_lot = point_lots[exp_i - 1]
            exp_pts = min(max(1, target_lot["remaining_points"] // 4), 3)
            target_lot["remaining_points"] -= exp_pts
            if target_lot["remaining_points"] == 0:
                target_lot["status"] = "EXPIRED"

            tx = {
                "transaction_id": tx_id,
                "account_id": target_lot["account_id"],
                "transaction_type": "EXPIRY",
                "points_delta": -exp_pts,
                "event_at": batch_cutoff,
                "effective_at": batch_cutoff,
                "source_type": "EXPIRY_BATCH",
                "source_id": expiry_batch_id,
                "original_transaction_id": None,
                "rule_id": "RULE-EXPIRY-V1",
                "status": "POSTED",
                "idempotency_key": f"IDEMP-EXP-{expiry_batch_id}-{exp_i}",
                "reason_code": "LOT_EXPIRY",
                "correlation_id": f"CORR-EXP-{expiry_batch_id}",
                "created_at": batch_cutoff
            }
            points_transactions.append(tx)

            alloc_id = f"ALLOC-{alloc_counter:08d}"
            alloc_counter += 1
            alloc = {
                "allocation_id": alloc_id,
                "transaction_id": tx_id,
                "lot_id": target_lot["lot_id"],
                "allocated_points": exp_pts,
                "allocation_type": "EXPIRY",
                "created_at": batch_cutoff
            }
            allocations.append(alloc)
            account_unspent[target_lot["account_id"]] -= exp_pts

        print(f"Generating {num_redemptions} redemptions with strict FIFO lot allocations...")
        # 4. Redemptions
        redemptions = []
        active_accounts = [acc_id for acc_id in account_ids if account_unspent.get(acc_id, 0) >= 2]
        if not active_accounts:
            active_accounts = account_ids

        for r_i in range(1, num_redemptions + 1):
            rdm_id = f"RDM-2026-{r_i:06d}"
            acc_id = active_accounts[(r_i - 1) % len(active_accounts)]
            avail = account_unspent.get(acc_id, 0)
            if avail < 2:
                for alt_acc in active_accounts:
                    if account_unspent.get(alt_acc, 0) >= 2:
                        acc_id = alt_acc
                        avail = account_unspent[acc_id]
                        break

            req_pts = min(avail, self.rng.choice([1, 2, 5])) if avail > 0 else 1
            rdm_date = self.sim_start + timedelta(seconds=self.rng.randint(self.sim_duration_seconds // 2, self.sim_duration_seconds))

            rdm = {
                "redemption_id": rdm_id,
                "account_id": acc_id,
                "reward_id": "REW-VOUCHER-100",
                "requested_points": req_pts,
                "approved_points": req_pts,
                "status": "APPROVED",
                "requested_at": rdm_date,
                "processed_at": rdm_date,
                "rejection_reason": None,
                "idempotency_key": f"IDEMP-RDM-{rdm_id}"
            }
            redemptions.append(rdm)

            tx_id = f"PTS-2026-{tx_counter:08d}"
            tx_counter += 1

            tx = {
                "transaction_id": tx_id,
                "account_id": acc_id,
                "transaction_type": "REDEMPTION",
                "points_delta": -req_pts,
                "event_at": rdm_date,
                "effective_at": rdm_date,
                "source_type": "REDEMPTION",
                "source_id": rdm_id,
                "original_transaction_id": None,
                "rule_id": "RULE-REDEMPTION-V1",
                "status": "POSTED",
                "idempotency_key": f"IDEMP-TX-RDM-{rdm_id}",
                "reason_code": "REWARD_REDEMPTION",
                "correlation_id": f"CORR-RDM-{rdm_id}",
                "created_at": rdm_date
            }
            points_transactions.append(tx)

            rem_to_deduct = req_pts
            for target_lot in account_open_lots[acc_id]:
                if rem_to_deduct <= 0:
                    break
                if target_lot["remaining_points"] <= 0:
                    continue
                deduct = min(target_lot["remaining_points"], rem_to_deduct)
                target_lot["remaining_points"] -= deduct
                if target_lot["remaining_points"] == 0:
                    target_lot["status"] = "EXHAUSTED"

                alloc_id = f"ALLOC-{alloc_counter:08d}"
                alloc_counter += 1
                alloc = {
                    "allocation_id": alloc_id,
                    "transaction_id": tx_id,
                    "lot_id": target_lot["lot_id"],
                    "allocated_points": deduct,
                    "allocation_type": "REDEMPTION",
                    "created_at": rdm_date
                }
                allocations.append(alloc)
                rem_to_deduct -= deduct

            account_unspent[acc_id] -= req_pts

        print("Reconciling account balances and evaluating tiers in O(N)...")
        account_balances = {}
        for tx in points_transactions:
            account_balances[tx["account_id"]] = account_balances.get(tx["account_id"], 0) + tx["points_delta"]

        # Pre-aggregate gross spend per customer using net_merchandise_minor
        cus_gross_spend = {}
        for ord in orders:
            cus_gross_spend[ord["customer_id"]] = cus_gross_spend.get(ord["customer_id"], 0) + ord["net_merchandise_minor"]

        # Pre-aggregate returns spend per customer
        cus_returns_spend = {}
        ord_to_cus = {ord["order_id"]: ord["customer_id"] for ord in orders}
        for ret in order_returns:
            c_id = ord_to_cus.get(ret["order_id"])
            if c_id:
                cus_returns_spend[c_id] = cus_returns_spend.get(c_id, 0) + ret["returned_eligible_spend_minor"]

        accounts = []
        tier_histories = []
        for i, cus_id in enumerate(customer_ids):
            acc_id = account_ids[i]
            bal = account_balances.get(acc_id, 0)
            gross = cus_gross_spend.get(cus_id, 0)
            ret = cus_returns_spend.get(cus_id, 0)
            net_qual = max(0, gross - ret)
            tier_id, _, _, _ = RuleEngine.evaluate_tier(net_qual, DEFAULT_TIERS_CONFIG)
            opened_at = account_opened_dates[acc_id]

            acc = {
                "account_id": acc_id,
                "customer_id": cus_id,
                "current_tier_id": tier_id,
                "status": "ACTIVE",
                "opened_at": opened_at,
                "closed_at": None,
                "cached_balance_points": bal
            }
            accounts.append(acc)

            th = {
                "history_id": f"TH-{acc_id}-00",
                "account_id": acc_id,
                "tier_id": tier_id,
                "qualifying_spend_minor": net_qual,
                "effective_from": opened_at,
                "effective_to": None,
                "reason": "QUALIFYING_SPEND_EVALUATION"
            }
            tier_histories.append(th)

        print(f"Persisting all records using bulk_insert_mappings...")
        session.bulk_insert_mappings(Customer, customers)
        session.bulk_insert_mappings(LoyaltyAccount, accounts)
        session.bulk_insert_mappings(AccountTierHistory, tier_histories)
        session.bulk_insert_mappings(ExpiryBatch, [exp_batch])
        session.bulk_insert_mappings(Order, orders)
        session.bulk_insert_mappings(OrderLine, order_lines)
        session.bulk_insert_mappings(PointsTransaction, points_transactions)
        session.bulk_insert_mappings(Redemption, redemptions)
        session.bulk_insert_mappings(OrderReturn, order_returns)
        session.bulk_insert_mappings(PointLot, point_lots)
        session.bulk_insert_mappings(TransactionLotAllocation, allocations)
        session.commit()



        print(f"Dataset generated successfully! Baseline transactions count: {len(points_transactions)}")
        return {
            "scale": scale,
            "seed": self.seed,
            "customers_count": len(customers),
            "orders_count": len(orders),
            "order_lines_count": len(order_lines),
            "transactions_count": len(points_transactions),
            "redemptions_count": len(redemptions),
            "returns_count": len(order_returns),
            "point_lots_count": len(point_lots),
            "allocations_count": len(allocations)
        }
