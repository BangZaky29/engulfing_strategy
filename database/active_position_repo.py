# =====================================================
# database/active_position_repo.py
# Repository: CRUD & Sync untuk table 'position_tracker_positions'
# =====================================================

from datetime import datetime
from database.supabase_client import get_supabase


class ActivePositionRepo:
    """Repository untuk sync posisi aktif ke table position_tracker_positions di Supabase."""

    TABLE = "position_tracker_positions"

    @staticmethod
    def sync_active_positions(symbol: str, active_tracked_positions: list) -> bool:
        """
        Upsert posisi yang sedang aktif dan hapus posisi pada symbol tersebut yang sudah ditutup.
        """
        sb = get_supabase()
        if sb is None:
            return False

        try:
            now_iso = datetime.now().isoformat()
            active_tickets = []

            for pos in active_tracked_positions:
                active_tickets.append(pos.ticket)
                origin_str = pos.origin.value if hasattr(pos.origin, "value") else str(pos.origin)
                payload = {
                    "ticket": pos.ticket,
                    "symbol": pos.symbol,
                    "position_type": pos.direction,
                    "current_price": getattr(pos, "current_price", pos.open_price) or pos.open_price,
                    "volume": pos.volume,
                    "swap": round(pos.current_swap, 4),
                    "profit": round(pos.current_profit, 2),
                    "margin": getattr(pos, "margin", 0.0) or 0.0,
                    "magic_number": pos.magic_number,
                    "comment": pos.comment,
                    "opened_at": pos.open_time.isoformat() if pos.open_time else now_iso,
                    "last_checked_at": now_iso,
                    "is_managed": True,
                    "origin": origin_str,
                    "entry_price": pos.open_price,
                    "sl_price": getattr(pos, "sl_price", 0.0) or 0.0,
                    "tp_price": getattr(pos, "tp_price", 0.0) or 0.0,
                }
                sb.table(ActivePositionRepo.TABLE).upsert(payload, on_conflict="ticket").execute()

            # Clean up: Hapus posisi aktif di Supabase untuk symbol ini yang sudah ditutup
            if active_tickets:
                sb.table(ActivePositionRepo.TABLE).delete().eq("symbol", symbol).not_in("ticket", active_tickets).execute()
            else:
                sb.table(ActivePositionRepo.TABLE).delete().eq("symbol", symbol).execute()

            return True
        except Exception as e:
            err_msg = str(e)
            if "PGRST205" in err_msg or "Could not find the table" in err_msg:
                # Supabase table belum dibuat via DDL SQL editor, abaikan agar bot tidak crash
                pass
            else:
                print(f"⚠️ Gagal sync active positions ke Supabase ({symbol}): {e}")
            return False
