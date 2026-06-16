-- =====================================================
-- SQL untuk Supabase - Ekstensi Analisis Performa Sesi
-- File: 007_session_analytics_extensions.sql
-- =====================================================

-- 1. Tambah kolom exit_price dan volume ke trade_analytics (jika belum ada)
ALTER TABLE public.trade_analytics 
ADD COLUMN IF NOT EXISTS exit_price DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS volume DOUBLE PRECISION;

COMMENT ON COLUMN public.trade_analytics.exit_price IS 'Harga penutupan aktual posisi trading dari MT5 deal';
COMMENT ON COLUMN public.trade_analytics.volume IS 'Ukuran lot size posisi trading';

-- 2. Tambah kolom volume ke engulfing_signals (jika belum ada)
ALTER TABLE public.engulfing_signals 
ADD COLUMN IF NOT EXISTS volume DOUBLE PRECISION;

COMMENT ON COLUMN public.engulfing_signals.volume IS 'Tick volume lilin engulfing pada saat sinyal terdeteksi';

-- 3. Perbarui view trade_deep_analytics_view dengan kolom baru dan kolom yang terlewat
DROP VIEW IF EXISTS public.trade_deep_analytics_view CASCADE;

CREATE OR REPLACE VIEW public.trade_deep_analytics_view AS
SELECT 
    ta.id AS trade_id,
    ta.ticket_id,
    ta.symbol,
    ta.timeframe,
    ta.mode,
    ta.result,
    ta.op_price,
    ta.sl_price,
    ta.tp_price,
    ta.exit_price,
    ta.volume AS trade_volume,
    ta.profit,
    ta.entry_time,
    ta.exit_time,
    ta.image_url,
    ta.trading_session,
    ta.created_at AS trade_created_at,
    es.id AS signal_id,
    es.pattern_type,
    es.engulf_ratio,
    es.ema_trend,
    es.confidence_score,
    es.signal_time,
    es.notes,
    es.prev_open,
    es.prev_close,
    es.prev_high,
    es.prev_low,
    es.curr_open,
    es.curr_close,
    es.curr_high,
    es.curr_low,
    es.volume AS signal_volume
FROM public.trade_analytics ta
LEFT JOIN public.engulfing_signals es 
    ON ta.ticket_id = es.ticket_id;
