# -*- coding: utf-8 -*-
# =====================================================
# mt5_client/execution.py
# Modul untuk eksekusi order Market, Stop Loss, dan Take Profit
# =====================================================

import os
import time

try:
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover
    mt5 = None  # type: ignore

from config.mt5_config import MT5Config, EMAConfig
from config.execution_config import ExecutionConfig
from mt5_client.trade_monitor import add_tracked_trade, load_tracked_trades, save_tracked_trades


from mt5_client.error_helper import get_last_error



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
    positions = mt5.positions_get(symbol=symbol)  # type: ignore
    if positions is None:
        err_msg = f"Gagal cek posisi: {get_last_error()}"
        print(f"❌ Eksekusi dibatalkan: {err_msg} untuk {symbol}")  # type: ignore
        return None, err_msg
    elif len(positions) > 0:
        active_info = []
        for pos in positions:
            pos_type = "BUY" if getattr(pos, "type", None) == mt5.POSITION_TYPE_BUY else "SELL"
            pos_ticket = getattr(pos, "ticket", None)
            pos_price = getattr(pos, "price_open", None) or getattr(pos, "price_current", None) or getattr(pos, "price", None)
            pos_vol = getattr(pos, "volume", None)
            pair = f"#{pos_ticket} {pos_type} @ {pos_price:.2f}" if pos_price is not None else f"#{pos_ticket} {pos_type}"
            if pos_vol is not None:
                pair += f" ({pos_vol:.2f})"
            active_info.append(pair)

        active_summary = ", ".join(active_info)
        err_msg = f"Ada posisi aktif ({len(positions)}): {active_summary}"
        print(f"⚠️ Eksekusi di-skip: {err_msg} untuk {symbol}. Menunggu OP sebelumnya close (kena TP/SL).")
        return None, err_msg

    # 0.5. Cek apakah ada PENDING ORDER yang menggantung, jika ada BATALKAN!
    orders = mt5.orders_get(symbol=symbol)  # type: ignore
    if orders is not None and len(orders) > 0:
        for old_order in orders:
            cancel_req = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": old_order.ticket
            }
            res = mt5.order_send(cancel_req)  # type: ignore
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"🧹 PENDING ORDER LAMA ({old_order.ticket}) DIBATALKAN karena ada trigger baru!")
                
                # Kirim log pembatalan ke Supabase agar WA bot men-trigger notifikasi
                try:
                    from database.supabase_client import get_supabase
                    supabase = get_supabase()
                    data_tracker = load_tracked_trades()
                    old_info = data_tracker.get(str(old_order.ticket), {})
                    log_data = {
                        "ticket_id": old_order.ticket,
                        "symbol": symbol,
                        "mode": old_info.get("mode", "BUY"),
                        "message": f"🧹 PENDING ORDER OVERRIDDEN! Dibatalkan karena ada trigger baru (sinyal ke-2) yang aktif.",
                        "op_price": old_info.get("op_price"),
                        "sl_price": old_info.get("sl_price"),
                        "tp_price": old_info.get("tp_price"),
                        "trading_session": old_info.get("trading_session", "Unknown")
                    }
                    supabase.table("trade_active_logs").insert(log_data).execute()
                    
                    # Hapus dari tracker agar tidak dicek oleh trade_monitor
                    if str(old_order.ticket) in data_tracker:
                        del data_tracker[str(old_order.ticket)]
                        save_tracked_trades(data_tracker)
                except Exception as ex:
                    print(f"⚠️ Gagal memproses log override ke Supabase: {ex}")
            else:
                print(f"⚠️ Gagal membatalkan pending order lama ({old_order.ticket}): {get_last_error()}")

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

    action = mt5.TRADE_ACTION_DEAL
    lot_size_used = exec_cfg.get_lot_size(symbol)


    # 2. Setup Parameter Order
    if action_str == "BUY":
        # --- OP Type & Price ---
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

        # --- SL Logic (Ring H1) ---
        if signal.get("tfm_status") in ("STRONG", "VALID") and "h1_trigger_close" in signal:
            h1_close = float(signal["h1_trigger_close"])
            h1_low = float(signal.get("h1_trigger_low", h1_close))
            h1_high = float(signal.get("h1_trigger_high", h1_close))
            # BUY: 0% close | 100% low
            sl_price = exec_cfg.calculate_sl_price(
                current_close=h1_close,
                current_low=h1_low,
                current_high=h1_high,
                action_str="BUY",
            )
            print(f"   [SL] Menggunakan SL Ring H1 (exec_cfg): {sl_price:.2f}")
        else:
            # Fallback jika tidak ada H1 Trigger
            sl_price = exec_cfg.calculate_sl_price(
                current_close=curr_close,
                current_low=curr_low,
                current_high=curr_high,
                action_str="BUY",
            )
            print(f"   [SL] Menggunakan SL Fallback M5 (exec_cfg): {sl_price:.2f}")

        # --- TP Logic (Jarak OP ke SL) ---
        tp_price = exec_cfg.calculate_tp_price(
            entry_price=price,
            sl_price=sl_price,
            action_str="BUY",
        )
        print(f"   [TP] Menggunakan TP Distance OP-SL (exec_cfg): {tp_price:.2f}")




    elif action_str == "SELL":
        # --- OP Type & Price ---
        if op_price_payload is None or op_price_payload <= bid:
            order_type = mt5.ORDER_TYPE_SELL
            action     = mt5.TRADE_ACTION_DEAL
            price      = bid
            comment    = "SIGNAL_SELL"
        else:
            order_type = mt5.ORDER_TYPE_SELL_LIMIT
            action     = mt5.TRADE_ACTION_PENDING
            price      = op_price_payload
            comment    = "SIGNAL_SELL_LIMIT"

        # --- SL Logic (Ring H1) ---
        if signal.get("tfm_status") in ("STRONG", "VALID") and "h1_trigger_close" in signal:
            h1_close = float(signal["h1_trigger_close"])
            h1_low = float(signal.get("h1_trigger_low", h1_close))
            h1_high = float(signal.get("h1_trigger_high", h1_close))
            # SELL: 0% close | 100% high
            sl_price = exec_cfg.calculate_sl_price(
                current_close=h1_close,
                current_low=h1_low,
                current_high=h1_high,
                action_str="SELL",
            )
            print(f"   [SL] Menggunakan SL Ring H1 (exec_cfg): {sl_price:.2f}")
        else:
            # Fallback jika tidak ada H1 Trigger
            sl_price = exec_cfg.calculate_sl_price(
                current_close=curr_close,
                current_low=curr_low,
                current_high=curr_high,
                action_str="SELL",
            )
            print(f"   [SL] Menggunakan SL Fallback M5 (exec_cfg): {sl_price:.2f}")

        # --- TP Logic (Jarak OP ke SL) ---
        tp_price = exec_cfg.calculate_tp_price(
            entry_price=price,
            sl_price=sl_price,
            action_str="SELL",
        )
        print(f"   [TP] Menggunakan TP Distance OP-SL (exec_cfg): {tp_price:.2f}")


    elif pattern == "bearish_engulfing":
        # Catatan: perubahan ini hanya untuk SL/TP versi tail & distance.
        # Pattern bearish_engulfing juga menggunakan logika yang sama dengan SELL.
        # --- OP Type & Price ---

        if op_price_payload is None or op_price_payload <= bid:
            order_type = mt5.ORDER_TYPE_SELL
            action     = mt5.TRADE_ACTION_DEAL
            price      = bid
            comment    = "Engulf_SELL"
        else:
            order_type = mt5.ORDER_TYPE_SELL_LIMIT
            action     = mt5.TRADE_ACTION_PENDING
            price      = op_price_payload
            comment    = "Engulf_SELL_LIMIT"

        # --- SL Logic (Ring H1) ---
        if signal.get("tfm_status") in ("STRONG", "VALID") and "h1_trigger_close" in signal:
            h1_close = float(signal["h1_trigger_close"])
            h1_low = float(signal.get("h1_trigger_low", h1_close))
            h1_high = float(signal.get("h1_trigger_high", h1_close))
            # SELL: 0% close | 100% high
            sl_price = exec_cfg.calculate_sl_price(
                current_close=h1_close,
                current_low=h1_low,
                current_high=h1_high,
                action_str="SELL",
            )
            print(f"   [SL] Menggunakan SL Ring H1 (exec_cfg): {sl_price:.2f}")
        else:
            # Fallback jika tidak ada H1 Trigger
            sl_price = exec_cfg.calculate_sl_price(
                current_close=curr_close,
                current_low=curr_low,
                current_high=curr_high,
                action_str="SELL",
            )
            print(f"   [SL] Menggunakan SL Fallback M5 (exec_cfg): {sl_price:.2f}")

        # --- TP Logic (Jarak OP ke SL) ---
        tp_price = exec_cfg.calculate_tp_price(
            entry_price=price,
            sl_price=sl_price,
            action_str="SELL",
        )
        print(f"   [TP] Menggunakan TP Distance OP-SL (exec_cfg): {tp_price:.2f}")


    else:
        err_msg = f"Pola tidak dikenali: {pattern}"
        print(f"❌ {err_msg}")
        return None, err_msg

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
        expire_time = int(tick.time) + (exec_cfg.pending_order_expire_candles * tf_seconds)
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
    try:
        add_tracked_trade(
            ticket=result_op1.order,
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

    return result_op1.order, None
