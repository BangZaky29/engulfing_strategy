# =====================================================
# mt5_client/autotrading_guard.py
# Monitor Realtime Transisi Status AutoTrading MT5
# =====================================================

import os
import time
import uuid
import MetaTrader5 as mt5
from database.supabase_client import execute_supabase
from utils.colors import cprint, Colors

_last_autotrading_state: dict[int, bool] = {}

def init_autotrading_state():
    """Inisialisasi status awal AutoTrading saat bot startup."""
    global _last_autotrading_state
    term = mt5.terminal_info()
    acc = mt5.account_info()
    login = getattr(acc, "login", 0) if acc else 0
    is_allowed = bool(getattr(term, "trade_allowed", False)) if term else False
    if login > 0:
        _last_autotrading_state[login] = is_allowed

def check_and_notify_autotrading_change(strategy_name: str, target_jid: str = ""):
    """
    Mengecek apakah ada perubahan status tombol Algo Trading di MT5 secara realtime.
    Jika status berubah dari DISABLED -> ALLOWED (atau sebaliknya), infokan ke Terminal & WA!
    """
    global _last_autotrading_state
    term = mt5.terminal_info()
    acc = mt5.account_info()

    if not term or not acc:
        return

    login = getattr(acc, "login", 0)
    server = getattr(acc, "server", "")
    is_allowed = bool(getattr(term, "trade_allowed", False))

    if login not in _last_autotrading_state:
        _last_autotrading_state[login] = is_allowed
        return

    prev_state = _last_autotrading_state[login]

    # Transisi 1: DISABLED -> ALLOWED (User baru saja klik tombol Algo Trading di MT5!)
    if not prev_state and is_allowed:
        _last_autotrading_state[login] = True
        msg_console = f"🟢 [AUTOTRADING AKTIF] Tombol Algo Trading pada terminal MT5 ({login} | {server}) telah DIAKTIFKAN! Sistem eksekusi trading [{strategy_name.upper()}] kini SIAP berjalan."
        print(cprint(msg_console, Colors.GREEN))

        dest_jid = target_jid or os.getenv("PRIVATE_JID") or os.getenv("RCS_GROUP_JID") or "120363409493021715@g.us"
        wa_text = (
            f"🟢 *AUTOTRADING DIAKTIFKAN* 🟢\n\n"
            f"Akun: *{login}* ({server})\n"
            f"Strategi: *{strategy_name.upper()}*\n"
            f"Status: AutoTrading telah *AKTIF (ALLOWED 🟢)*.\n\n"
            f"✅ Sistem eksekusi trading otomatis kini SIAP berjalan normal."
        )
        _send_autotrading_wa(dest_jid, strategy_name, wa_text, "AUTOTRADING_ENABLED")

    # Transisi 2: ALLOWED -> DISABLED (Tombol Algo Trading dimatikan oleh user di MT5)
    elif prev_state and not is_allowed:
        _last_autotrading_state[login] = False
        msg_console = f"🔴 [AUTOTRADING NONAKTIF] Tombol Algo Trading pada terminal MT5 ({login} | {server}) DIMATIKAN! Order tidak dapat dieksekusi."
        print(cprint(msg_console, Colors.RED))

        dest_jid = target_jid or os.getenv("PRIVATE_JID") or os.getenv("RCS_GROUP_JID") or "120363409493021715@g.us"
        wa_text = (
            f"🔴 *AUTOTRADING DINONAKTIFKAN* 🔴\n\n"
            f"Akun: *{login}* ({server})\n"
            f"Strategi: *{strategy_name.upper()}*\n"
            f"Status: AutoTrading *NONAKTIF (DISABLED 🔴)*.\n\n"
            f"⚠️ Harap klik tombol *'Algo Trading' 🟢* di jendela MetaTrader 5 agar bot dapat mengeksekusi order."
        )
        _send_autotrading_wa(dest_jid, strategy_name, wa_text, "AUTOTRADING_DISABLED")

def _send_autotrading_wa(dest_jid: str, strategy_name: str, message: str, event_type: str):
    """Kirim pesan outbox ke Supabase."""
    payload = {
        'source_table': f'{strategy_name.lower()}_system',
        'event_type': event_type,
        'group_jid': dest_jid,
        'message_type': 'TEXT',
        'message': message,
        'dedupe_key': f'autotrade_{event_type}_{int(time.time())}_{uuid.uuid4().hex[:6]}'
    }
    try:
        execute_supabase(lambda sb: sb.table('wa_outbox').insert(payload).execute())
        print(cprint(f"📲 Notifikasi WA {event_type} terkirim ke {dest_jid}", Colors.GREEN))
    except Exception as e:
        print(cprint(f"⚠️ Gagal kirim WA notif AutoTrading: {e}", Colors.RED))
