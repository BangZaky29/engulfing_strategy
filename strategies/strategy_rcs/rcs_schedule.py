# =====================================================
# strategies/strategy_rcs/rcs_schedule.py
# Modul Scheduler Jam Eksekusi Trading RCS (TUYUL COPET)
# =====================================================

from datetime import datetime
from config.rcs_config import RCSConfig

def is_rcs_trading_active(config: RCSConfig) -> bool:
    """
    Cek apakah waktu sekarang berada di dalam jam eksekusi RCS.
    Jika rcs_trading_active_enabled == False, selalu return True (selalu boleh trade).
    Default window: 05:00 -> 15:00 WIB.
    """
    if not config.rcs_trading_active_enabled:
        return True

    now = datetime.now().time()

    try:
        start = datetime.strptime(config.rcs_trading_active_start, "%H:%M").time()
        end = datetime.strptime(config.rcs_trading_active_end, "%H:%M").time()
    except ValueError:
        print(f"[WARNING] Format RCS_TRADING_ACTIVE_START/END tidak valid: {config.rcs_trading_active_start}/{config.rcs_trading_active_end}")
        return True

    if start > end:
        # Overnight window (misal 22:00 -> 06:00)
        return now >= start or now < end
    else:
        # Normal window (misal 05:00 -> 15:00)
        return start <= now < end

def get_rcs_trading_status_text(config: RCSConfig) -> str:
    """Return status teks untuk logging."""
    if not config.rcs_trading_active_enabled:
        return "ALWAYS ACTIVE (schedule disabled)"

    if is_rcs_trading_active(config):
        return f"ACTIVE (window: {config.rcs_trading_active_start} → {config.rcs_trading_active_end} WIB)"
    else:
        return f"PAUSED (outside window: {config.rcs_trading_active_start} → {config.rcs_trading_active_end} WIB)"
