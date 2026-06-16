-- =====================================================
-- SQL untuk Supabase - Table Log Aktif Limit Order
-- =====================================================

CREATE TABLE IF NOT EXISTS trade_active_logs (
    id BIGSERIAL PRIMARY KEY,
    ticket_id BIGINT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    mode VARCHAR(10) NOT NULL CHECK (mode IN ('BUY', 'SELL')),
    message TEXT NOT NULL,
    op_price DOUBLE PRECISION,
    sl_price DOUBLE PRECISION,
    tp_price DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_active_log_ticket UNIQUE (ticket_id)
);

-- Index
CREATE INDEX IF NOT EXISTS idx_active_logs_ticket ON trade_active_logs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_active_logs_time ON trade_active_logs (created_at DESC);

-- Enable RLS
ALTER TABLE trade_active_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow service role full access on trade_active_logs" 
    ON trade_active_logs FOR ALL 
    USING (true) WITH CHECK (true);

CREATE POLICY "Allow public read access on trade_active_logs"
    ON trade_active_logs FOR SELECT
    USING (true);

-- Enable Realtime (PENTING untuk WA Bot)
ALTER PUBLICATION supabase_realtime ADD TABLE trade_active_logs;
