import os
import time
import uuid
import threading
from datetime import datetime
import MetaTrader5 as mt5

from database.supabase_client import execute_supabase
from database.supabase_storage import upload_screenshot
from mt5_client.visualizer import generate_screenshot
from config.mt5_config import MT5Config, EMAConfig
from utils.colors import cprint, Colors

HEADER_TEXT = ""

_last_mrcv_notif_times = {}
_mrcv_notif_lock = threading.Lock()
COOLDOWN_EVENTS = {
    "MRCV_MAX_LOSS_CLOSE_ALL": 60,   # Cooldown 60 detik per-JID
    "MRCV_HANGING_PAUSED": 60,       # Cooldown 60 detik per-JID
    "MRCV_POSITIONS_CLEARED": 30,     # Cooldown 30 detik per-JID
}

def _send_wa_notif_worker(
    message: str,
    event_type: str,
    target_jid: str | None = None,
    media_url: str | None = None,
    include_header: bool = False,
):
    mrcv_group = os.getenv("MRCV_GROUP_JID", "120363430592783067@g.us")
    dest_jid = target_jid if target_jid else mrcv_group
    if not dest_jid:
        return

    # Check Rate-Limiting / Cooldown
    key = (event_type, dest_jid)
    cooldown = COOLDOWN_EVENTS.get(event_type, 3)
    now = time.time()
    with _mrcv_notif_lock:
        last_t = _last_mrcv_notif_times.get(key, 0.0)
        if (now - last_t) < cooldown:
            print(cprint(f"⏳ Notifikasi WA {event_type} ke {dest_jid} di-throttle (cooldown {cooldown}s).", Colors.GRAY))
            return
        _last_mrcv_notif_times[key] = now

    full_message = (HEADER_TEXT + message) if include_header else message
    message_type = 'IMAGE' if media_url else 'TEXT'

    payload = {
        'source_table': 'mrcv_system',
        'event_type': event_type,
        'group_jid': dest_jid,
        'message_type': message_type,
        'message': full_message,
        'dedupe_key': f'mrcv_{event_type}_{int(time.time())}_{uuid.uuid4().hex[:8]}'
    }

    if media_url:
        payload['image_url'] = media_url

    try:
        execute_supabase(lambda sb: sb.table('wa_outbox').insert(payload).execute())
        print(cprint(f"📲 Notifikasi WA {event_type} terkirim ke {dest_jid}", Colors.GREEN))
    except Exception as e:
        print(cprint(f"⚠️ Gagal kirim WA notif MRCV ({event_type}): {e}", Colors.RED))

def send_mrcv_wa_notif(
    message: str,
    event_type: str,
    target_jid: str | None = None,
    media_url: str | None = None,
    include_header: bool = False,
):
    """
    Kirim notifikasi WA secara asynchronous ke tabel wa_outbox.
    """
    t = threading.Thread(
        target=_send_wa_notif_worker,
        args=(message, event_type, target_jid, media_url, include_header),
        daemon=True
    )
    t.start()

def generate_and_upload_mrcv_screenshot(symbol: str, state) -> str:
    """Generates screenshot menggunakan TF M5 dan mengunggah ke Supabase Storage."""
    try:
        tf_label = os.getenv("MRCV_TIMEFRAME", "M5")
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
            entry_time=None,
            entry_price=op_price,
            exit_time=datetime.now(),
            exit_price=tp_price,
            trigger_time=None,
            tf_label=tf_label,
            output_dir="temp_screenshots",
            num_candles=50
        )
        
        if img_path and os.path.exists(img_path):
            folder_date = datetime.now().strftime("%Y-%m-%d")
            timestamp = int(time.time())
            filename = f"MRCV_{mode}_{symbol}_{tf_label}_{ticket}_{timestamp}.png"
            new_path = os.path.join("temp_screenshots", filename)
            
            if os.path.exists(new_path):
                os.remove(new_path)
            os.rename(img_path, new_path)
            
            success, public_url = upload_screenshot(new_path, "engulfing", folder_date, filename)
            if os.path.exists(new_path):
                os.remove(new_path)
                
            if success:
                return public_url
    except Exception as e:
        print(cprint(f"⚠️ Gagal generate/upload screenshot MRCV: {e}", Colors.RED))
        
    return ""
