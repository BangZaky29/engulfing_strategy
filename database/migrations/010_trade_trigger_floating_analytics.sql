-- =====================================================
-- View: trade_trigger_floating_analytics
-- Menggabungkan data dari trade_trigger_analytics (agregat per hari)
-- dengan metrik floating snapshot yang dihitung dari trade_floating_snapshots.
--
-- CATATAN: Definisi view ini awalnya dibuat langsung di Supabase SQL Editor
-- dan tidak didokumentasikan di file migrasi. File ini adalah dokumentasi
-- agar definisi view dapat dilacak di codebase.
--
-- Jika view ini belum ada di Supabase, jalankan SQL berikut:
-- =====================================================

-- Opsi A: max berdasarkan floating_profit_usd (sebelum profit)
-- Opsi B: max berdasarkan floating_pct_from_entry (sebelum profit)

CREATE OR REPLACE VIEW public.trade_trigger_floating_analytics AS
SELECT
    tta.trade_date,
    tta.symbol,
    tta.trigger_type,
    tta.mode,
    tta.tf_execute,
    tta.tf_monitor,
    tta.total_trades,
    tta.total_profit_count,
    tta.total_loss_count,
    tta.total_profit_usd,
    tta.total_loss_usd,
    tta.probability_profit,

    -- Kolom dari trade_trigger_analytics (legacy floating metrics)
    tta.max_negative_floating_before_profit_usd,
    tta.max_negative_floating_before_profit_pct,
    tta.sum_negative_floating_before_profit_usd,

    -- ============ Opsi A: USD-based floating metrics ============
    -- Agregasi dari trade_floating_snapshots: hanya snapshot dengan floating_profit_usd < 0
    fs_usd.avg_max_before_profit_usd,
    fs_usd.max_max_before_profit_usd,
    fs_usd.avg_max_before_profit_pct_usd_based,
    fs_usd.avg_total_distance_price_usd_based,
    fs_usd.sum_total_distance_price_usd_based,

    -- ============ Opsi B: Pct-based floating metrics ============
    fs_pct.avg_max_before_profit_pct,
    fs_pct.max_max_before_profit_pct,
    fs_pct.avg_max_before_profit_usd_pct_based,
    fs_pct.avg_total_distance_price_pct_based,
    fs_pct.sum_total_distance_price_pct_based

FROM public.trade_trigger_analytics tta

-- JOIN lateral subquery: Opsi A (ranked by min floating_profit_usd per ticket)
LEFT JOIN LATERAL (
    SELECT
        AVG(sub_a.min_usd) AS avg_max_before_profit_usd,
        MIN(sub_a.min_usd) AS max_max_before_profit_usd,
        AVG(sub_a.min_pct) AS avg_max_before_profit_pct_usd_based,
        AVG(sub_a.total_dist) AS avg_total_distance_price_usd_based,
        SUM(sub_a.total_dist) AS sum_total_distance_price_usd_based
    FROM (
        SELECT
            tfs.ticket_id,
            MIN(tfs.floating_profit_usd) AS min_usd,
            MIN(tfs.floating_pct_from_entry) AS min_pct,
            SUM(ABS(tfs.current_price - tfs.entry_price)) AS total_dist
        FROM public.trade_floating_snapshots tfs
        WHERE tfs.symbol = tta.symbol
          AND tfs.trigger_type = tta.trigger_type
          AND tfs.mode = tta.mode
          AND tfs.tf_execute = tta.tf_execute
          AND tfs.tf_monitor = tta.tf_monitor
          AND DATE(tfs.snapshot_time) = tta.trade_date
          AND tfs.floating_profit_usd < 0
        GROUP BY tfs.ticket_id
    ) sub_a
) fs_usd ON TRUE

-- JOIN lateral subquery: Opsi B (ranked by min floating_pct_from_entry per ticket)
LEFT JOIN LATERAL (
    SELECT
        AVG(sub_b.min_pct) AS avg_max_before_profit_pct,
        MIN(sub_b.min_pct) AS max_max_before_profit_pct,
        AVG(sub_b.min_usd) AS avg_max_before_profit_usd_pct_based,
        AVG(sub_b.total_dist) AS avg_total_distance_price_pct_based,
        SUM(sub_b.total_dist) AS sum_total_distance_price_pct_based
    FROM (
        SELECT
            tfs.ticket_id,
            MIN(tfs.floating_pct_from_entry) AS min_pct,
            MIN(tfs.floating_profit_usd) AS min_usd,
            SUM(ABS(tfs.current_price - tfs.entry_price)) AS total_dist
        FROM public.trade_floating_snapshots tfs
        WHERE tfs.symbol = tta.symbol
          AND tfs.trigger_type = tta.trigger_type
          AND tfs.mode = tta.mode
          AND tfs.tf_execute = tta.tf_execute
          AND tfs.tf_monitor = tta.tf_monitor
          AND DATE(tfs.snapshot_time) = tta.trade_date
          AND tfs.floating_pct_from_entry < 0
        GROUP BY tfs.ticket_id
    ) sub_b
) fs_pct ON TRUE;

-- Policy: Izinkan SELECT untuk anon & authenticated (read-only view)
-- Catatan: View mewarisi policy dari tabel yang mendasarinya.
-- Jika perlu, tambahkan grant:
-- GRANT SELECT ON public.trade_trigger_floating_analytics TO anon, authenticated;