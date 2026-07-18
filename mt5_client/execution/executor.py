# =====================================================
# mt5_client/execution/executor.py
# Orchestrator tipis: execute_engulfing_order.
# Memanggil modul guard, params, sender, tracker.
# =====================================================

import MetaTrader5 as mt5

from config.mt5_config import MT5Config, EMAConfig
from config.execution_config import ExecutionConfig
from mt5_client.trade_monitor import add_tracked_trade

from .position_guard import check_active_positions, cancel_old_pending_orders
from .order_params import build_order_params
from .order_sender import send_main_order

def execute_engulfing_order(signal: dict, mt5_cfg: MT5Config, exec_cfg: ExecutionConfig, ema_cfg: EMAConfig) -> tuple[int | None, str | None]:
    """
    Eksekusi OP berdasarkan sinyal Engulfing. Returns (ticket_id, skip_reason).

    Metode SL — Ring H1 Dynamic (EXECUTION_SL_PCT):
      Bullish (BUY) : SL diletakkan menjauh dari ekor bawah H1 (contoh: 110%)
      Bearish (SELL): SL diletakkan menjauh dari ekor atas H1 (contoh: 110%)

    Metode TP — Distance dari OP ke SL (EXECUTION_TP_PCT):
      TP Distance   = | OP - SL | * (tp_pct / 100)
      BUY : tp_price = OP + TP Distance
      SELL: tp_price = OP - TP Distance
    """
    symbol = signal["symbol"]

    if mt5 is None:
        err_msg = "MetaTrader5 module is not loaded (mt5 is None)."
        print(f"❌ Eksekusi dibatalkan: {err_msg}")
        return None, err_msg

    # 0. Cek apakah sudah ada posisi yang masih terbuka (aktif) untuk symbol ini
    is_clear, err_msg = check_active_positions(symbol)
    if not is_clear:
        return None, err_msg

    # 0.5. Cek apakah ada PENDING ORDER yang menggantung, jika ada BATALKAN!
    cancel_old_pending_orders(symbol)

    # 1. Pastikan symbol terpilih
    if not mt5.symbol_select(symbol, True):  # type: ignore
        err_msg = "Gagal select symbol"
        print(f"❌ Eksekusi dibatalkan: {err_msg} {symbol}")
        return None, err_msg

    symbol_info = mt5.symbol_info(symbol)  # type: ignore
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    if symbol_info is None or tick is None:
        err_msg = "Gagal ambil tick data"
        print(f"❌ Eksekusi dibatalkan: {err_msg} {symbol}")
        return None, err_msg

    digits = symbol_info.digits
    point  = symbol_info.point
    ask    = tick.ask
    bid    = tick.bid

    pattern    = signal["pattern_type"]
    action_str = str(signal.get("action_str", "BUY")).upper()
    curr_close = signal["curr_close"]
    curr_low   = signal["curr_low"]
    curr_high  = signal["curr_high"]

    # =====================================================
    # OP Price Payload
    # =====================================================
    op_price_payload = signal.get("op_price")
    
    if not exec_cfg.use_limit_orders:
        op_price_payload = None
        print("⚡ Mode Eksekusi Langsung (Market Execution) Aktif. Limit Order Dibatalkan.")

    lot_size_used = exec_cfg.get_lot_size(symbol)

    # 2. Setup Parameter Order
    order_type, action, price, sl_price, tp_price, comment, err_msg = build_order_params(
        action_str=action_str,
        pattern=pattern,
        op_price_payload=op_price_payload,
        ask=ask,
        bid=bid,
        signal=signal,
        exec_cfg=exec_cfg,
        symbol_info=symbol_info,
        curr_close=curr_close,
        curr_low=curr_low,
        curr_high=curr_high,
        lot_size_used=lot_size_used,
    )
    if err_msg:
        return None, err_msg

    # 3. Request OP-1 (Main Order) ke MT5, 4. Log, 5. Send order
    ticket_id, err_msg = send_main_order(
        symbol=symbol,
        action=action,
        order_type=order_type,
        price=price,
        sl_price=sl_price,
        tp_price=tp_price,
        comment=comment,
        digits=digits,
        point=point,
        tick_time=int(tick.time),
        signal=signal,
        exec_cfg=exec_cfg,
        lot_size_used=lot_size_used,
        pattern=pattern,
        curr_low=curr_low,
        curr_high=curr_high,
    )
    if err_msg or ticket_id is None:
        return None, err_msg

    # =====================================================
    # OP Level Calculation & Triggers
    # =====================================================
    op_level_pts = 0
    op_level_pct = 0.0
    if signal.get("tfm_status") in ("STRONG", "VALID") and "h1_trigger_close" in signal:
        h1_c = float(signal["h1_trigger_close"])
        h1_l = float(signal.get("h1_trigger_low", h1_c))
        h1_h = float(signal.get("h1_trigger_high", h1_c))
        if action_str == "BUY" or (pattern == "bullish_engulfing" and action_str != "SELL"):
            op_level_pts = round((h1_c - price) / point) if point > 0 else 0
            ring_range = h1_c - h1_l
            if ring_range != 0:
                op_level_pct = round(((h1_c - price) / ring_range) * 100, 2)
        else: # SELL
            op_level_pts = round((price - h1_c) / point) if point > 0 else 0
            ring_range = h1_h - h1_c
            if ring_range != 0:
                op_level_pct = round(((price - h1_c) / ring_range) * 100, 2)

    h1_trigger_src = signal.get("h1_trigger_source", "")
    m15_trigger_src = signal.get("m15_trigger_source", "")
    m5_trigger_src = signal.get("m5_trigger_source", "")

    # =====================================================
    # Simpan ke Tracker untuk di-SS setelah closed
    # =====================================================
    session_str = signal.get("trading_session", "Unknown")
    try:
        add_tracked_trade(
            ticket=ticket_id,
            symbol=symbol,
            mode="BUY" if pattern == "bullish_engulfing" else "SELL",
            tf=signal["timeframe"],
            op_price=price,
            sl_price=sl_price, # Disimpan untuk track info saja
            tp_price=tp_price,
            status="PENDING" if action == mt5.TRADE_ACTION_PENDING else "ACTIVE",
            trading_session=session_str,
            hedge_ticket=None,
            h1_trigger_source=h1_trigger_src,
            m15_trigger_source=m15_trigger_src,
            m5_trigger_source=m5_trigger_src,
            op_level_pts=op_level_pts,
            op_level_pct=op_level_pct
        )
        print(f"⏳ Trade OP-1 masuk tracker. Screenshot akan digenerate saat close.")
    except Exception as e:
        print(f"⚠️ Gagal menambahkan tracker: {e}")

    return ticket_id, None
