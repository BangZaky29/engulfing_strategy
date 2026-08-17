import os
import MetaTrader5 as mt5
from .wa_base_sender import send_mrcv_wa_notif, HEADER_TEXT

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
    from mt5_client.multi_account_dispatcher import get_account_footer_label
    acc_footer = get_account_footer_label("MRCV")

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
        f"{acc_footer}"
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
    from mt5_client.multi_account_dispatcher import get_account_footer_label
    acc_footer = get_account_footer_label("MRCV")

    msg = (
        f"📉 *[MRCV OP2 LIMIT TERBUKA]*\n"
        f"Symbol: {symbol}\n"
        f"Arah: {direction} LIMIT (Aktif)\n"
        f"Ticket: #{ticket}\n"
        f"Harga Open: {price:.5f}\n"
        f"Target TP2: {tp_price:.5f}\n"
        f"Volume: {volume} Lot"
        f"{acc_footer}"
    )
    target_jid = os.getenv("PRIVATE_JID", "120363406387314492@g.us")
    send_mrcv_wa_notif(msg, "MRCV_OP2_FILLED", target_jid=target_jid, include_header=False)

def notify_mrcv_op3_freeze(symbol: str, op3_direction: str, ticket: int, price: float, volume: float, floating_freeze: float):
    """
    Kirim notifikasi OP3 Stop (Hedge) aktif / Freeze ke GROUP OP SIGNAL (PRIVATE_JID).
    """
    from mt5_client.multi_account_dispatcher import get_account_footer_label
    acc_footer = get_account_footer_label("MRCV")

    msg = (
        f"❄️ *[MRCV PHASE FREEZE - HEDGE AKTIF]*\n"
        f"Symbol: {symbol}\n"
        f"OP3 Stop tersentuh! Posisi kini terkunci (Hedge).\n\n"
        f"Ticket OP3: #{ticket}\n"
        f"Arah: {op3_direction} (Hedge) @ {price:.5f} ({volume} Lot)\n"
        f"Snapshot Floating Freeze: ${floating_freeze:.2f}\n"
        f"Status: Posisi terkunci, mencari trigger pemulihan berikutnya..."
        f"{acc_footer}"
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

    header = (
        "🎉 [PROFIT : MARUBOZU CANDLE SYSTEM (RECOVERY SYSTEM | MRCV)]\n\n"
        if cycle_profit >= 0
        else "☠️ [LOSS : MARUBOZU CANDLE SYSTEM (RECOVERY SYSTEM | MRCV)]\n\n"
    )

    if not is_wait_rcs:
        # Mode Mandiri (MRCV_WAIT_FOR_RCS_HEDGE=false)
        msg = (
            f"{header}"
            f"Putaran Marubozu sukses tertutup.\n"
            f"Profit putaran ini: ${cycle_profit:+.2f}\n\n"
            f"📊 *Status Performa MRCV:*\n"
            f"Total Kumulatif Profit: ${cumulative_profit:+.2f}"
        )
    else:
        # Mode Recovery RCS (MRCV_WAIT_FOR_RCS_HEDGE=true)
        msg = (
            f"{header}"
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
        include_header=False
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
