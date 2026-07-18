# =====================================================
# mt5_client/trade_monitor/session_utils.py
# Helper: format tanggal Indonesia + resolve trading session.
# =====================================================

from datetime import datetime, timezone, timedelta

from strategies.engulfing.signal_builder import get_trading_session_wib
from .tracker_store import save_tracked_trades


def get_indonesian_date_str() -> str:
    """Mendapatkan tanggal hari ini dalam zona waktu WIB (UTC+7)."""
    # Gunakan mapping manual hari bahasa indonesia
    hari_map = {
        0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis", 
        4: "Jumat", 5: "Sabtu", 6: "Minggu"
    }
    now = datetime.now(timezone(timedelta(hours=7)))
    hari = hari_map[now.weekday()]
    tgl = now.strftime("%d/%m/%Y")
    # File system kadang bermasalah dengan slash '/'.
    # Untuk Supabase Path, slash '/' berarti folder baru.
    # User minta format: Kamis, 11/06/2026
    # Supabase bisa handle '/', tapi kita buat aman:
    return f"{hari}, {tgl}"


def resolve_trading_session(ticket: int, info: dict, data: dict) -> str:
    """Menentukan sesi trading dari info order, fallback menggunakan get_trading_session_wib."""
    session_str = info.get("trading_session", info.get("session", "Unknown"))

    # Fallback calculation if session is Unknown and timestamp is present
    if session_str == "Unknown" and "timestamp" in info:
        try:
            dt_local = datetime.strptime(info["timestamp"], "%Y%m%d_%H%M%S")
            dt_local = dt_local.astimezone()  # Local machine timezone
            session_str = get_trading_session_wib(dt_local)

            info["trading_session"] = session_str
            save_tracked_trades(data)
        except Exception as ex:
            print(f"⚠️ Gagal menghitung session fallback untuk ticket {ticket}: {ex}")

    return session_str
