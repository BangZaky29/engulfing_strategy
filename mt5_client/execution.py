# -*- coding: utf-8 -*-
# =====================================================
# mt5_client/execution.py
# Modul untuk eksekusi order Market, Stop Loss, dan Take Profit
# =====================================================

import MetaTrader5 as mt5
from config.mt5_config import MT5Config, EMAConfig
from config.execution_config import ExecutionConfig
from mt5_client.trade_monitor import add_tracked_trade


def execute_engulfing_order(signal: dict, mt5_cfg: MT5Config, exec_cfg: ExecutionConfig, ema_cfg: EMAConfig) -> bool:
    """
    Eksekusi OP berdasarkan sinyal Engulfing.

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
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        print(f"❌ Eksekusi dibatalkan: Gagal mengambil daftar posisi untuk {symbol}, error: {mt5.last_error()}")
        return False
    elif len(positions) > 0:
        print(f"⚠️ Eksekusi di-skip: Masih ada {len(positions)} posisi terbuka untuk {symbol}. Menunggu OP sebelumnya close (kena TP/SL).")
        return False

    # 1. Pastikan symbol terpilih
    if not mt5.symbol_select(symbol, True):
        print(f"❌ Eksekusi dibatalkan: Gagal select symbol {symbol}")
        return False

    symbol_info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if symbol_info is None or tick is None:
        print(f"❌ Eksekusi dibatalkan: Gagal ambil tick {symbol}")
        return False

    digits = symbol_info.digits
    ask    = tick.ask
    bid    = tick.bid

    pattern    = signal["pattern_type"]
    curr_close = signal["curr_close"]
    curr_low   = signal["curr_low"]
    curr_high  = signal["curr_high"]

    # =====================================================
    # Hitung SL — Metode Ring %
    #
    # sl_ring_pct = % menjauh dari Close ke arah Low/High
    #   Default 80 → SL berada 80% perjalanan dari Close menuju Low/High
    #
    # Contoh BUY (Close=3300, Low=3290, sl_ring_pct=80):
    #   ring_range  = 3300 - 3290 = 10
    #   sl_distance = 10 * 0.80   =  8
    #   sl_price    = 3300 - 8    = 3292  ← dekat Low, masih di dalam ring
    #
    # Contoh SELL (Close=3300, High=3310, sl_ring_pct=80):
    #   ring_range  = 3310 - 3300 = 10
    #   sl_distance = 10 * 0.80   =  8
    #   sl_price    = 3300 + 8    = 3308  ← dekat High, masih di dalam ring
    # =====================================================
    sl_pct = exec_cfg.sl_ring_pct / 100.0   # e.g. 80 → 0.80

    # 2. Setup Parameter Order
    if pattern == "bullish_engulfing":
        order_type  = mt5.ORDER_TYPE_BUY
        price       = ask

        # SL — Ring BUY: Close → Low
        ring_range  = curr_close - curr_low
        sl_distance = ring_range * sl_pct
        sl_price    = curr_close - sl_distance      # SL 80% menjauh dari Close ke Low

        # TP — 1:1 RR dari Entry
        sl_from_entry = abs(price - sl_price)       # jarak entry (ask) ke SL
        tp_price      = price + (sl_from_entry * exec_cfg.tp_rr_ratio)

        comment = "Engulf_BUY"

    elif pattern == "bearish_engulfing":
        order_type  = mt5.ORDER_TYPE_SELL
        price       = bid

        # SL — Ring SELL: Close → High
        ring_range  = curr_high - curr_close
        sl_distance = ring_range * sl_pct
        sl_price    = curr_close + sl_distance      # SL 80% menjauh dari Close ke High

        # TP — 1:1 RR dari Entry
        sl_from_entry = abs(price - sl_price)       # jarak entry (bid) ke SL
        tp_price      = price - (sl_from_entry * exec_cfg.tp_rr_ratio)

        comment = "Engulf_SELL"

    else:
        print(f"❌ Pola tidak dikenali: {pattern}")
        return False

    # 3. Request ke MT5
    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
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
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    # 4. Log sebelum kirim
    print(f"\n🚀 Mengirim Eksekusi {comment} ...")
    print(f"   Pair      : {symbol}")
    print(f"   Harga OP  : {round(price,    digits)}")
    print(f"   Ring      : {round(ring_range, digits)} | SL_PCT={exec_cfg.sl_ring_pct}% | sl_distance={round(sl_distance, digits)}")
    print(f"   SL        : {round(sl_price,  digits)} (jarak dari entry: {round(sl_from_entry, digits)})")
    print(f"   TP        : {round(tp_price,  digits)} (RR {exec_cfg.tp_rr_ratio}:1 | jarak: {round(sl_from_entry * exec_cfg.tp_rr_ratio, digits)})")

    # 5. Kirim order
    result = mt5.order_send(request)

    if result is None:
        print(f"❌ Eksekusi gagal! mt5.order_send() me-return None. Error: {mt5.last_error()}")
        return False

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ Eksekusi ditolak MT5! Retcode: {result.retcode} ({result.comment})")
        return False

    print(f"✅ EKSEKUSI SUKSES! Ticket: #{result.order} | Volume: {result.volume}")

    # =====================================================
    # Simpan ke Tracker untuk di-SS setelah closed
    # =====================================================
    try:
        add_tracked_trade(
            ticket=result.order,
            symbol=symbol,
            mode="BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL",
            tf=signal["timeframe"],
            op_price=price,
            sl_price=sl_price,
            tp_price=tp_price
        )
        print(f"⏳ Trade masuk tracker. Screenshot akan digenerate saat kena SL/TP.")
    except Exception as e:
        print(f"⚠️ Gagal menambahkan tracker: {e}")

    return True
