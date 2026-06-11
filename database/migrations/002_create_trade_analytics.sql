-- =====================================================
-- SQL untuk Supabase - Tambahan Table Trade Analytics
-- =====================================================

CREATE TABLE IF NOT EXISTS trade_analytics (
    id BIGSERIAL PRIMARY KEY,
    ticket_id BIGINT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    mode VARCHAR(10) NOT NULL CHECK (mode IN ('BUY', 'SELL')),
    result VARCHAR(10) NOT NULL CHECK (result IN ('PROFIT', 'LOSS')),
    op_price DOUBLE PRECISION,
    sl_price DOUBLE PRECISION,
    tp_price DOUBLE PRECISION,
    profit DOUBLE PRECISION,
    entry_time TIMESTAMPTZ,
    exit_time TIMESTAMPTZ,
    image_url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_trade_ticket UNIQUE (ticket_id)
);

-- Index untuk mempermudah pencarian (misal di website dashboard)
CREATE INDEX IF NOT EXISTS idx_trade_analytics_symbol ON trade_analytics (symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_trade_analytics_result ON trade_analytics (result);
CREATE INDEX IF NOT EXISTS idx_trade_analytics_time ON trade_analytics (created_at DESC);

-- Enable RLS dan beri akses penuh (Service Role)
ALTER TABLE trade_analytics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow service role full access on trade_analytics" 
    ON trade_analytics FOR ALL 
    USING (true) WITH CHECK (true);

-- Jika website Frontend butuh akses read tanpa login (Public Read):
CREATE POLICY "Allow public read access on trade_analytics"
    ON trade_analytics FOR SELECT
    USING (true);
