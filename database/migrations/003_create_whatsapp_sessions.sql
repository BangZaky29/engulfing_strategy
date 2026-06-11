-- Membuat tabel untuk menyimpan sesi WhatsApp (Baileys) dan QR Code
CREATE TABLE IF NOT EXISTS public.whatsapp_sessions (
  id text not null primary key, -- akan diisi 'main_session'
  status text not null default 'UNPAIRED', -- UNPAIRED, CONNECTED, LOGOUT_REQUESTED
  qr_code text, -- raw string QR code untuk di-scan
  session_data jsonb default '{}'::jsonb, -- menyimpan credentials baileys
  updated_at timestamp with time zone default now()
);

-- Mengaktifkan Realtime untuk tabel ini agar Frontend bisa langsung menerima QR Code
ALTER PUBLICATION supabase_realtime ADD TABLE whatsapp_sessions;

-- Atur Row Level Security (RLS) jika perlu
-- Saat ini kita beri akses public read/write untuk mempermudah (karena ini dashboard admin)
ALTER TABLE whatsapp_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public full access on whatsapp_sessions"
  ON whatsapp_sessions FOR ALL
  USING (true) WITH CHECK (true);

-- Membuat data awal jika belum ada
INSERT INTO public.whatsapp_sessions (id, status, session_data) 
VALUES ('main_session', 'UNPAIRED', '{}'::jsonb)
ON CONFLICT (id) DO NOTHING;
