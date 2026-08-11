-- SQL Script to create `indicator_triggers` table
-- Run this in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS public.indicator_triggers (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    direction TEXT NOT NULL, -- 'BUY' or 'SELL'
    trigger_time TIMESTAMP WITH TIME ZONE NOT NULL,
    details JSONB DEFAULT '{}'::jsonb, -- e.g. {"range": 500, "body_pct": 80.5, "streak": 4}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster queries by AI
CREATE INDEX IF NOT EXISTS idx_indicator_triggers_symbol_tf ON public.indicator_triggers (symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_indicator_triggers_time ON public.indicator_triggers (trigger_time DESC);

-- Enable RLS (Optional, depending on your setup)
ALTER TABLE public.indicator_triggers ENABLE ROW LEVEL SECURITY;

-- Create policy to allow all authenticated/anon read/write (adjust as needed for your security)
CREATE POLICY "Allow all operations for anon" ON public.indicator_triggers
    FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);
    
CREATE POLICY "Allow all operations for authenticated" ON public.indicator_triggers
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);
