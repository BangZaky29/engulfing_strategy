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
    - Bullish Engulfing -> BUY Market, SL di Lowest C1/C2, TP 100 point.
    - Bearish Engulfing -> SELL Market, SL di Highest C1/C2, TP 100 point.
    """
    symbol = signal["symbol"]

    # 0. Cek apakah sudah ada posisi yang masih terbuka (aktif) untuk symbol ini
    # Jika ada, batalkan OP baru agar tidak terjadi multi OP
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
    point = symbol_info.point
    ask = tick.ask
    bid = tick.bid

    pattern = signal["pattern_type"]

    # Cari Highest High dan Lowest Low dari 2 candle trigger (C1 dan C2)
    highest_high = max(signal["prev_high"], signal["curr_high"])
    lowest_low = min(signal["prev_low"], signal["curr_low"])

    # 2. Setup Parameter Order
    if pattern == "bullish_engulfing":
        order_type = mt5.ORDER_TYPE_BUY
        price = ask
        # SL di ekor terbawah (Lowest Low C1/C2)
        sl_price = lowest_low
        # TP 100 point ke atas
        tp_price = price + (exec_cfg.tp_points * point)
        comment = "Engulf_BUY"

    elif pattern == "bearish_engulfing":
        order_type = mt5.ORDER_TYPE_SELL
        price = bid
        # SL di head teratas (Highest High C1/C2)
        sl_price = highest_high
        # TP 100 point ke bawah
        tp_price = price - (exec_cfg.tp_points * point)
        comment = "Engulf_SELL"

    else:
        print(f"❌ Pola tidak dikenali: {pattern}")
        return False

    # 3. Request ke MT5
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": exec_cfg.lot_size,
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

    print(f"\n🚀 Mengirim Eksekusi {comment} ...")
    print(f"   Harga OP : {round(price, digits)}")
    print(f"   SL       : {round(sl_price, digits)} (Jarak: {abs(round(price - sl_price, digits))} harga)")
    print(f"   TP       : {round(tp_price, digits)} ({exec_cfg.tp_points} point)")

    # Kirim order
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
