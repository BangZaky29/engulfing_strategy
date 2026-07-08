# =====================================================
# tests/test_tp_usd_calculation.py
# Testing khusus: verifikasi TP statis $USD dihitung benar
# per symbol, berdasarkan lot size masing-masing dari .env
# =====================================================
#
# Cara jalanin:
#   python tests/test_tp_usd_calculation.py
#
# Script ini TIDAK mengirim order apapun ke MT5.
# Cuma connect buat baca symbol_info (tick_value/tick_size),
# lalu hitung ulang TP price + verifikasi hasil profit USD-nya.

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
from config.execution_config import ExecutionConfig


def get_min_profit_distance(min_profit_usd: float, lot_size: float, tick_value: float, tick_size: float) -> float:
    """Copy persis dari mt5_client/execution.py biar test independen dari import order."""
    if min_profit_usd <= 0 or lot_size <= 0 or tick_value <= 0 or tick_size <= 0:
        return 0.0
    value_per_tick = tick_value * lot_size
    if value_per_tick <= 0:
        return 0.0
    ticks_needed = min_profit_usd / value_per_tick
    return ticks_needed * tick_size


def test_symbol(symbol: str, exec_cfg: ExecutionConfig):
    print(f"\n{'='*60}")
    print(f"TEST SYMBOL: {symbol}")
    print(f"{'='*60}")

    if not mt5.symbol_select(symbol, True):
        print(f"  ❌ Gagal select symbol {symbol}, skip.")
        return False

    symbol_info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if symbol_info is None or tick is None:
        print(f"  ❌ Gagal ambil symbol_info/tick untuk {symbol}, skip.")
        return False

    digits = symbol_info.digits
    tick_value = symbol_info.trade_tick_value
    tick_size = symbol_info.trade_tick_size
    ask = tick.ask
    bid = tick.bid

    # Lot dinamis dari .env, sesuai symbol (LOT_XAUUSD, LOT_Bitcoin, dst)
    lot_size = exec_cfg.get_lot_size(symbol)
    target_usd = exec_cfg.tp_target_usd_b

    print(f"  Digits       : {digits}")
    print(f"  Tick Value   : {tick_value}")
    print(f"  Tick Size    : {tick_size}")
    print(f"  Lot Size     : {lot_size}  (dari .env, key otomatis dicari)")
    print(f"  Target TP    : ${target_usd:.2f}")

    tp_distance = get_min_profit_distance(target_usd, lot_size, tick_value, tick_size)

    if tp_distance <= 0:
        print(f"  ❌ FAIL: tp_distance = 0, cek tick_value/tick_size/lot_size.")
        return False

    print(f"  TP Distance  : {tp_distance:.{digits}f} (dalam satuan harga)")

    ok_all = True

    # ── Simulasi BUY ──
    op_price_buy = ask
    tp_price_buy = op_price_buy + tp_distance
    ticks_moved_buy = (tp_price_buy - op_price_buy) / tick_size
    profit_buy = ticks_moved_buy * tick_value * lot_size

    print(f"\n  [BUY]  OP price   : {op_price_buy:.{digits}f}")
    print(f"  [BUY]  TP price   : {tp_price_buy:.{digits}f}")
    print(f"  [BUY]  Profit hasil hitung ulang : ${profit_buy:.2f}  (target: ${target_usd:.2f})")
    if abs(profit_buy - target_usd) > 0.05:
        print(f"  ❌ FAIL: selisih > $0.05")
        ok_all = False
    else:
        print(f"  ✅ PASS")

    # ── Simulasi SELL ──
    op_price_sell = bid
    tp_price_sell = op_price_sell - tp_distance
    ticks_moved_sell = (op_price_sell - tp_price_sell) / tick_size
    profit_sell = ticks_moved_sell * tick_value * lot_size

    print(f"\n  [SELL] OP price   : {op_price_sell:.{digits}f}")
    print(f"  [SELL] TP price   : {tp_price_sell:.{digits}f}")
    print(f"  [SELL] Profit hasil hitung ulang : ${profit_sell:.2f}  (target: ${target_usd:.2f})")
    if abs(profit_sell - target_usd) > 0.05:
        print(f"  ❌ FAIL: selisih > $0.05")
        ok_all = False
    else:
        print(f"  ✅ PASS")

    return ok_all


def main():
    if not mt5.initialize():
        print("❌ MetaTrader5 initialization failed. Pastikan terminal MT5 lagi jalan & login.")
        return

    exec_cfg = ExecutionConfig()

    print(f"Mode TP saat ini : {exec_cfg.tp_mode_b}")
    print(f"Target USD       : ${exec_cfg.tp_target_usd_b}")

    if exec_cfg.tp_mode_b != "USD":
        print("\n⚠️  EXECUTION_TP_MODE_B bukan 'USD'. Set dulu di .env sebelum test ini valid.")

    # Test semua symbol yang biasa dipakai bot (sesuai .env MT5_SYMBOLS)
    symbols_env = os.getenv("MT5_SYMBOLS", "XAUUSD,NASDAQ-100,BTC")
    symbols = [s.strip() for s in symbols_env.split(",") if s.strip()]

    results = {}
    for sym in symbols:
        results[sym] = test_symbol(sym, exec_cfg)

    print(f"\n{'='*60}")
    print("RINGKASAN")
    print(f"{'='*60}")
    for sym, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {sym:<15} {status}")

    mt5.shutdown()


if __name__ == "__main__":
    main()