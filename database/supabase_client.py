# =====================================================
# database/supabase_client.py
# Singleton Supabase client connection
# =====================================================

from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY

_client: Client | None = None


def get_supabase() -> Client:
    """
    Singleton Supabase client.
    Menggunakan service_role key agar bisa bypass RLS.
    """
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print("✅ Supabase client terhubung.")
    return _client


def reset_client():
    """Reset client (untuk testing/reconnect)."""
    global _client
    _client = None
