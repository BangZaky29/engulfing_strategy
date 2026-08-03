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

def notify_engulfing_system_status(status: str, extra_info: str = ""):
    """
    Kirim notifikasi status sistem (AKTIF / DIMATIKAN) untuk Strategi Engulfing.
    Di-broadcast ke seluruh group (OP SIGNAL, PROFIT SIGNAL, LOSS SIGNAL, INFO SIGNAL, & GROUP-MALING-SKIPPED).
    status: 'START' atau 'STOP'
    """
    private_jid = os.getenv("PRIVATE_JID")
    profit_jid = os.getenv("PROFIT_SIGNAL")
    loss_jid = os.getenv("LOSS_SIGNAL")
    info_jid = os.getenv("GROUP_JID")
    skip_maling_jid = os.getenv("SKIP_SIGNAL") or "120363427057207863@g.us"

    # Kumpulkan unique standard groups (selain group skipped)
    standard_jids = set()
    for jid in [private_jid, profit_jid, loss_jid, info_jid]:
        if jid and jid != skip_maling_jid:
            standard_jids.add(jid)

    mt5_cfg = MT5Config()
    symbols_str = ", ".join(mt5_cfg.symbols)

    if status == 'START':
        # Format Ringkas untuk Group Standar
        std_msg = (
            f"🟢 SISTEM DIAKTIFKAN 🟢\n\n"
            f"🟢 [STRATEGI: REVERSAL CANDLE SYSTEM (TUYUL MALING | ENGULFING)]"
        )
        # Format Lengkap Khusus Group SKIPPED Signal Engulfing
        skipped_msg = (
            f"🟢 SISTEM DIAKTIFKAN 🟢\n\n"
            f"🟢 [STRATEGI: REVERSAL CANDLE SYSTEM (TUYUL MALING | ENGULFING)]\n\n"
            f"⚙️ INFO CONFIG LENGKAP ENGULFING:\n"
            f"• Symbols: {symbols_str}\n"
            f"• Execute TF: {mt5_cfg.timeframes[0] if mt5_cfg.timeframes else 'M5'}\n"
            f"• Info TFs: {', '.join(mt5_cfg.info_timeframes)}\n"
            f"• Schedule: {get_trading_status_text()}\n"
            f"• Daily Guard: {get_daily_guard_status_text()}"
        )
    else:
        # Format Dimatikan untuk Group Standar & Group SKIPPED
        std_msg = (
            f"🛑 SISTEM DIMATIKAN 🛑\n\n"
            f"🛑 [STRATEGI: REVERSAL CANDLE SYSTEM (TUYUL MALING | ENGULFING)]"
        )
        skipped_msg = std_msg

    try:
        sb = get_supabase()
        outbox_rows = []

        # 1. Row untuk Standard Groups
        for jid in standard_jids:
            outbox_rows.append({
                'source_table': 'engulfing_system',
                'event_type': 'ENGULFING_SYSTEM',
                'group_jid': jid,
                'message_type': 'TEXT',
                'message': std_msg,
                'dedupe_key': f'engulf_std_{status.lower()}_{jid[:10]}_{int(time.time())}_{uuid.uuid4().hex[:4]}'
            })

        # 2. Row untuk Group SKIPPED Engulfing
        if skip_maling_jid:
            outbox_rows.append({
                'source_table': 'engulfing_system',
                'event_type': 'ENGULFING_SYSTEM',
                'group_jid': skip_maling_jid,
                'message_type': 'TEXT',
                'message': skipped_msg,
                'dedupe_key': f'engulf_skip_{status.lower()}_{int(time.time())}_{uuid.uuid4().hex[:4]}'
            })

        if outbox_rows:
            sb.table('wa_outbox').insert(outbox_rows).execute()
            print(cprint(f"📲 Broadcast Notifikasi Engulfing System ({status}) ke {len(outbox_rows)} group WA", Colors.GREEN))
    except Exception as e:
        print(cprint(f"⚠️ Gagal broadcast WA notif Engulfing System ({status}): {e}", Colors.RED))
