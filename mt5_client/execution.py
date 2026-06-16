# -*- coding: utf-8 -*-
# =====================================================
# mt5_client/execution.py
# Modul untuk eksekusi order Market, Stop Loss, dan Take Profit
# =====================================================

import time
import MetaTrader5 as mt5
from config.mt5_config import MT5Config, EMAConfig
from config.execution_config import ExecutionConfig
from mt5_client.trade_monitor import add_tracked_trade, load_tracked_trades, save_tracked_trades


from mt5_client.error_helper import get_last_error


def execute_engulfing_order(signal: dict, mt5_cfg: MT5Config, exec_cfg: ExecutionConfig, ema_cfg: EMAConfig) -> tuple[int | None, str | None]:
    """
    Eksekusi OP berdasarkan sinyal Engulfing. Returns (ticket_id, skip_reason).

    Metode SL — Ring % (EXECUTION_SL_RING_PCT):
      Bullish (BUY) : ring = Close → Low  (0%=Close, 100%=Low)
                      sl_distance = (Close - Low) * sl_ring_pct%
                      sl_price    = Close - sl_distance   [dekat Low]

      Bearish (SELL): ring = Close → High (0%=Close, 100%=High)
                      sl_distance = (High - Close) * sl_ring_pct%
                      sl_price    = Close + sl_distance   [dekat High]

    Metode TP — RR Ratio dari Entry (EXECUTION_TP_RR_RATIO):
      sl_from_entry = |entry_price - sl_price|
      tp_distance   = sl_from_entry * tp_rr_ratio
      BUY : tp_price = entry + tp_distance
      SELL: tp_price = entry - tp_distance
    """
    symbol = signal["symbol"]

    # 0. Cek apakah sudah ada posisi yang masih terbuka (aktif) untuk symbol ini
    positions = mt5.positions_get(symbol=symbol)  # type: ignore
    if positions is None:
        err_msg = f"Gagal cek posisi: {get_last_error()}"
        print(f"❌ Eksekusi dibatalkan: {err_msg} untuk {symbol}")  # type: ignore
        return None, err_msg
    elif len(positions) > 0:
        err_msg = f"Ada posisi aktif ({len(positions)})"
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
    curr_close = signal["curr_close"]
    curr_low   = signal["curr_low"]
    curr_high  = signal["curr_high"]

    # =====================================================
    # Ambil Dynamic SL & RR dari Payload Sinyal (Jika Ada)
    # Jika tidak ada (versi lama), fallback ke exec_cfg
    # =====================================================
    rr_ratio = signal.get("rr_ratio", exec_cfg.tp_rr_ratio)
    op_price_payload = signal.get("op_price")
    sl_price_payload = signal.get("sl_price")
    tp_price_payload = signal.get("tp_price")
    sl_pct_fallback = exec_cfg.sl_ring_pct / 100.0

    action = mt5.TRADE_ACTION_DEAL

    # 2. Setup Parameter Order
    if pattern == "bullish_engulfing":
        # OP
        if op_price_payload is not None and op_price_payload < ask:
            order_type = mt5.ORDER_TYPE_BUY_LIMIT
            action     = mt5.TRADE_ACTION_PENDING
            price      = op_price_payload
            comment    = "Engulf_BUY_LIMIT"
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price      = ask
            comment    = "Engulf_BUY"

        # SL
        if sl_price_payload is not None:
            sl_price = sl_price_payload
        else:
            ring_range  = curr_close - curr_low
            sl_distance = ring_range * sl_pct_fallback
            sl_price    = curr_close - sl_distance

        # TP
        if tp_price_payload is not None:
            tp_price = tp_price_payload
        else:
            sl_from_entry = abs(price - sl_price)
            tp_price      = price + (sl_from_entry * rr_ratio)


    elif pattern == "bearish_engulfing":
        # OP
        if op_price_payload is not None and op_price_payload > bid:
            order_type = mt5.ORDER_TYPE_SELL_LIMIT
            action     = mt5.TRADE_ACTION_PENDING
            price      = op_price_payload
            comment    = "Engulf_SELL_LIMIT"
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price      = bid
            comment    = "Engulf_SELL"

        # SL
        if sl_price_payload is not None:
            sl_price = sl_price_payload
        else:
            ring_range  = curr_high - curr_close
            sl_distance = ring_range * sl_pct_fallback
            sl_price    = curr_close + sl_distance

        # TP
        if tp_price_payload is not None:
            tp_price = tp_price_payload
        else:
            sl_from_entry = abs(price - sl_price)
            tp_price      = price - (sl_from_entry * rr_ratio)

    else:
        err_msg = f"Pola tidak dikenali: {pattern}"
        print(f"❌ {err_msg}")
        return None, err_msg

    # 3. Request ke MT5
    request = {
        "action":       action,
        "symbol":       symbol,
        "volume":       exec_cfg.lot_size,
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
        request["type_filling"] = mt5.ORDER_FILLING_FOK
    elif action == mt5.TRADE_ACTION_PENDING:
        request["type_time"] = mt5.ORDER_TIME_SPECIFIED
        tf_seconds_map = {
            "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
            "H1": 3600, "H4": 14400, "D1": 86400
        }
        tf_seconds = tf_seconds_map.get(signal["timeframe"], 300)
        expire_time = int(tick.time) + (exec_cfg.pending_order_expire_candles * tf_seconds)
        request["expiration"] = expire_time

    # 4. Log sebelum kirim
    print(f"\n🚀 Mengirim Eksekusi {comment} ...")
    print(f"   Pair      : {symbol}")
    print(f"   Harga OP  : {round(price,    digits)} (Action: {'PENDING' if action == mt5.TRADE_ACTION_PENDING else 'MARKET'})")
    ring_pts = round(abs(curr_high - curr_low) / point)
    sl_from_entry = abs(price - sl_price)
    tp_from_entry = abs(tp_price - price)
    print(f"   Ring      : {ring_pts} pts")
    print(f"   SL        : {round(sl_price, digits)} (jarak dari entry: {round(sl_from_entry, digits)})")
    print(f"   TP        : {round(tp_price, digits)} (jarak dari entry: {round(tp_from_entry, digits)})")
    
    session_str = signal.get("trading_session", "Unknown")
    print(f"   Sesi      : [{session_str}]")

    # 5. Kirim order
    result = mt5.order_send(request)  # type: ignore

    if result is None:
        err_msg = f"order_send me-return None: {get_last_error()}"
        print(f"❌ Eksekusi gagal! {err_msg}")  # type: ignore
        return None, err_msg

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        err_msg = f"Ditolak MT5: {result.comment} (code {result.retcode})"
        print(f"❌ Eksekusi ditolak MT5! {err_msg}")
        return None, err_msg

    print(f"✅ EKSEKUSI SUKSES! Ticket: #{result.order} | Volume: {result.volume}")

    # =====================================================
    # Simpan ke Tracker untuk di-SS setelah closed
    # =====================================================
    try:
        add_tracked_trade(
            ticket=result.order,
            symbol=symbol,
            mode="BUY" if pattern == "bullish_engulfing" else "SELL",
            tf=signal["timeframe"],
            op_price=price,
            sl_price=sl_price,
            tp_price=tp_price,
            status="PENDING" if action == mt5.TRADE_ACTION_PENDING else "ACTIVE",
            trading_session=session_str
        )
        print(f"⏳ Trade masuk tracker. Screenshot akan digenerate saat kena SL/TP.")
    except Exception as e:
        print(f"⚠️ Gagal menambahkan tracker: {e}")

    return result.order, None
