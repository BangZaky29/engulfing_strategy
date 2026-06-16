-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.candles (
  id bigint NOT NULL DEFAULT nextval('candles_id_seq'::regclass),
  symbol character varying NOT NULL,
  timeframe character varying NOT NULL,
  timestamp timestamp with time zone NOT NULL,
  open_ double precision NOT NULL,
  high_ double precision NOT NULL,
  low_ double precision NOT NULL,
  close_ double precision NOT NULL,
  volume double precision DEFAULT 0,
  spread double precision DEFAULT 0,
  ema_fast double precision,
  ema_slow double precision,
  body_size double precision,
  upper_wick double precision,
  lower_wick double precision,
  is_bullish boolean,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT candles_pkey PRIMARY KEY (id)
);
CREATE TABLE public.engulfing_signals (
  id bigint NOT NULL DEFAULT nextval('engulfing_signals_id_seq'::regclass),
  symbol character varying NOT NULL,
  timeframe character varying NOT NULL,
  signal_time timestamp with time zone NOT NULL,
  pattern_type character varying NOT NULL CHECK (pattern_type::text = ANY (ARRAY['bullish_engulfing'::character varying, 'bearish_engulfing'::character varying]::text[])),
  prev_open double precision NOT NULL,
  prev_close double precision NOT NULL,
  prev_high double precision NOT NULL,
  prev_low double precision NOT NULL,
  curr_open double precision NOT NULL,
  curr_close double precision NOT NULL,
  curr_high double precision NOT NULL,
  curr_low double precision NOT NULL,
  engulf_ratio double precision,
  ema_fast_value double precision,
  ema_slow_value double precision,
  ema_trend character varying,
  confidence_score double precision,
  is_confirmed boolean DEFAULT false,
  notes text,
  created_at timestamp with time zone DEFAULT now(),
  skip_reason text,
  ticket_id bigint,
  trading_session character varying,
  CONSTRAINT engulfing_signals_pkey PRIMARY KEY (id)
);
CREATE TABLE public.engulfing_stats (
  id bigint NOT NULL DEFAULT nextval('engulfing_stats_id_seq'::regclass),
  symbol character varying NOT NULL,
  timeframe character varying NOT NULL,
  date date NOT NULL,
  total_bullish integer DEFAULT 0,
  total_bearish integer DEFAULT 0,
  avg_confidence double precision DEFAULT 0,
  highest_confidence double precision DEFAULT 0,
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT engulfing_stats_pkey PRIMARY KEY (id)
);
CREATE TABLE public.trade_analytics (
  id bigint NOT NULL DEFAULT nextval('trade_analytics_id_seq'::regclass),
  ticket_id bigint NOT NULL UNIQUE,
  symbol character varying NOT NULL,
  timeframe character varying NOT NULL,
  mode character varying NOT NULL CHECK (mode::text = ANY (ARRAY['BUY'::character varying, 'SELL'::character varying]::text[])),
  result character varying NOT NULL CHECK (result::text = ANY (ARRAY['PROFIT'::character varying, 'LOSS'::character varying]::text[])),
  op_price double precision,
  sl_price double precision,
  tp_price double precision,
  profit double precision,
  entry_time timestamp with time zone,
  exit_time timestamp with time zone,
  image_url text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  trading_session character varying,
  CONSTRAINT trade_analytics_pkey PRIMARY KEY (id)
);
CREATE TABLE public.whatsapp_sessions (
  id text NOT NULL,
  status text NOT NULL DEFAULT 'UNPAIRED'::text,
  qr_code text,
  session_data jsonb DEFAULT '{}'::jsonb,
  updated_at timestamp with time zone DEFAULT now(),
  owner_id text,
  locked_at timestamp with time zone,
  CONSTRAINT whatsapp_sessions_pkey PRIMARY KEY (id)
);
CREATE TABLE public.report_history (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  report_type text NOT NULL,
  report_date date NOT NULL,
  file_url text NOT NULL,
  total_trades integer DEFAULT 0,
  win_rate double precision DEFAULT 0,
  total_profit double precision DEFAULT 0,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT report_history_pkey PRIMARY KEY (id)
);
CREATE TABLE public.whatsapp_auth_keys (
  session_id text NOT NULL,
  key_type text NOT NULL,
  key_id text NOT NULL,
  value jsonb NOT NULL,
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT whatsapp_auth_keys_pkey PRIMARY KEY (session_id, key_type, key_id),
  CONSTRAINT whatsapp_auth_keys_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.whatsapp_sessions(id)
);
CREATE TABLE public.trade_active_logs (
  id bigint NOT NULL DEFAULT nextval('trade_active_logs_id_seq'::regclass),
  ticket_id bigint NOT NULL UNIQUE,
  symbol character varying NOT NULL,
  mode character varying NOT NULL CHECK (mode::text = ANY (ARRAY['BUY'::character varying, 'SELL'::character varying]::text[])),
  message text NOT NULL,
  op_price double precision,
  sl_price double precision,
  tp_price double precision,
  created_at timestamp with time zone DEFAULT now(),
  trading_session character varying,
  CONSTRAINT trade_active_logs_pkey PRIMARY KEY (id)
);