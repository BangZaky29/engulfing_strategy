# =====================================================
# mt5_client/execution/order_params.py
# Modul untuk menghitung parameter order (SL, TP, Price).
# =====================================================

import MetaTrader5 as mt5
from config.execution_config import ExecutionConfig

def _resolve_order_params(
    action_str: str,
    pattern: str,
    op_price_payload: float | None,
    ask: float,
    bid: float,
    signal: dict,
    exec_cfg: ExecutionConfig,
    symbol_info,
    curr_close: float,
    curr_low: float,
    curr_high: float,
    lot_size_used: float,
) -> tuple:
    """Helper untuk menghitung parameter order generik (BUY/SELL)."""
    # 1. Tentukan OP Price & Type
    if action_str == "BUY":
        if op_price_payload is None or op_price_payload >= ask:
            order_type = mt5.ORDER_TYPE_BUY
            action     = mt5.TRADE_ACTION_DEAL
            price      = ask
            comment    = "SIGNAL_BUY"
        else:
            order_type = mt5.ORDER_TYPE_BUY_LIMIT
            action     = mt5.TRADE_ACTION_PENDING
            price      = op_price_payload
            comment    = "SIGNAL_BUY_LIMIT"
    else:
        if op_price_payload is None or op_price_payload <= bid:
            order_type = mt5.ORDER_TYPE_SELL
            action     = mt5.TRADE_ACTION_DEAL
            price      = bid
            comment    = "Engulf_SELL" if pattern == "bearish_engulfing" else "SIGNAL_SELL"
        else:
            order_type = mt5.ORDER_TYPE_SELL_LIMIT
            action     = mt5.TRADE_ACTION_PENDING
            price      = op_price_payload
            comment    = "Engulf_SELL_LIMIT" if pattern == "bearish_engulfing" else "SIGNAL_SELL_LIMIT"

    # 2. Hitung SL Logic (Ring H1)
    if signal.get("tfm_status") in ("STRONG", "VALID") and "h1_trigger_close" in signal:
        h1_close = float(signal["h1_trigger_close"])
        h1_low = float(signal.get("h1_trigger_low", h1_close))
        h1_high = float(signal.get("h1_trigger_high", h1_close))
        sl_price = exec_cfg.calculate_sl_price(
            current_close=h1_close,
            current_low=h1_low,
            current_high=h1_high,
            action_str=action_str,
        )
        print(f"   [SL] Menggunakan SL Ring H1 (exec_cfg): {sl_price:.2f}")
    else:
        # Fallback jika tidak ada H1 Trigger
        sl_price = exec_cfg.calculate_sl_price(
            current_close=curr_close,
            current_low=curr_low,
            current_high=curr_high,
            action_str=action_str,
        )
        print(f"   [SL] Menggunakan SL Fallback M5 (exec_cfg): {sl_price:.2f}")

    # 3. Hitung TP Logic
    if signal.get("tp_price") is not None:
        tp_price = float(signal["tp_price"])
        print(f"   [TP] Menggunakan TP payload dari detector: {tp_price:.2f}")
    elif getattr(exec_cfg, 'tp_mode_b', 'PCT') == "USD":
        tick_value = symbol_info.trade_tick_value
        tick_size  = symbol_info.trade_tick_size
        try:
            tp_price = exec_cfg.calculate_tp_price_usd(
                entry_price=price,
                action_str=action_str,
                lot_size=lot_size_used,
                tick_value=tick_value,
                tick_size=tick_size,
            )
            print(f"   [TP] TP Statis ${exec_cfg.tp_target_usd_b:.2f} USD (lot={lot_size_used}, tick_val={tick_value}, tick_sz={tick_size}): {tp_price:.5f}")
        except Exception as e:
            tp_price = exec_cfg.calculate_tp_price(entry_price=price, sl_price=sl_price, action_str=action_str)
            print(f"   ⚠️ [TP] Gagal hitung TP USD ({e}), fallback ke PCT: {tp_price:.2f}")
    else:
        tp_price = exec_cfg.calculate_tp_price(
            entry_price=price,
            sl_price=sl_price,
            action_str=action_str,
        )
        print(f"   [TP] Menggunakan TP Distance OP-SL (exec_cfg): {tp_price:.2f}")

    return order_type, action, price, sl_price, tp_price, comment, None

def build_order_params(
    action_str: str,
    pattern: str,
    op_price_payload: float | None,
    ask: float,
    bid: float,
    signal: dict,
    exec_cfg: ExecutionConfig,
    symbol_info,
    curr_close: float,
    curr_low: float,
    curr_high: float,
    lot_size_used: float,
) -> tuple:
    """Menghitung dan menyusun parameter order termasuk harga open, SL, TP, tipe order, dan komentar."""
    if action_str not in ("BUY", "SELL"):
        if pattern == "bearish_engulfing":
            action_str = "SELL"
        elif pattern == "bullish_engulfing":
            action_str = "BUY"
        else:
            err_msg = f"Pola tidak dikenali: {pattern}"
            print(f"❌ {err_msg}")
            return None, None, None, None, None, None, err_msg
            
    return _resolve_order_params(
        action_str, pattern, op_price_payload, ask, bid, signal,
        exec_cfg, symbol_info, curr_close, curr_low, curr_high, lot_size_used
    )
