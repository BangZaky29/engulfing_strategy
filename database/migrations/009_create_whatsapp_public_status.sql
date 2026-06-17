-- Migration: 009_create_whatsapp_public_status.sql
-- Create public table for WhatsApp status check & logout request (accessible by frontend/anon/authenticated)

-- 1. Create table whatsapp_public_status
CREATE TABLE IF NOT EXISTS public.whatsapp_public_status (
  id text NOT NULL,
  status text NOT NULL DEFAULT 'UNPAIRED'::text,
  qr_code text,
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT whatsapp_public_status_pkey PRIMARY KEY (id)
);

-- 2. Enable Row Level Security (RLS)
ALTER TABLE public.whatsapp_public_status ENABLE ROW LEVEL SECURITY;

-- 3. Grant SELECT, UPDATE privileges to anon and authenticated roles
GRANT SELECT, UPDATE ON TABLE public.whatsapp_public_status TO anon;
GRANT SELECT, UPDATE ON TABLE public.whatsapp_public_status TO authenticated;
GRANT ALL ON TABLE public.whatsapp_public_status TO service_role;

-- 4. Create policy for SELECT access
DROP POLICY IF EXISTS "Allow select whatsapp_public_status" ON public.whatsapp_public_status;
CREATE POLICY "Allow select whatsapp_public_status" 
ON public.whatsapp_public_status 
FOR SELECT 
TO anon, authenticated, service_role
USING (true);

-- 5. Create policy for UPDATE access for anon and authenticated (frontend)
DROP POLICY IF EXISTS "Allow anon update whatsapp_public_status" ON public.whatsapp_public_status;
CREATE POLICY "Allow anon update whatsapp_public_status" 
ON public.whatsapp_public_status 
FOR UPDATE 
TO anon 
USING (true) 
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow auth update whatsapp_public_status" ON public.whatsapp_public_status;
CREATE POLICY "Allow auth update whatsapp_public_status" 
ON public.whatsapp_public_status 
FOR UPDATE 
TO authenticated 
USING (true) 
WITH CHECK (true);

-- 6. Create policy for service_role full control
DROP POLICY IF EXISTS "Allow service_role full access on whatsapp_public_status" ON public.whatsapp_public_status;
CREATE POLICY "Allow service_role full access on whatsapp_public_status"
ON public.whatsapp_public_status
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- 7. Seed initial main session row
INSERT INTO public.whatsapp_public_status (id, status, qr_code, updated_at)
VALUES ('main_session', 'UNPAIRED', NULL, now())
ON CONFLICT (id) DO NOTHING;
