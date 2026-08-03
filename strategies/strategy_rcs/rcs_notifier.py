# =====================================================
# strategies/strategy_rcs/rcs_notifier.py
# Mengirim notifikasi RCS ke WhatsApp dan Console
# =====================================================

import time
import uuid
from database.supabase_client import get_supabase
from config.rcs_config import RCSConfig
from utils.colors import cprint, Colors

def send_rcs_wa_notif(config: RCSConfig, message: str, event_type: str):
    """Fungsi helper untuk kirim pesan ke Supabase WA Outbox"""
    if not config.group_jid:
        return
        
    supabase = get_supabase()
    if supabase is None:
        return
        
    try:
        supabase.table('wa_outbox').insert({
            'source_table': 'rcs_system',
            'event_type': event_type,
            'group_jid': config.group_jid,
            'message_type': 'TEXT',
            'message': message,
            'dedupe_key': f'rcs_{event_type}_{int(time.time())}_{uuid.uuid4().hex[:8]}'
        }).execute()
    except Exception as e:
        print(cprint(f"⚠️ Gagal kirim WA notif ({event_type}): {e}", Colors.RED))

def notify_trigger(symbol: str, pattern: str, direction: str, state, config: RCSConfig):
    if not config.notif_trigger: return
    msg = (
        f"🎯 *RCS TRIGGER VALID*\n\n"
        f"Symbol: {symbol}\n"
        f"Pattern: {pattern}\n"
        f"Arah: *{direction}*\n\n"
        f"Level OP1: {state.op1_level:.5f} | TP1: {state.tp1_price:.5f}\n"
        f"Level OP2: {state.op2_level:.5f} | TP2: {state.tp2_price:.5f}\n"
        f"Level OP3: {state.op3_level:.5f} | Mode: {config.op3_mode}"
    )
    send_rcs_wa_notif(config, msg, 'RCS_TRIGGER')

def notify_skip(symbol: str, pattern: str, direction: str, reason: str, config: RCSConfig):
    if not config.notif_skip: return
    msg = (
        f"⏭️ *RCS TRIGGER SKIPPED*\n\n"
        f"Symbol: {symbol}\n"
        f"Pattern: {pattern}\n"
        f"Arah: *{direction}*\n\n"
        f"Alasan: {reason}"
    )
    send_rcs_wa_notif(config, msg, 'RCS_SKIP')

def notify_open(symbol: str, phase_name: str, ticket: int, price: float, target: float, config: RCSConfig):
    if not config.notif_open: return
    msg = (
        f"✅ *RCS {phase_name} TERBUKA*\n\n"
        f"Symbol: {symbol}\n"
        f"Ticket: {ticket}\n"
        f"Harga: {price:.5f}\n"
        f"Target TP: {target:.5f}"
    )
    send_rcs_wa_notif(config, msg, 'RCS_OPEN')

def notify_freeze(symbol: str, floating_usd: float, config: RCSConfig):
    if not config.notif_freeze: return
    msg = (
        f"❄️ *RCS PHASE FREEZE*\n\n"
        f"Symbol: {symbol}\n"
        f"Posisi telah terkunci (Hedge).\n"
        f"Snapshot Floating: *${floating_usd:.2f}*\n\n"
        f"Menunggu posisi ditutup manual oleh trader..."
    )
    send_rcs_wa_notif(config, msg, 'RCS_FREEZE')

def notify_result(symbol: str, event_desc: str, profit: float, recovery: float, config: RCSConfig):
    if not config.notif_result: return
    msg = (
        f"📊 *RCS RESULT*\n\n"
        f"Symbol: {symbol}\n"
        f"Info: {event_desc}\n"
        f"Closed PnL: *${profit:.2f}*\n"
    )
    if recovery != 0.0:
        msg += f"Hasil Recovery: *${recovery:.2f}*"
        
    send_rcs_wa_notif(config, msg, 'RCS_RESULT')
