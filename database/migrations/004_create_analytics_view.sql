-- =====================================================
-- SQL untuk Supabase - Deep Analytics View
-- Menggabungkan data profit/loss dengan data teknikal sinyal engulfing
-- =====================================================

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
    ta.created_at AS trade_created_at,
    es.id AS signal_id,
    es.pattern_type,
    es.engulf_ratio,
    es.ema_trend,
    es.confidence_score,
    es.signal_time
FROM trade_analytics ta
LEFT JOIN engulfing_signals es 
    ON ta.symbol = es.symbol 
    AND ta.timeframe = es.timeframe 
    -- Menghubungkan trade dengan sinyal terakhir yang muncul TEPAT sebelum atau sama dengan waktu OP
    AND es.signal_time = (
        SELECT MAX(es2.signal_time) 
        FROM engulfing_signals es2 
        WHERE es2.symbol = ta.symbol 
          AND es2.timeframe = ta.timeframe 
          AND es2.signal_time <= ta.entry_time
    );

-- Mengaktifkan Realtime untuk view ini tidak diperlukan karena view adalah virtual,
-- kita mengambil data dari view saat frontend diload.
