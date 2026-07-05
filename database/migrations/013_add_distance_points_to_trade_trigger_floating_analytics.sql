-- =====================================================
-- Add distance points analytics (max/sum negative before profit)
-- to trade_trigger_floating_analytics.
--
-- This allows converting "max_before_profit_usd" into an equivalent
-- "total pip/points against C1 trigger window" using symbol specs + lot.
-- =====================================================

ALTER TABLE public.trade_trigger_floating_analytics
ADD COLUMN IF NOT EXISTS max_negative_distance_points DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS max_negative_distance_price_points DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS sum_negative_distance_points DOUBLE PRECISION;

-- Optional: also keep pct-based distance if you want later
-- (not added now because we derive points from price distance)
