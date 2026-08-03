# =====================================================
# app/engulfing_notifier.py
# Notifikasi Status Sistem untuk Strategi Engulfing (TUYUL MALING)
# =====================================================

import os
import time
import uuid
from database.supabase_client import get_supabase
from config.mt5_config import MT5Config
from config.trading_schedule import get_trading_status_text
from config.daily_guard import get_daily_guard_status_text
from utils.colors import cprint, Colors

HEADER_TEXT = "🤖 *[STRATEGI: REVERSAL CANDLE SYSTEM (TUYUL MALING | ENGULFING)]*\n\n"

def notify_engulfing_system_status(status: str, extra_info: str = ""):
    """
    Kirim notifikasi status sistem (AKTIF / DIMATIKAN) untuk Strategi Engulfing ke WhatsApp Outbox.
    status: 'START' atau 'STOP'
    """
    dest_jid = os.getenv("SKIP_SIGNAL") or os.getenv("GROUP_JID") or os.getenv("PRIVATE_JID")
    if not dest_jid:
        return

    mt5_cfg = MT5Config()
    symbols_str = ", ".join(mt5_cfg.symbols)

    if status == 'START':
        msg = (
            f"{HEADER_TEXT}"
            f"🟢 *SISTEM AKTIF* 🟢\n\n"
            f"Bot trading Engulfing (Tuyul Maling) telah berhasil dinyalakan dan siap memantau pasar.\n\n"
            f"• Symbols: {symbols_str}\n"
            f"• Schedule: {get_trading_status_text()}\n"
            f"• Daily Guard: {get_daily_guard_status_text()}"
        )
    else:
        msg = (
            f"{HEADER_TEXT}"
            f"🛑 *SISTEM telah di matikan* 🛑\n\n"
            f"Bot trading Engulfing (Tuyul Maling) telah dihentikan / dimatikan.\n\n"
            f"• Symbols: {symbols_str}"
        )
        if extra_info:
            msg += f"\n• Catatan: {extra_info}"

    try:
        sb = get_supabase()
        payload = {
            'source_table': 'engulfing_system',
            'event_type': 'ENGULFING_SYSTEM',
            'group_jid': dest_jid,
            'message_type': 'TEXT',
            'message': msg,
            'dedupe_key': f'engulfing_sys_{status.lower()}_{int(time.time())}_{uuid.uuid4().hex[:6]}'
        }
        sb.table('wa_outbox').insert(payload).execute()
        print(cprint(f"📲 Notifikasi Engulfing System ({status}) terkirim ke WA Outbox ({dest_jid})", Colors.GREEN))
    except Exception as e:
        print(cprint(f"⚠️ Gagal kirim WA notif Engulfing System ({status}): {e}", Colors.RED))
