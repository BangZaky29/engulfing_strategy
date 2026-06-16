-- Script untuk menjodohkan data transaksi lama dengan sinyal aslinya
-- Script ini aman dijalankan berulang kali.

UPDATE public.engulfing_signals es
SET ticket_id = sub.ticket_id
FROM (
    SELECT 
        ta.ticket_id,
        ta.symbol,
        ta.timeframe,
        ta.entry_time,
        (
            -- Cari sinyal yang paling mendekati waktu eksekusi
            SELECT es2.id
            FROM public.engulfing_signals es2
            WHERE es2.symbol = ta.symbol 
              AND es2.timeframe = ta.timeframe 
              -- PASTIKAN HANYA MENGAMBIL SINYAL YANG VALID / DIKONFIRMASI
              AND es2.is_confirmed = true
              AND es2.signal_time <= ta.entry_time
            ORDER BY es2.signal_time DESC
            LIMIT 1
        ) as matching_signal_id
    FROM public.trade_analytics ta
    -- Hanya transaksi yang belum memiliki pasangan
    WHERE NOT EXISTS (
        SELECT 1 FROM public.engulfing_signals es3 
        WHERE es3.ticket_id = ta.ticket_id
    )
) sub
WHERE es.id = sub.matching_signal_id
  AND es.ticket_id IS NULL;
