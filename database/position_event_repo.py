# =====================================================
# database/position_event_repo.py
# Repository: CRUD operasi untuk table 'position_events'
# =====================================================

from typing import Optional
from database.supabase_client import execute_supabase


class PositionEventRepo:
    """Repository untuk table position_events di Supabase."""

    TABLE = "position_events"

    @staticmethod
    def insert(event_data: dict) -> bool:
        """
        Insert log event posisi ke Supabase table position_events.
        Catatan: Jika tabel belum dibuat di Supabase, menangkap exception secara graceful.
        """
        try:
            execute_supabase(lambda sb: sb.table(PositionEventRepo.TABLE).insert(event_data).execute())
            return True
        except Exception as e:
            err_msg = str(e)
            if "PGRST205" in err_msg or "Could not find the table" in err_msg:
                print("⚠️ Tabel 'position_events' belum dibuat di Supabase. Silakan jalankan DDL SQL dari AllDatabase.sql.")
            else:
                print(f"⚠️ Gagal insert ke position_events: {e}")
            return False

    @staticmethod
    def get_recent(symbol: Optional[str] = None, limit: int = 50) -> list:
        """
        Membaca event posisi terbaru dari Supabase.
        
        Args:
            symbol: Filter symbol (opsional)
            limit: Batas jumlah record yang diambil
        """
        try:
            def _query(sb):
                query = sb.table(PositionEventRepo.TABLE).select("*").order("created_at", desc=True).limit(limit)
                if symbol:
                    query = query.eq("symbol", symbol)
                return query.execute()

            res = execute_supabase(_query)
            return res.data or []
        except Exception as e:
            print(f"⚠️ Gagal membaca data dari position_events: {e}")
            return []

