-- =====================================================
-- SQL untuk Supabase - Project Engulfing Pattern
-- Jalankan di Supabase SQL Editor
-- Project: metaTrader5 (wcsxwordxurulfslwgcu)
-- =====================================================

-- =====================================================
-- 1. Table: candles (simpan data candle dari MT5)
-- =====================================================
CREATE TABLE IF NOT EXISTS candles (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open_ DOUBLE PRECISION NOT NULL,
    high_ DOUBLE PRECISION NOT NULL,
    low_ DOUBLE PRECISION NOT NULL,
    close_ DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION DEFAULT 0,
    spread DOUBLE PRECISION DEFAULT 0,
    ema_fast DOUBLE PRECISION,
    ema_slow DOUBLE PRECISION,
    body_size DOUBLE PRECISION,
    upper_wick DOUBLE PRECISION,
    lower_wick DOUBLE PRECISION,
    is_bullish BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unik constraint untuk mencegah duplikat candle
    CONSTRAINT unique_candle UNIQUE (symbol, timeframe, timestamp)
);

-- Index untuk query cepat
CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_time 
    ON candles (symbol, timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_candles_timestamp 
    ON candles (timestamp DESC);

-- =====================================================
-- 2. Table: engulfing_signals (deteksi pola engulfing)
-- =====================================================
CREATE TABLE IF NOT EXISTS engulfing_signals (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    signal_time TIMESTAMPTZ NOT NULL,
    pattern_type VARCHAR(20) NOT NULL CHECK (pattern_type IN ('bullish_engulfing', 'bearish_engulfing')),
    
    -- Data candle sebelumnya (C1)
    prev_open DOUBLE PRECISION NOT NULL,
    prev_close DOUBLE PRECISION NOT NULL,
    prev_high DOUBLE PRECISION NOT NULL,
    prev_low DOUBLE PRECISION NOT NULL,
    
    -- Data candle engulfing (C2)
    curr_open DOUBLE PRECISION NOT NULL,
    curr_close DOUBLE PRECISION NOT NULL,
    curr_high DOUBLE PRECISION NOT NULL,
    curr_low DOUBLE PRECISION NOT NULL,
    
    -- Analisa
    engulf_ratio DOUBLE PRECISION,           -- rasio body C2 / body C1
    ema_fast_value DOUBLE PRECISION,
    ema_slow_value DOUBLE PRECISION,
    ema_trend VARCHAR(10),                   -- 'bullish' / 'bearish' / 'neutral'
    confidence_score DOUBLE PRECISION,       -- skor kepercayaan 0-100
    
    -- Metadata
    is_confirmed BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unik constraint
    CONSTRAINT unique_engulfing_signal UNIQUE (symbol, timeframe, signal_time, pattern_type)
);

-- Index
CREATE INDEX IF NOT EXISTS idx_engulfing_symbol_time 
    ON engulfing_signals (symbol, timeframe, signal_time DESC);

CREATE INDEX IF NOT EXISTS idx_engulfing_pattern 
    ON engulfing_signals (pattern_type, signal_time DESC);

CREATE INDEX IF NOT EXISTS idx_engulfing_confidence 
    ON engulfing_signals (confidence_score DESC);

-- =====================================================
-- 3. Table: engulfing_stats (statistik akumulasi)
-- =====================================================
CREATE TABLE IF NOT EXISTS engulfing_stats (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    total_bullish INT DEFAULT 0,
    total_bearish INT DEFAULT 0,
    avg_confidence DOUBLE PRECISION DEFAULT 0,
    highest_confidence DOUBLE PRECISION DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_stats UNIQUE (symbol, timeframe, date)
);

CREATE INDEX IF NOT EXISTS idx_stats_symbol_date 
    ON engulfing_stats (symbol, timeframe, date DESC);

-- =====================================================
-- 4. Enable Row Level Security (RLS) - Optional
-- =====================================================
-- Jika ingin akses publik (untuk development), disable RLS:
ALTER TABLE candles ENABLE ROW LEVEL SECURITY;
ALTER TABLE engulfing_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE engulfing_stats ENABLE ROW LEVEL SECURITY;

-- Policy: Allow all operations with service_role key
CREATE POLICY "Allow service role full access on candles" 
    ON candles FOR ALL 
    USING (true) WITH CHECK (true);

CREATE POLICY "Allow service role full access on engulfing_signals" 
    ON engulfing_signals FOR ALL 
    USING (true) WITH CHECK (true);

CREATE POLICY "Allow service role full access on engulfing_stats" 
    ON engulfing_stats FOR ALL 
    USING (true) WITH CHECK (true);

-- =====================================================
-- 5. View: latest engulfing signals (helper view)
-- =====================================================
CREATE OR REPLACE VIEW v_latest_engulfing AS
SELECT 
    es.*,
    CASE 
        WHEN es.pattern_type = 'bullish_engulfing' THEN '🟩 BULLISH'
        ELSE '🟥 BEARISH'
    END AS signal_label,
    CASE 
        WHEN es.confidence_score >= 80 THEN '🔥 HIGH'
        WHEN es.confidence_score >= 50 THEN '⚡ MEDIUM'
        ELSE '💤 LOW'
    END AS confidence_label
FROM engulfing_signals es
ORDER BY es.signal_time DESC
LIMIT 50;

-- =====================================================
-- 6. Enable Realtime for engulfing_signals
-- =====================================================
ALTER PUBLICATION supabase_realtime ADD TABLE engulfing_signals;

