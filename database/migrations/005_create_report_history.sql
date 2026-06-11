-- =====================================================
-- SQL untuk Supabase - Report History Table
-- Menyimpan data riwayat pembuatan PDF Laporan
-- =====================================================

CREATE TABLE public.report_history (
  id uuid DEFAULT gen_random_uuid() NOT NULL,
  report_type text NOT NULL, -- DAILY, WEEKLY, MONTHLY, YEARLY, MANUAL
  report_date date NOT NULL,
  file_url text NOT NULL,
  total_trades integer DEFAULT 0,
  win_rate double precision DEFAULT 0,
  total_profit double precision DEFAULT 0,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT report_history_pkey PRIMARY KEY (id)
);

-- =====================================================
-- INSTRUKSI STORAGE BUCKET:
-- Pastikan Anda membuat Storage Bucket di menu Storage Supabase
-- dengan nama: "pdf_reports"
-- dan atur ke "Public" agar file PDF bisa didownload oleh grup WA.
-- =====================================================
