-- =====================================================
-- SQL untuk Supabase - Tambah Kolom Screenshot di Pending Logs & Kebijakan Storage
-- File: 008_add_active_logs_image_url.sql
-- =====================================================

-- 1. Tambah kolom image_url ke tabel trade_active_logs (jika belum ada)
ALTER TABLE public.trade_active_logs 
ADD COLUMN IF NOT EXISTS image_url TEXT;

COMMENT ON COLUMN public.trade_active_logs.image_url IS 'URL screenshot chart MT5 saat pending order expired/dibatalkan';

-- 2. Kebijakan Storage untuk bucket order_expired (jika RLS aktif)
DROP POLICY IF EXISTS "Public Access to Order Expired Bucket" ON storage.objects;
DROP POLICY IF EXISTS "Allow Bot Uploads to Order Expired Bucket" ON storage.objects;

CREATE POLICY "Public Access to Order Expired Bucket" 
ON storage.objects FOR SELECT 
USING (bucket_id = 'order_expired');

CREATE POLICY "Allow Bot Uploads to Order Expired Bucket" 
ON storage.objects FOR INSERT 
WITH CHECK (bucket_id = 'order_expired');
