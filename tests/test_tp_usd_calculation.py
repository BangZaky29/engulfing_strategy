"""
tests/test_tp_usd_calculation.py
=================================
Testing script untuk validasi TP USD mode.

Cara kerja:
  1. Connect ke MT5 yang sedang berjalan (harus sudah login)
  2. Baca semua symbol dari MT5_SYMBOLS di .env
  3. Untuk tiap symbol:
     - Ambil lot size dari LOT_<symbol> di .env (sama persis dengan bot)
     - Ambil tick_value & tick_size REAL dari MT5 symbol_info
     - Hitung TP price menggunakan calculate_tp_price_usd()
     - Hitung BALIK profit USD dari TP price yang didapat
     - Bandingkan dengan target $5 (toleransi $0.05)
  4. Print ✅ PASS / ❌ FAIL per symbol

Tidak mengirim order apapun — murni baca data, aman dijalankan kapan saja.

Jalankan:
    python tests/test_tp_usd_calculation.py
"""

import sys
import os

# Root project ada di parent dari folder tests/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env agar config bisa baca variable
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    # dotenv opsional — kalau gak ada, pakai os.environ yang sudah di-set
    pass

import MetaTrader5 as mt5  # type: ignore
from config.mt5_config import MT5Config
from config.execution_config import ExecutionConfig


def run_test():
    mt5_cfg = MT5Config()
    exec_cfg = ExecutionConfig()

    target_usd = exec_cfg.tp_target_usd_b
    tp_mode    = exec_cfg.tp_mode_b

    print("=" * 70)
    print(f"  TEST TP USD MODE — Target: ${target_usd:.2f} | Mode: {tp_mode}")
    print("=" * 70)

    if tp_mode != "USD":
        print(f"\n⚠️  EXECUTION_TP_MODE_B saat ini = '{tp_mode}' (bukan USD).")
        print("   Set EXECUTION_TP_MODE_B=USD di .env lalu jalankan ulang.")
        return

    # --- Init MT5 ---
    if not mt5.initialize(
        path=mt5_cfg.path,
        login=mt5_cfg.login,
        server=mt5_cfg.server,
        password=mt5_cfg.password,
    ):
        print(f"❌ Gagal init MT5: {mt5.last_error()}")
        return

    print(f"✅ MT5 Terhubung: {mt5.terminal_info().name}\n")

    # --- Ambil symbol list dari .env ---
    symbols_raw = os.getenv("MT5_SYMBOLS", "XAUUSD")
    symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]

    all_passed = True
    tolerance  = 0.05  # toleransi $0.05 untuk rounding float

    for symbol in symbols:
        print(f"--- Symbol: {symbol} ---")

        # Pastikan symbol aktif di MT5
        if not mt5.symbol_select(symbol, True):
            print(f"  ❌ Gagal select symbol {symbol}\n")
            all_passed = False
            continue

        symbol_info = mt5.symbol_info(symbol)
        tick        = mt5.symbol_info_tick(symbol)

        if symbol_info is None or tick is None:
            print(f"  ❌ Gagal ambil info untuk {symbol}\n")
            all_passed = False
            continue

        tick_value     = symbol_info.trade_tick_value
        tick_size      = symbol_info.trade_tick_size
        contract_size  = symbol_info.trade_contract_size
        digits         = symbol_info.digits
        lot_size       = exec_cfg.get_lot_size(symbol)

        op_price_buy  = tick.ask   # simulasi BUY
        op_price_sell = tick.bid   # simulasi SELL

        print(f"  Lot Size       : {lot_size}")
        print(f"  Tick Value     : {tick_value}")
        print(f"  Tick Size      : {tick_size}")
        print(f"  Contract Size  : {contract_size}")
        print(f"  Digits         : {digits}")
        print(f"  OP (ASK/BUY)  : {op_price_buy}")
        print(f"  OP (BID/SELL) : {op_price_sell}")

        for action, op_price in [("BUY", op_price_buy), ("SELL", op_price_sell)]:
            try:
                tp_price = exec_cfg.calculate_tp_price_usd(
                    entry_price=op_price,
                    action_str=action,
                    lot_size=lot_size,
                    tick_value=tick_value,
                    tick_size=tick_size,
                )

                # Verifikasi balik: dari jarak TP ke OP, hitung profit USD
                tp_distance_price = abs(tp_price - op_price)
                # profit = ticks_count * tick_value * lot
                ticks_count       = tp_distance_price / tick_size if tick_size > 0 else 0
                profit_usd_check  = ticks_count * tick_value * lot_size

                is_correct = abs(profit_usd_check - target_usd) <= tolerance
                status = "✅ PASS" if is_correct else "❌ FAIL"
                if not is_correct:
                    all_passed = False

                direction = "↑" if action == "BUY" else "↓"
                print(
                    f"  {status} {action} {direction}"
                    f" | OP={op_price:.{digits}f}"
                    f" → TP={tp_price:.{digits}f}"
                    f" | Jarak={tp_distance_price:.{digits}f}"
                    f" | Profit=${profit_usd_check:.4f}"
                    f" (target=${target_usd:.2f})"
                )

                if not is_correct:
                    print(f"       ⚠️  SELISIH: ${abs(profit_usd_check - target_usd):.6f}")

            except Exception as e:
                print(f"  ❌ ERROR saat hitung TP {action}: {e}")
                all_passed = False

        print()

    # --- Shutdown ---
    mt5.shutdown()

    print("=" * 70)
    if all_passed:
        print("  🎉 SEMUA TEST LULUS! TP USD calculation BENAR untuk semua symbol.")
    else:
        print("  ❌ ADA TEST YANG GAGAL! Cek output di atas.")
    print("=" * 70)


if __name__ == "__main__":
    run_test()
