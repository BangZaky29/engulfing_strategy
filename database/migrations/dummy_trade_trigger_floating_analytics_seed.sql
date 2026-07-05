-- Dummy seed untuk test UI agregasi trade_trigger_floating_analytics
-- Error fix: pastikan kolom NOT NULL pada trade_floating_snapshots terpenuhi, termasuk timeframe.

BEGIN;

-- 1) Seed trade_analytics
INSERT INTO public.trade_analytics (
  ticket_id, symbol, timeframe, mode, result,
  op_price, sl_price, tp_price, profit,
  entry_time, exit_time, image_url, created_at
)
VALUES (
  900001, 'TEST', 'M5', 'BUY', 'LOSS',
  100.0, 90.0, 110.0, -1.0,
  NOW() - INTERVAL '2 days', NOW() - INTERVAL '1 days',
  'https://example.com/dummy.png',
  NOW() - INTERVAL '1 days'
)
ON CONFLICT (ticket_id) DO UPDATE
SET
  symbol = EXCLUDED.symbol,
  timeframe = EXCLUDED.timeframe,
  mode = EXCLUDED.mode,
  result = EXCLUDED.result,
  op_price = EXCLUDED.op_price,
  sl_price = EXCLUDED.sl_price,
  tp_price = EXCLUDED.tp_price,
  profit = EXCLUDED.profit,
  image_url = EXCLUDED.image_url;

-- 2) Seed trade_floating_snapshots
-- Tambahkan timeframe='M5' agar tidak null.
-- Sesuaikan field jika schema kamu memakai nama berbeda.
INSERT INTO public.trade_floating_snapshots (
  ticket_id, symbol, timeframe, trigger_type, mode,
  tf_execute, tf_monitor,
  phase, snapshot_time,
  floating_profit_usd, floating_pct_from_entry,
  entry_price, current_price
)
VALUES
(
  900001, 'TEST', 'M5', 'engulfing', 'BUY',
  'M5', 'M15',
  'BEFORE_PROFIT', NOW() - INTERVAL '30 minutes',
  -5.25, -0.0525,
  100.0, 95.0
),
(
  900001, 'TEST', 'M5', 'engulfing', 'BUY',
  'M5', 'M15',
  'BEFORE_PROFIT', NOW() - INTERVAL '10 minutes',
  -2.00, -0.0200,
  100.0, 98.0
);

COMMIT;

