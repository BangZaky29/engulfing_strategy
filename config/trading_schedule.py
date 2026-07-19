# =====================================================
# config/trading_schedule.py
# Trading Time Window — control kapan bot boleh execute order.
#
# Bot tetap jalan 24/7 (infinite loop), tapi hanya execute
# order di jam tertentu. Di luar jam aktif, bot tetap scan
# dan kumpulkan data ke Supabase.
#
# ⛔ DISABLED by default (TRADING_ACTIVE_ENABLED=false)
#    Aktifkan di .env saat deploy ke production server.
# =====================================================

import os
from datetime import datetime


# === Load from .env ===
TRADING_ACTIVE_ENABLED: bool = os.getenv("TRADING_ACTIVE_ENABLED", "false").lower() == "true"
TRADING_ACTIVE_START: str = os.getenv("TRADING_ACTIVE_START", "15:00")   # WIB
TRADING_ACTIVE_END: str = os.getenv("TRADING_ACTIVE_END", "04:00")       # WIB (keesokan hari)


def is_trading_active() -> bool:
    """
    Cek apakah sekarang dalam jam trading aktif.

    Jika TRADING_ACTIVE_ENABLED=false, selalu return True
    (perilaku lama — bot selalu boleh trade).

    Jika enabled, cek apakah waktu sekarang berada di antara
    TRADING_ACTIVE_START dan TRADING_ACTIVE_END.

    Mendukung overnight window (misal 15:00 → 04:00).
    """
    if not TRADING_ACTIVE_ENABLED:
        return True  # Disabled = selalu aktif (perilaku lama)

    now = datetime.now().time()

    try:
        start = datetime.strptime(TRADING_ACTIVE_START, "%H:%M").time()
        end = datetime.strptime(TRADING_ACTIVE_END, "%H:%M").time()
    except ValueError:
        # Jika format salah, fallback ke selalu aktif
        print(f"[WARNING] Format TRADING_ACTIVE_START/END tidak valid: {TRADING_ACTIVE_START}/{TRADING_ACTIVE_END}")
        return True

    # Handle overnight window (contoh: 15:00 → 04:00)
    if start > end:
        # Aktif jika sekarang >= start ATAU sekarang < end
        return now >= start or now < end
    else:
        # Normal window (contoh: 09:00 → 17:00)
        return start <= now < end


def get_trading_status_text() -> str:
    """Return status text untuk logging."""
    if not TRADING_ACTIVE_ENABLED:
        return "ALWAYS ACTIVE (schedule disabled)"

    if is_trading_active():
        return f"ACTIVE (window: {TRADING_ACTIVE_START} → {TRADING_ACTIVE_END} WIB)"
    else:
        return f"PAUSED (outside window: {TRADING_ACTIVE_START} → {TRADING_ACTIVE_END} WIB)"
