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

HEADER_TEXT = "🟢 [STRATEGI: MARUBOZU CANDLE SYSTEM (RECOVERY SYSTEM | MRCV)]\n\n"

def _send_wa_notif_worker(
    message: str,
    event_type: str,
    target_jid: str | None = None,
    media_url: str | None = None,
    include_header: bool = True,
):
    mrcv_group = os.getenv("MRCV_GROUP_JID", "120363430592783067@g.us")
    dest_jid = target_jid if target_jid else mrcv_group
    if not dest_jid:
        return

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
    include_header: bool = True,
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

def notify_mrcv_trigger(
    symbol: str,
    tf_label: str,
    direction: str,
    c_high: float,
    c_low: float,
    ring_pts: float,
    pips: float,
    time_str: str,
    state,
    lot_op1: float,
    lot_op2: float,
    lot_op3: float,
    op3_direction: str
):
    """
    Kirim notifikasi trigger sinyal awal ke GROUP OP SIGNAL (PRIVATE_JID).
    """
    msg = (
        f"🌟 SIGNAL MRCV [{direction}] 🌟\n"
        f"Symbol: {symbol} ({tf_label})\n\n"
        f"📊 *Detail Candle Trigger C1:*\n"
        f"• High: {c_high:.5f} | Low: {c_low:.5f}\n"
        f"• Range C1: {ring_pts:.1f} pts ({pips:.1f} pips)\n"
        f"• Waktu Candle:  {time_str}\n\n"
        f"📍 *Rincian Level Order:*\n"
        f"🟢 OP1 {direction} (Market) : {state.op1_level:.5f} | TP1: {state.tp1_price:.5f} (Lot: {lot_op1})\n"
        f"📉 OP2 {direction} LIMIT    : {state.op2_level:.5f} | TP2: {state.tp2_price:.5f} (Lot: {lot_op2})\n"
        f"❄️ OP3 {op3_direction} STOP (Hedge) : {state.op3_level:.5f} (Lot: {lot_op3})"
    )
    target_jid = os.getenv("PRIVATE_JID", "120363406387314492@g.us")
    send_mrcv_wa_notif(msg, "MRCV_TRIGGER", target_jid=target_jid, include_header=False)

def notify_mrcv_skip(
    symbol: str,
    tf_label: str,
    direction: str,
    c_high: float,
    c_low: float,
    ring_pts: float,
    pips: float,
    time_str: str,
    min_pts: float,
    max_pts: float,
    reason: str = ""
):
    """
    Kirim notifikasi trigger yang di-skip ke RCS_GROUP_JID.
    """
    notif_skip = os.getenv("MRCV_NOTIF_SKIP", "true").lower() == "true"
    if not notif_skip:
        return

    reason_text = reason if reason else f"Ukuran Ring C1 ({ring_pts:.1f} pts) di luar batas filter ({min_pts:.1f} - {max_pts:.1f} pts)."

    msg = (
        f"⏭️ *[MRCV TRIGGER SKIPPED]*\n"
        f"Symbol: {symbol} ({tf_label})\n"
        f"Arah: *{direction}*\n"
        f"Pola: Marubozu\n\n"
        f"📊 *Detail Candle Trigger C1:*\n"
        f"• High: {c_high:.5f} | Low: {c_low:.5f}\n"
        f"• Range Ring C1: {ring_pts:.1f} pts ({pips:.1f} pips)\n"
        f"• Waktu Candle:  {time_str}\n\n"
        f"⚠️ *Alasan Skip:*\n"
        f"{reason_text}"
    )
    target_jid = os.getenv("MRCV_GROUP_JID", "120363430592783067@g.us")
    send_mrcv_wa_notif(msg, "MRCV_SKIP", target_jid=target_jid, include_header=False)

def notify_mrcv_op2_filled(symbol: str, direction: str, ticket: int, price: float, tp_price: float, volume: float):
    """
    Kirim notifikasi OP2 Limit terbuka/aktif ke GROUP OP SIGNAL (PRIVATE_JID).
    """
    msg = (
        f"📉 *[MRCV OP2 LIMIT TERBUKA]*\n"
        f"Symbol: {symbol}\n"
        f"Arah: {direction} LIMIT (Aktif)\n"
        f"Ticket: #{ticket}\n"
        f"Harga Open: {price:.5f}\n"
        f"Target TP2: {tp_price:.5f}\n"
        f"Volume: {volume} Lot"
    )
    target_jid = os.getenv("PRIVATE_JID", "120363406387314492@g.us")
    send_mrcv_wa_notif(msg, "MRCV_OP2_FILLED", target_jid=target_jid, include_header=False)

def notify_mrcv_op3_freeze(symbol: str, op3_direction: str, ticket: int, price: float, volume: float, floating_freeze: float):
    """
    Kirim notifikasi OP3 Stop (Hedge) aktif / Freeze ke GROUP OP SIGNAL (PRIVATE_JID).
    """
    msg = (
        f"❄️ *[MRCV PHASE FREEZE - HEDGE AKTIF]*\n"
        f"Symbol: {symbol}\n"
        f"OP3 Stop tersentuh! Posisi kini terkunci (Hedge).\n\n"
        f"Ticket OP3: #{ticket}\n"
        f"Arah: {op3_direction} (Hedge) @ {price:.5f} ({volume} Lot)\n"
        f"Snapshot Floating Freeze: ${floating_freeze:.2f}\n"
        f"Status: Posisi terkunci, mencari trigger pemulihan berikutnya..."
    )
    target_jid = os.getenv("PRIVATE_JID", "120363406387314492@g.us")
    send_mrcv_wa_notif(msg, "MRCV_FREEZE", target_jid=target_jid, include_header=False)

def notify_mrcv_cycle_done(
    symbol: str,
    cycle_profit: float,
    cumulative_profit: float,
    rcs_floating: float,
    is_wait_rcs: bool,
    screenshot_url: str = ""
):
    """
    Kirim notifikasi siklus selesai + screenshot ke grup PROFIT/LOSS.
    """
    profit_jid = os.getenv("PROFIT_SIGNAL") if cycle_profit >= 0 else os.getenv("LOSS_SIGNAL")
    if not profit_jid:
        return

    if not is_wait_rcs:
        # Mode Mandiri (MRCV_WAIT_FOR_RCS_HEDGE=false)
        msg = (
            f"Putaran Marubozu sukses tertutup.\n"
            f"Profit putaran ini: ${cycle_profit:+.2f}\n\n"
            f"📊 *Status Performa MRCV:*\n"
            f"Total Kumulatif Profit: ${cumulative_profit:+.2f}"
        )
    else:
        # Mode Recovery RCS (MRCV_WAIT_FOR_RCS_HEDGE=true)
        msg = (
            f"Putaran recovery Marubozu sukses tertutup.\n"
            f"Profit putaran ini: ${cycle_profit:+.2f}\n\n"
            f"📊 *Status Recovery:*\n"
            f"Total Kumulatif MRCV: ${cumulative_profit:+.2f}\n"
            f"Floating RCS saat ini: ${rcs_floating:.2f}\n"
            f"⏳ *Mesin akan terus mencari trigger sampai kumulatif profit melebihi floating RCS.*"
        )

    send_mrcv_wa_notif(
        msg,
        "MRCV_CYCLE_DONE",
        target_jid=profit_jid,
        media_url=screenshot_url if screenshot_url else None,
        include_header=True
    )

def notify_mrcv_hanging_positions(symbol: str, positions: list):
    """
    Kirim notifikasi deteksi posisi aktif / manual menggantung ke RCS_GROUP_JID.
    """
    pos_lines = []
    total_floating = 0.0
    for p in positions:
        total_floating += p.profit
        dir_str = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
        pos_lines.append(
            f"• #{p.ticket} | {dir_str} {p.volume} lot @ {p.price_open:.5f} | PnL: ${p.profit:+.2f}"
        )
    pos_str = "\n".join(pos_lines)

    msg = (
        f"⚠️ *[MRCV DETEKSI POSISI AKTIF/MANUAL]*\n"
        f"Symbol: {symbol}\n"
        f"Sistem mendeteksi {len(positions)} posisi aktif pada broker MT5:\n"
        f"{pos_str}\n\n"
        f"📊 Total Floating: ${total_floating:+.2f}\n"
        f"🛑 *STATUS SIKLUS:* DIJEDA (PAUSED)\n"
        f"Mesin Marubozu TIDAK akan membuka OP baru sampai posisi di atas ditutup manual oleh trader."
    )
    target_jid = os.getenv("MRCV_GROUP_JID", "120363430592783067@g.us")
    send_mrcv_wa_notif(msg, "MRCV_HANGING_PAUSED", target_jid=target_jid, include_header=False)

def notify_mrcv_positions_cleared(symbol: str):
    """
    Kirim notifikasi saat semua posisi pada broker MT5 telah bersih.
    """
    msg = (
        f"✅ *[MRCV POSISI BERSIH - SIKLUS AKTIF]*\n"
        f"Symbol: {symbol}\n"
        f"Seluruh posisi pada {symbol} telah bersih (0 posisi).\n"
        f"🚀 *STATUS:* Mesin Marubozu kembali AKTIF mencari trigger normal."
    )
    target_jid = os.getenv("MRCV_GROUP_JID", "120363430592783067@g.us")
    send_mrcv_wa_notif(msg, "MRCV_POSITIONS_CLEARED", target_jid=target_jid, include_header=False)

def notify_mrcv_max_loss_close_all(
    symbol: str,
    total_net: float,
    max_loss: float,
    mrcv_floating: float,
    rcs_floating: float,
    cumulative_profit: float
):
    """
    Kirim notifikasi emergency cutloss close all ke MRCV_GROUP_JID dan LOSS_SIGNAL.
    """
    msg = (
        f"🛑 *[MRCV EMERGENCY CLOSE ALL - MAX LOSS]*\n"
        f"Symbol: {symbol}\n"
        f"Batas toleransi kerugian maksimal sistem telah tercapai!\n\n"
        f"📊 *Rincian Keuangan Realtime:*\n"
        f"• Total Net PnL: *${total_net:+.2f}*\n"
        f"• Batas Maksimal Loss: ${max_loss:.2f}\n"
        f"• Floating MRCV: ${mrcv_floating:+.2f}\n"
        f"• Floating RCS: ${rcs_floating:+.2f}\n"
        f"• Kumulatif Profit MRCV: ${cumulative_profit:+.2f}\n\n"
        f"🧹 Seluruh posisi aktif (RCS & MRCV) telah ditutup darurat (Sapu Bersih) untuk melindungi ekuitas modal.\n"
        f"🟢 Sistem di-reset dan kembali siaga normal."
    )
    target_jid = os.getenv("MRCV_GROUP_JID", "120363430592783067@g.us")
    send_mrcv_wa_notif(msg, "MRCV_MAX_LOSS_CLOSE_ALL", target_jid=target_jid, include_header=False)
    loss_jid = os.getenv("LOSS_SIGNAL")
    if loss_jid:
        send_mrcv_wa_notif(msg, "MRCV_MAX_LOSS_CLOSE_ALL", target_jid=loss_jid, include_header=False)
