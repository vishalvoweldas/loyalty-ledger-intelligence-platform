-- Loyalty Ledger Sample Master Seed Data
INSERT INTO tiers (tier_id, tier_name, min_qualifying_spend_minor, spend_per_point_minor, earning_rate_points, effective_from, status) VALUES ('TIER-BRONZE', 'Bronze', 0, 10000, 1, '2026-01-01 00:00:00', 'ACTIVE') ON CONFLICT DO NOTHING;
INSERT INTO tiers (tier_id, tier_name, min_qualifying_spend_minor, spend_per_point_minor, earning_rate_points, effective_from, status) VALUES ('TIER-SILVER', 'Silver', 1000000, 5000, 2, '2026-01-01 00:00:00', 'ACTIVE') ON CONFLICT DO NOTHING;
INSERT INTO tiers (tier_id, tier_name, min_qualifying_spend_minor, spend_per_point_minor, earning_rate_points, effective_from, status) VALUES ('TIER-GOLD', 'Gold', 5000000, 3333, 3, '2026-01-01 00:00:00', 'ACTIVE') ON CONFLICT DO NOTHING;
