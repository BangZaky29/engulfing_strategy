# =====================================================
# mt5_client/execution/order_sender.py
# Modul untuk mem-build request order, mengirim ke MT5, dan logging.
# =====================================================

import os
import MetaTrader5 as mt5
from config.execution_config import ExecutionConfig
from mt5_client.error_helper import get_last_error

def send_order(
    symbol: str,
    order_type: int,
    action: int,
    price: float,
    sl_price: float,
    tp_price: float,
    comment: str,
    lot_size: float,
    exec_cfg: ExecutionConfig,
    digits: int,
    tick,
    signal: dict,
) -> dict | None:
    """Mengirim request order ke MetaTrader 5 dan mengembalikan hasil eksekusi."""
    request = {
        "action": action,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": round(price, digits),
        "sl": round(sl_price, digits),
        "tp": round(tp_price, digits),
        "deviation": exec_cfg.slippage,
        "magic": exec_cfg.magic_number,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(request)
    return result

def send_main_order(
    symbol: str,
    action: int,
    order_type: int,
    price: float,
    sl_price: float,
    tp_price: float,
    comment: str,
    digits: int,
    point: float,
    tick_time: int,
    signal: dict,
    exec_cfg: ExecutionConfig,
    lot_size_used: float,
    pattern: str,
    curr_low: float,
    curr_high: float,
) -> tuple[int | None, str | None]:
    """
    Build MT5 request dictionary, log ke terminal, lalu send order (OP-1).
    Returns (ticket_id, err_msg)
    """
    # 3. Request OP-1 (Main Order) ke MT5
    # Gunakan SL normal (bukan Hedging)
    request_op1 = {
        "action":       action,
        "symbol":       symbol,
        "volume":       lot_size_used,
        "type":         order_type,
        "price":        round(price,    digits),
        "sl":           round(sl_price, digits),
        "tp":           round(tp_price, digits),
        "deviation":    exec_cfg.slippage,
        "magic":        exec_cfg.magic_number,
        "comment":      comment,
        "type_time":    mt5.ORDER_TIME_GTC,
    }
    
    if action == mt5.TRADE_ACTION_DEAL:
        request_op1["type_filling"] = mt5.ORDER_FILLING_FOK
    elif action == mt5.TRADE_ACTION_PENDING:
        request_op1["type_time"] = mt5.ORDER_TIME_SPECIFIED
        tf_seconds_map = {
            "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
            "H1": 3600, "H4": 14400, "D1": 86400
        }
        tf_seconds = tf_seconds_map.get(signal["timeframe"], 300)
        expire_time = int(tick_time) + (exec_cfg.pending_order_expire_candles * tf_seconds)
        request_op1["expiration"] = expire_time

    # 4. Log clean terminal output
    ring_pts = round(abs(curr_high - curr_low) / point)
    session_str = signal.get("trading_session", "Unknown")
    
    active_filter = os.getenv("ACTIVE_FILTER_STRATEGY", "B")
    print(f"⚠️ [SIGNAL] {symbol} | FILTER {active_filter} | {pattern.upper().replace('_', ' ')} | Sesi: {session_str}")
    print(f"🚀 Eksekusi OP-1: {'MARKET' if action == mt5.TRADE_ACTION_DEAL else 'PENDING (LIMIT)'} di {round(price, digits):.2f} | SL: {round(sl_price, digits):.2f} ({ring_pts} pts) | TP: {round(tp_price, digits):.2f}")

    # 5. Kirim order OP-1
    result_op1 = mt5.order_send(request_op1)  # type: ignore

    if result_op1 is None:
        err_msg = f"order_send OP-1 me-return None: {get_last_error()}"
        print(f"❌ Eksekusi OP-1 gagal! {err_msg}")  # type: ignore
        return None, err_msg

    if result_op1.retcode != mt5.TRADE_RETCODE_DONE:
        err_msg = f"Ditolak MT5 (OP-1): {result_op1.comment} (code {result_op1.retcode})"
        print(f"❌ Eksekusi OP-1 ditolak MT5! {err_msg}")
        return None, err_msg

    print(f"✅ EKSEKUSI OP-1 SUKSES! Ticket: #{result_op1.order} | Volume: {result_op1.volume}")

    # Hedging OP-2 Dihapus Sesuai Permintaan User

    return result_op1.order, None
