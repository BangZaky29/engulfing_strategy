# =====================================================
# database/supabase_client.py
# Singleton Supabase client connection with auto-reconnect & retry support
# =====================================================

from typing import Callable, TypeVar
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY

_client: Client | None = None

T = TypeVar("T")


def get_supabase(force_refresh: bool = False) -> Client | None:
    """
    Singleton Supabase client.
    Menggunakan service_role key agar bisa bypass RLS.
    Jika force_refresh=True, memaksa pembuatan instance client baru.
    """
    global _client
    if _client is None or force_refresh:
        try:
            _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            print("✅ Supabase client terhubung.")
        except Exception as e:
            print(f"❌ Gagal menginisialisasi Supabase client: {e}")
            _client = None
    return _client


def reset_client():
    """Reset client (untuk testing/reconnect)."""
    global _client
    _client = None


def execute_supabase(query_fn: Callable[[Client], T], retries: int = 2) -> T:
    """
    Menjalankan fungsi query Supabase dengan proteksi auto-reconnect dan retry
    apabila terjadi error koneksi (HTTP/2 ConnectionTerminated, stream_id, socket, dll).
    
    Example usage:
        res = execute_supabase(lambda sb: sb.table("my_table").select("*").execute())
    """
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        client = get_supabase(force_refresh=(attempt > 0))
        if client is None:
            raise RuntimeError("Supabase client gagal terhubung.")

        try:
            return query_fn(client)
        except Exception as e:
            last_err = e
            err_str = str(e)

            # Cek jika error PGRST205 (tabel tidak ditemukan di DDL) - langsung raise agar pemanggil menangani
            if "PGRST205" in err_str or "Could not find the table" in err_str:
                raise e

            # Deteksi error koneksi / HTTP2 / stream_id / protocol error
            is_conn_err = any(
                k in err_str.lower()
                for k in [
                    "connectionterminated",
                    "remoteprotocolerror",
                    "stream_id",
                    "connection",
                    "closed",
                    "httpcore",
                    "httpx",
                    "socket",
                    "winerror",
                    "timeout",
                ]
            )

            if is_conn_err and attempt < retries:
                print(f"🔄 Reconnecting Supabase client (attempt {attempt + 1}/{retries + 1}) due to error: {err_str[:120]}")
                reset_client()
            else:
                raise e

    if last_err is not None:
        raise last_err
    raise RuntimeError("Eksekusi Supabase gagal tanpa detail exception.")

