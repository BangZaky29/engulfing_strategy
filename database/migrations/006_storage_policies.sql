-- =====================================================
-- SQL untuk Supabase - Storage Policies
-- Memberikan izin kepada Bot untuk meng-upload PDF ke bucket
-- =====================================================

-- 1. Beri izin kepada siapa saja untuk MEMBACA (download) PDF
CREATE POLICY "Public Access to PDF Reports" 
ON storage.objects FOR SELECT 
USING (bucket_id = 'pdf_reports');

-- 2. Beri izin kepada kunci ANON (Bot Anda) untuk MENG-UPLOAD PDF
CREATE POLICY "Allow Bot Uploads to PDF Reports" 
ON storage.objects FOR INSERT 
WITH CHECK (bucket_id = 'pdf_reports');
