# =====================================================
# strategies/strategy_rcs/rcs_notifier.py
# Mengirim notifikasi RCS ke WhatsApp dan Console
# =====================================================

import os
import time
import uuid
from datetime import datetime
import MetaTrader5 as mt5

from database.supabase_client import get_supabase
from database.supabase_storage import upload_screenshot
from mt5_client.visualizer import generate_screenshot
from config.mt5_config import MT5Config, EMAConfig
from config.rcs_config import RCSConfig
from utils.colors import cprint, Colors

HEADER_TEXT = "🤖 *[STRATEGI: REVERSAL CANDLE SYSTEM (TUYUL COPET | RCS)]*\n\n"

def send_rcs_wa_notif(config: RCSConfig, message: str, event_type: str, target_jid: str | None = None, media_url: str | None = None):
    """Fungsi helper untuk kirim pesan ke Supabase WA Outbox dengan routing JID"""
    # Gunakan target_jid yang spesifik, fallback ke group_jid jika tidak ditentukan
    dest_jid = target_jid if target_jid else config.group_jid
    if not dest_jid:
        return
        
    supabase = get_supabase()
    if supabase is None:
        return
        
    full_message = HEADER_TEXT + message
    message_type = 'IMAGE' if media_url else 'TEXT'
    
    payload = {
        'source_table': 'rcs_system',
        'event_type': event_type,
        'group_jid': dest_jid,
        'message_type': message_type,
        'message': full_message,
        'dedupe_key': f'rcs_{event_type}_{int(time.time())}_{uuid.uuid4().hex[:8]}'
    }
    
    if media_url:
        payload['image_url'] = media_url
        
    try:
        supabase.table('wa_outbox').insert(payload).execute()
        print(cprint(f"📲 Notifikasi WA {event_type} terkirim ke {dest_jid}", Colors.GREEN))
    except Exception as e:
        print(cprint(f"⚠️ Gagal kirim WA notif ({event_type}): {e}", Colors.RED))

def generate_and_upload_rcs_screenshot(state, config: RCSConfig) -> str:
    """Generates screenshot menggunakan Timeframe dinamis RCS_SIGNAL_TIMEFRAME dan mengunggah ke Supabase Storage."""
    try:
        symbol = config.symbol
        tf_label = config.signal_timeframe
        mt5_cfg = MT5Config()
        tf_const = mt5_cfg.get_mt5_timeframe(tf_label)
        
        rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, 50)
        if rates is None or len(rates) == 0:
            return ""
            
        ticket = state.op1_ticket or 0
        op_price = state.op1_level or 0.0
        sl_price = state.op3_level or 0.0
        tp_price = state.tp1_price or 0.0
        mode = state.trigger_direction or "BUY"
        
        img_path = generate_screenshot(
            rates=rates,
            ticket_id=ticket,
            op_price=op_price,
            sl_price=sl_price,
            tp_price=tp_price,
            ema_cfg=EMAConfig(),
            mode=mode,
            tf_label=tf_label,
            output_dir="temp_screenshots",
            num_candles=40
        )
        
        if img_path and os.path.exists(img_path):
            folder_date = datetime.now().strftime("%Y-%m-%d")
            filename = f"RCS_{mode}_{symbol}_{tf_label}_{ticket}_{int(time.time())}.png"
            new_path = os.path.join("temp_screenshots", filename)
            os.rename(img_path, new_path)
            
            success, public_url = upload_screenshot(new_path, "engulfing", folder_date, filename)
            if os.path.exists(new_path):
                os.remove(new_path)
                
            if success:
                return public_url
    except Exception as e:
        print(cprint(f"⚠️ Gagal generate/upload RCS screenshot: {e}", Colors.RED))
        
    return ""

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
    # Target: PRIVATE_JID
    send_rcs_wa_notif(config, msg, 'RCS_TRIGGER', target_jid=config.private_jid)

def notify_skip(symbol: str, pattern: str, direction: str, reason: str, config: RCSConfig):
    if not config.notif_skip: return
    msg = (
        f"⏭️ *RCS TRIGGER SKIPPED*\n\n"
        f"Symbol: {symbol}\n"
        f"Pattern: {pattern}\n"
        f"Arah: *{direction}*\n\n"
        f"Alasan: {reason}"
    )
    # Target: RCS_GROUP_JID
    send_rcs_wa_notif(config, msg, 'RCS_SKIP', target_jid=config.group_jid)

def notify_open(symbol: str, phase_name: str, ticket: int, price: float, target: float, config: RCSConfig):
    if not config.notif_open: return
    msg = (
        f"✅ *RCS {phase_name} TERBUKA*\n\n"
        f"Symbol: {symbol}\n"
        f"Ticket: {ticket}\n"
        f"Harga: {price:.5f}\n"
        f"Target TP: {target:.5f}"
    )
    # Target: PRIVATE_JID
    send_rcs_wa_notif(config, msg, 'RCS_OPEN', target_jid=config.private_jid)

def notify_freeze(symbol: str, floating_usd: float, config: RCSConfig):
    if not config.notif_freeze: return
    msg = (
        f"❄️ *RCS PHASE FREEZE*\n\n"
        f"Symbol: {symbol}\n"
        f"Posisi telah terkunci (Hedge).\n"
        f"Snapshot Floating: *${floating_usd:.2f}*\n\n"
        f"Menunggu posisi ditutup manual oleh trader..."
    )
    # Target: PRIVATE_JID
    send_rcs_wa_notif(config, msg, 'RCS_FREEZE', target_jid=config.private_jid)

def notify_result(symbol: str, event_desc: str, profit: float, recovery: float, config: RCSConfig, state=None):
    if not config.notif_result: return
    
    # 1. Generate & Upload Screenshot if state is provided
    media_url = ""
    if state is not None:
        media_url = generate_and_upload_rcs_screenshot(state, config)
        
    msg = (
        f"📊 *RCS RESULT*\n\n"
        f"Symbol: {symbol}\n"
        f"Info: {event_desc}\n"
        f"Closed PnL: *${profit:.2f}*\n"
    )
    if recovery != 0.0:
        msg += f"Hasil Recovery: *${recovery:.2f}*"
        
    # Determine target group based on Profit or Loss
    target_group = config.profit_signal_jid if profit > 0 else config.loss_signal_jid
    
    send_rcs_wa_notif(config, msg, 'RCS_RESULT', target_jid=target_group, media_url=media_url if media_url else None)
