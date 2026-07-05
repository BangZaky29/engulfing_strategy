-- =====================================================
-- Add volume_lot column to trade_floating_snapshots
-- So we can convert floating USD to distance (points/pips)
-- across multiple symbols/currencies.
-- =====================================================

ALTER TABLE public.trade_floating_snapshots
ADD COLUMN IF NOT EXISTS volume_lot DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_tfs_symbol_time ON public.trade_floating_snapshots(symbol, snapshot_time DESC);
