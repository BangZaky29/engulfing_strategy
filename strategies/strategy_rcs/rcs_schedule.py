# =====================================================
# strategies/strategy_rcs/rcs_schedule.py
# Modul Scheduler Jam Eksekusi Trading RCS (TUYUL COPET)
# =====================================================

from datetime import datetime
from config.rcs_config import RCSConfig

def is_rcs_trading_active(config: RCSConfig) -> bool:
    """
    Cek apakah waktu sekarang berada di dalam jam eksekusi RCS.
    Jika rcs_trading_active_enabled == False, selalu return True (selalu boleh trade / 24 Jam).
    Default window: 06:00 -> 12:00 WIB.
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


def get_rcs_schedule_wa_summary(config: RCSConfig) -> str:
    """Format status jadwal untuk notifikasi WA startup."""
    if not config.rcs_trading_active_enabled:
        return "🟢 *SELALU AKTIF (24 Jam Nonstop)*"
    
    if is_rcs_trading_active(config):
        return f"🟢 *AKTIF (Boleh Eksekusi OP1)* [{config.rcs_trading_active_start} – {config.rcs_trading_active_end} WIB]"
    else:
        return f"⏸️ *STANDBY / PAUSED (Luar Jam Kerja - Sistem TIDAK AKAN melakukan eksekusi)* [{config.rcs_trading_active_start} – {config.rcs_trading_active_end} WIB]"


_last_schedule_active_state: bool | None = None

def check_and_notify_rcs_schedule_transition(configs: dict[str, RCSConfig]) -> None:
    """
    Memantau transisi jadwal eksekusi RCS secara realtime.
    Kirim notifikasi WA ke RCS_GROUP_JID tepat 1 kali ketika waktu memasuki/keluar jam kerja.
    """
    global _last_schedule_active_state
    if not configs:
        return

    first_config = list(configs.values())[0]
    if not first_config.rcs_trading_active_enabled:
        return

    is_currently_active = is_rcs_trading_active(first_config)

    # Inisialisasi state awal saat bot baru start tanpa kirim notifikasi dobel
    if _last_schedule_active_state is None:
        _last_schedule_active_state = is_currently_active
        return

    # Jika terjadi perubahan status transisi
    if is_currently_active != _last_schedule_active_state:
        _last_schedule_active_state = is_currently_active
        now_str = datetime.now().strftime("%H:%M")
        
        from utils.colors import Colors, cprint
        from strategies.strategy_rcs.rcs_notifier import notify_rcs_schedule_change
        
        if is_currently_active:
            print(cprint(f"⏰ [RCS SCHEDULE] Jam kerja Copet dimulai ({first_config.rcs_trading_active_start} → {first_config.rcs_trading_active_end} WIB). Eksekusi OP1 AKTIF 🟢", Colors.GREEN))
            notify_rcs_schedule_change("SCHEDULE_OPEN", first_config, now_str)
        else:
            print(cprint(f"⏰ [RCS SCHEDULE] Jam kerja Copet selesai ({first_config.rcs_trading_active_start} → {first_config.rcs_trading_active_end} WIB). Eksekusi OP1 PAUSED ⏸️", Colors.YELLOW))
            notify_rcs_schedule_change("SCHEDULE_PAUSED", first_config, now_str)

