-- 1. Tambahkan kolom ticket_id ke tabel engulfing_signals
ALTER TABLE public.engulfing_signals
ADD COLUMN IF NOT EXISTS ticket_id BIGINT;

-- 2. Backfill (isi data lama) ticket_id yang ada di dalam JSON notes
-- (Hanya mengekstrak ticket_id dari kolom notes bagi yang is_confirmed = true)
UPDATE public.engulfing_signals
SET ticket_id = (notes::jsonb->>'ticket_id')::BIGINT
WHERE is_confirmed = true 
  AND notes IS NOT NULL 
  AND notes LIKE '{%';

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
FROM public.trade_analytics ta
LEFT JOIN public.engulfing_signals es 
    ON ta.ticket_id = es.ticket_id;
