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

def send_rcs_wa_notif(
    config: RCSConfig,
    message: str,
    event_type: str,
    target_jid: str | None = None,
    media_url: str | None = None,
    include_header: bool = True,
):
    """
    Fungsi helper untuk kirim pesan ke Supabase WA Outbox dengan routing JID.

    include_header=True  → prepend HEADER_TEXT (untuk grup skip/result)
    include_header=False → tanpa header (untuk PRIVATE_JID / grup OP Signal)
    """
    dest_jid = target_jid if target_jid else config.group_jid
    if not dest_jid:
        return

    supabase = get_supabase()
    if supabase is None:
        return

    full_message = (HEADER_TEXT + message) if include_header else message
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

def generate_and_upload_rcs_screenshot(symbol: str, state, config: RCSConfig) -> str:
    """Generates screenshot menggunakan Timeframe dinamis RCS_SIGNAL_TIMEFRAME dan mengunggah ke Supabase Storage."""
    try:
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
            entry_time=None,
            trigger_time=state.trigger_timestamp or int(time.time()),
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

def notify_trigger(symbol: str, pattern: str, direction: str, state, config: RCSConfig, candle_data: dict | None = None):
    if not config.notif_trigger: return

    metrics_str = ""
    if candle_data:
        point = candle_data.get("point", 0.00001)
        c_open = candle_data.get("open_", 0.0)
        c_close = candle_data.get("close_", 0.0)
        c_high = candle_data.get("high_", 0.0)
        c_low = candle_data.get("low_", 0.0)
        spread = int(candle_data.get("spread", 0))
        body_pct = candle_data.get("body_pct", 0.0)
        ema = candle_data.get("ema_now", 0.0)

        if point > 0:
            risk_range_pts = int(round((c_close - c_low) / point)) if direction == "BUY" else int(round((c_high - c_close) / point))
            dist_open_ema = int(round(abs(c_open - ema) / point))
        else:
            risk_range_pts = 0
            dist_open_ema = 0

        metrics_str = (
            f"📊 ALASAN SIGNAL VALID:\n"
            f"* Jarak Open C1 - EMA 20: {dist_open_ema} pts (Syarat: {config.min_ema_distance_pts}-{config.max_ema_distance_pts} pts)\n"
            f"* Risk Range C1: {risk_range_pts} pts (Syarat: {config.min_trigger_range}-{config.max_trigger_range} pts)\n"
            f"* Body Candle C1: {body_pct:.1f}% (Syarat: {config.min_body_percent}-{config.max_body_percent}%)\n"
            f"* Spread Market: {spread} pts (Syarat: <= {config.max_spread_points} pts)\n\n"
        )

    # Label OP1 sesuai mode entry
    op1_mode_label = "Market" if config.op1_entry_mode == "INSTANT_ZERO" else f"Limit ({config.op1_entry_mode})"

    msg = (
        f"🌟 SIGNAL RCS [{direction}] 🌟\n"
        f"🎯 RCS TRIGGER VALID\n\n"
        f"Symbol: {symbol}\n"
        f"Pattern: {pattern}\n"
        f"Arah: {direction}\n\n"
        f"{metrics_str}"
        f"📍 LEVEL EKSEKUSI & TARGET:\n"
        f"* OP1 {op1_mode_label} : {state.op1_level:.5f} | TP1: {state.tp1_price:.5f}\n"
        f"* OP2 Limit  : {state.op2_level:.5f} | TP2: {state.tp2_price:.5f}\n"
        f"* OP3 SL/Hdg : {state.op3_level:.5f} | Mode: {config.op3_mode}"
    )
    # Target: PRIVATE_JID — tanpa header (format bersih)
    send_rcs_wa_notif(config, msg, 'RCS_TRIGGER', target_jid=config.private_jid, include_header=False)

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

def notify_open(
    symbol: str,
    phase_name: str,
    ticket: int,
    price: float,
    target: float,
    config: RCSConfig,
    direction: str = "",
    is_op1: bool = False,
):
    """
    Kirim notifikasi order terbuka ke PRIVATE_JID.

    is_op1=True  → format premium (🌟) tanpa header, hanya untuk OP1 mode Limit/Percent
    is_op1=False → format standar (✅) tanpa header, untuk OP2 / OP3
    """
    if not config.notif_open:
        return

    if is_op1 and direction:
        # Format khusus OP1 Limit — bersih, tidak ada header
        msg = (
            f"🌟  RCS OP1 TERBUKA [{direction}] 🌟\n\n"
            f"Symbol: {symbol}\n"
            f"Ticket: {ticket}\n"
            f"Harga: {price:.5f}\n"
            f"Target TP: {target:.5f}"
        )
    else:
        # Format standar OP2 / OP3
        msg = (
            f"✅ *RCS {phase_name} TERBUKA*\n\n"
            f"Symbol: {symbol}\n"
            f"Ticket: {ticket}\n"
            f"Harga: {price:.5f}\n"
            f"Target TP: {target:.5f}"
        )

    # Target: PRIVATE_JID — selalu tanpa header
    send_rcs_wa_notif(config, msg, 'RCS_OPEN', target_jid=config.private_jid, include_header=False)

    # Target: PRIVATE_JID — tanpa header
    send_rcs_wa_notif(config, msg, 'RCS_FREEZE', target_jid=config.private_jid, include_header=False)

def notify_startup_hanging_positions(symbol: str, snapshot, config: RCSConfig):
    """
    Kirim notifikasi saat bot startup jika mendeteksi posisi aktif tertinggal di broker.
    Target: RCS_GROUP_JID (GRUP COPET SKIPPED) & PRIVATE_JID
    """
    rcs_skip_jid = config.group_jid or os.getenv("RCS_GROUP_JID") or "120363409493021715@g.us"
    private_jid = config.private_jid or os.getenv("PRIVATE_JID")

    all_positions = snapshot.system_positions + snapshot.manual_positions
    pos_lines = []
    for p in all_positions:
        origin_label = "MANUAL" if (hasattr(p.origin, 'value') and p.origin.value == "MANUAL") else f"SYSTEM ({p.strategy})"
        pos_lines.append(
            f"• Tkt #{p.ticket} | {p.direction} {p.volume} lot @ {p.open_price:.5f} | PnL: ${p.net_profit:.2f} [{origin_label}]"
        )
    pos_str = "\n".join(pos_lines)

    msg = (
        f"⚠️ *DETEKSI POSISI TERGANTUNG SAAT STARTUP* [{symbol}]\n\n"
        f"Sistem mendeteksi *{snapshot.total_count} posisi aktif* tertinggal di broker MT5:\n"
        f"• Posisi Manual: {snapshot.manual_count} posisi\n"
        f"• Posisi Sistem: {snapshot.system_count} posisi\n"
        f"• Total Floating PnL: *${snapshot.total_floating:.2f}*\n\n"
        f"📍 RINCIAN POSISI TERTINGGAL:\n"
        f"{pos_str}\n\n"
        f"🛑 *STATUS SIKLUS:* DIBLOKIR (PAUSED)\n"
        f"Sistem TIDAK akan membuka siklus baru pada {symbol} sampai semua posisi di atas ditutup."
    )

    if rcs_skip_jid:
        send_rcs_wa_notif(config, msg, 'RCS_STARTUP_HANGING', target_jid=rcs_skip_jid, include_header=True)
    if private_jid and private_jid != rcs_skip_jid:
        send_rcs_wa_notif(config, msg, 'RCS_STARTUP_HANGING', target_jid=private_jid, include_header=True)

def notify_result(symbol: str, event_desc: str, profit: float, recovery: float, config: RCSConfig, state=None):
    if not config.notif_result: return
    
    # 1. Generate & Upload Screenshot if state is provided
    media_url = ""
    if state is not None:
        media_url = generate_and_upload_rcs_screenshot(symbol, state, config)

    # 2. Header dinamis berdasarkan profit/loss
    if profit > 0:
        header = "🎉 [PROFIT (TUYUL COPET | RCS)]"
    elif profit < 0:
        header = "☠️ [LOSS (TUYUL COPET | RCS)]"
    else:
        header = "📊 [RESULT (TUYUL COPET | RCS)]"

    # 3. Hitung akumulasi total OP yang ditutup dalam siklus (Sistem + Manual)
    total_op_closed = 0
    if state is not None:
        if state.op1_ticket: total_op_closed += 1
        if state.op2_ticket: total_op_closed += 1
        if state.op3_ticket: total_op_closed += 1
        try:
            from mt5_client.position_tracker import PositionTracker
            manual_summary = PositionTracker().get_closed_manual_summary(symbol, since=state.freeze_start_time)
            total_op_closed += manual_summary.total_count
        except Exception:
            pass

    # 4. Blok trigger metrics dari state (jika tersedia)
    metrics_str = ""
    if state is not None and hasattr(state, 'trigger_risk_range_pts'):
        metrics_str = (
            f"Info :\n"
            f"* Jarak Open C1 - EMA 20: {state.trigger_dist_ema_pts} pts "
            f"(Syarat: 0-{config.max_ema_distance_pts} pts)\n"
            f"* Risk Range C1: {state.trigger_risk_range_pts} pts "
            f"(Syarat: {config.min_trigger_range}-{config.max_trigger_range} pts)\n"
            f"* Body Candle C1: {state.trigger_body_pct:.1f}% "
            f"(Syarat: {config.min_body_percent}-{config.max_body_percent}%)\n"
            f"* Spread Market: {state.trigger_spread_pts} pts "
            f"(Syarat: <= {config.max_spread_points} pts)\n\n"
        )

    # 5. Body pesan
    op_count_str = f"Total OP Ditutup: *{total_op_closed} posisi*\n" if total_op_closed > 0 else ""
    msg = (
        f"{header}\n"
        f"📊 RCS RESULT\n"
        f"{metrics_str}"
        f"Symbol: {symbol}\n"
        f"{op_count_str}"
        f"Info: {event_desc}\n"
        f"Closed Net PnL: *${profit:.2f}*\n"
    )
    if recovery != 0.0:
        msg += f"Hasil Recovery: *${recovery:.2f}*"
        
    # 6. Kirim ke grup profit atau loss — tanpa HEADER_TEXT karena sudah ada di body
    target_group = config.profit_signal_jid if profit > 0 else config.loss_signal_jid
    
    send_rcs_wa_notif(
        config, msg, 'RCS_RESULT',
        target_jid=target_group,
        media_url=media_url if media_url else None,
        include_header=False,
    )

def notify_system_status(status: str, configs: dict[str, RCSConfig], extra_info: str = ""):
    from strategies.strategy_rcs.rcs_schedule import get_rcs_trading_status_text
    from strategies.strategy_rcs.rcs_daily_guard import get_rcs_daily_guard_status_text

    first_config = list(configs.values())[0] if configs else None
    if not first_config: return

    rcs_skip_jid = first_config.group_jid or os.getenv("RCS_GROUP_JID") or "120363409493021715@g.us"
    private_jid = first_config.private_jid or os.getenv("PRIVATE_JID")
    profit_jid = first_config.profit_signal_jid or os.getenv("PROFIT_SIGNAL")
    loss_jid = first_config.loss_signal_jid or os.getenv("LOSS_SIGNAL")
    info_jid = os.getenv("GROUP_JID")

    standard_jids = set()
    for jid in [private_jid, profit_jid, loss_jid, info_jid]:
        if jid and jid != rcs_skip_jid:
            standard_jids.add(jid)

    try:
        sb = get_supabase()
        outbox_rows = []

        if status == 'START':
            std_msg = (
                f"🟢 SISTEM DIAKTIFKAN 🟢\n\n"
                f"🟢 [STRATEGI: REVERSAL CANDLE SYSTEM (TUYUL COPET | RCS)]"
            )
            
            skipped_msg_lines = [
                f"🟢 SISTEM DIAKTIFKAN 🟢\n\n",
                f"🟢 [STRATEGI: REVERSAL CANDLE SYSTEM (TUYUL COPET | RCS)]\n\n"
            ]
            
            for symbol, config in configs.items():
                op1_info = config.op1_entry_mode
                if config.op1_entry_mode == "PERCENT":
                    op1_info += f" ({config.entry_percent}%)"
                    
                skipped_msg_lines.append(f"⚙️ INFO CONFIG RCS [{symbol}]:")
                skipped_msg_lines.append(f"• Signal TF: {config.signal_timeframe}")
                skipped_msg_lines.append(f"• Schedule: {get_rcs_trading_status_text(config)}")
                skipped_msg_lines.append(f"• Daily Guard: {get_rcs_daily_guard_status_text(config)}")
                skipped_msg_lines.append(f"• OP1 Setup: {op1_info} ({config.lot_size_op1} Lot | TP: {config.tp_percent}%)")
                skipped_msg_lines.append(f"• OP2 Setup: {config.op2_mode} {config.op2_percent}% ({config.lot_size_op2} Lot | TP: {config.tp2_percent}%)")
                skipped_msg_lines.append(f"• OP3 Setup: {config.op3_mode} {config.op3_percent}% (OP1+OP2 Lot)")
                skipped_msg_lines.append(f"• Filters: Range({config.min_trigger_range}-{config.max_trigger_range}) | Body({config.min_body_percent}-{config.max_body_percent}%) | EMA_Dist({config.min_ema_distance_pts}-{config.max_ema_distance_pts} pts)\n")
                
            skipped_msg = "\n".join(skipped_msg_lines).strip()
            
        else:
            std_msg = (
                f"🛑 SISTEM DIMATIKAN 🛑\n\n"
                f"🛑 [STRATEGI: REVERSAL CANDLE SYSTEM (TUYUL COPET | RCS)]"
            )
            skipped_msg = std_msg

        for jid in standard_jids:
            outbox_rows.append({
                'source_table': 'rcs_system',
                'event_type': 'RCS_SYSTEM',
                'group_jid': jid,
                'message_type': 'TEXT',
                'message': std_msg,
                'dedupe_key': f'rcs_std_{status.lower()}_{jid[:10]}_{int(time.time())}_{uuid.uuid4().hex[:4]}'
            })

        if rcs_skip_jid:
            outbox_rows.append({
                'source_table': 'rcs_system',
                'event_type': 'RCS_SYSTEM',
                'group_jid': rcs_skip_jid,
                'message_type': 'TEXT',
                'message': skipped_msg,
                'dedupe_key': f'rcs_skip_{status.lower()}_{int(time.time())}_{uuid.uuid4().hex[:4]}'
            })

        if outbox_rows:
            sb.table('wa_outbox').insert(outbox_rows).execute()
            print(cprint(f"📲 Broadcast Notifikasi RCS System ({status}) ke {len(outbox_rows)} WA (Gabungan {len(configs)} symbol)", Colors.GREEN))
    except Exception as e:
        print(cprint(f"⚠️ Gagal broadcast WA notif RCS System ({status}): {e}", Colors.RED))


def notify_company_target_reached_rcs(reason: str):
    """
    Broadcast notifikasi Company Daily Target dari sisi RCS (TUYUL COPET).
    Dipanggil hanya SEKALI per hari — dijaga oleh should_send_company_notif().

    Fungsi ini me-reuse logic yang sama dengan engulfing_notifier.notify_company_target_reached,
    namun dipanggil dari rcs_engine.py tanpa cross-import ke app/.
    """
    from app.engulfing_notifier import notify_company_target_reached
    notify_company_target_reached(reason)
