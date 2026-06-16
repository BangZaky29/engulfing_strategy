-- =====================================================
-- SQL untuk Supabase - Deep Analytics View
-- Menggabungkan data profit/loss dengan data teknikal sinyal engulfing
-- =====================================================

DROP VIEW IF EXISTS public.trade_deep_analytics_view CASCADE;

CREATE OR REPLACE VIEW public.trade_deep_analytics_view AS
SELECT 
    ta.id AS trade_id,
    ta.ticket_id,
    ta.symbol,
    ta.timeframe,
    ta.mode,
    ta.result,
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
    es.notes
FROM trade_analytics ta
LEFT JOIN engulfing_signals es 
    ON ta.ticket_id = es.ticket_id;

-- Mengaktifkan Realtime untuk view ini tidak diperlukan karena view adalah virtual,
-- kita mengambil data dari view saat frontend diload.
