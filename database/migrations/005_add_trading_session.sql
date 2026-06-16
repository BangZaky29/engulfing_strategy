-- =====================================================
-- SQL untuk Supabase - Tambah Kolom Trading Session
-- =====================================================

ALTER TABLE engulfing_signals ADD COLUMN IF NOT EXISTS trading_session VARCHAR(50);
ALTER TABLE trade_analytics ADD COLUMN IF NOT EXISTS trading_session VARCHAR(50);
ALTER TABLE trade_active_logs ADD COLUMN IF NOT EXISTS trading_session VARCHAR(50);
