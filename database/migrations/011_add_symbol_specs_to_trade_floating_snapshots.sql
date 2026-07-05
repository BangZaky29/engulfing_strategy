-- =====================================================
-- SQL untuk Supabase - Tambah spec symbol (point/tick) ke trade_floating_snapshots
-- Supaya view analytics bisa menghitung jarak dalam points/pips dan USD-equivalent.
-- File: 011_add_symbol_specs_to_trade_floating_snapshots.sql
-- =====================================================

ALTER TABLE public.trade_floating_snapshots
ADD COLUMN IF NOT EXISTS digits INT,
ADD COLUMN IF NOT EXISTS point DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS tick_size DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS tick_value DOUBLE PRECISION;

-- Optional: indeks agar query cepat kalau nanti ada filter point/tick
CREATE INDEX IF NOT EXISTS idx_tfs_symbol_digits ON public.trade_floating_snapshots(symbol, digits);

