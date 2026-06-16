# =====================================================
# main.py - Entry point: Engulfing Pattern Scanner
# Realtime MT5 → Supabase
# =====================================================

import time
from datetime import datetime

from config.settings import validate_env, POLL_INTERVAL
from config.mt5_config import MT5Config, EMAConfig
from config.engulfing_config import EngulfingConfig
from config.execution_config import ExecutionConfig

from mt5_client import init_mt5, shutdown_mt5, get_closed_candles, execute_engulfing_order
from mt5_client.trade_monitor import check_closed_trades
from database import CandleRepo, SignalRepo, StatsRepo
from strategies.engulfing import detect_engulfing


def print_banner(mt5_cfg: MT5Config, ema_cfg: EMAConfig):
    print("=" * 60)
    print("🕯️  ENGULFING PATTERN SCANNER (MODULAR)")
    print(f"   Symbol    : {mt5_cfg.symbol}")
    print(f"   Scan TFs  : {', '.join(mt5_cfg.timeframes)}")
    print(f"   Strategy  : {mt5_cfg.strategy_timeframe}")
    print(f"   EMA       : {ema_cfg.labels['fast']} / {ema_cfg.labels['slow']}")
    print(f"   Database  : Supabase (metaTrader5)")
    print("=" * 60)


def main():
    # 1. Validasi Environment Variables
    try:
        validate_env()
    except EnvironmentError as e:
        print(e)
        return

    # 2. Load Configurations
    mt5_cfg = MT5Config()
    ema_cfg = EMAConfig()
    engulf_cfg = EngulfingConfig()
    exec_cfg = ExecutionConfig()

    print_banner(mt5_cfg, ema_cfg)

    # 3. Inisialisasi MT5
    if not init_mt5(mt5_cfg):
        return

    # =====================================================
    # 4. Main Loop - Polling candle baru
    # =====================================================
    last_candle_time = {}  # dict to store last candle time per timeframe
    total_candles = 0
    total_signals = 0

    print(f"\n🔄 Memulai scan realtime (interval: {POLL_INTERVAL}s)...\n")

    try:
        while True:
            # 1. Cek apakah ada trade yang sudah close (SL/TP) untuk upload screenshot
            check_closed_trades(mt5_cfg, ema_cfg)

            for tf in mt5_cfg.timeframes:
                # Ambil data candle
                candle_data = get_closed_candles(mt5_cfg, ema_cfg, tf_label=tf, verbose=False)

                if candle_data is None:
                    continue

                current_time = candle_data["timestamp"]

                # Skip jika candle sama dengan sebelumnya
                if tf in last_candle_time and current_time == last_candle_time[tf]:
                    continue

                # =====================================================
                # Candle baru terdeteksi!
                # =====================================================
                total_candles += 1
                last_candle_time[tf] = current_time

                warna = "🟩" if candle_data["is_bullish"] else "🟥"
                print(f"\n{'─' * 55}")
                print(f"{warna} [{mt5_cfg.symbol} {tf}] {current_time}")
                print(f"   O: {candle_data['open_']:.2f}  H: {candle_data['high_']:.2f}  "
                      f"L: {candle_data['low_']:.2f}  C: {candle_data['close_']:.2f}  "
                      f"V: {candle_data['volume']:.0f}  Spread: {candle_data['spread']}")
                print(f"   📈 {ema_cfg.labels['fast']}: {candle_data['ema_fast']:.2f} | "
                      f"{ema_cfg.labels['slow']}: {candle_data['ema_slow']:.2f}")

                # =====================================================
                # Simpan candle ke Supabase
                # =====================================================
                CandleRepo.upsert(candle_data)

                # =====================================================
                # Deteksi pola Engulfing HANYA untuk Strategy TF (M1)
                # =====================================================
                if tf == mt5_cfg.strategy_timeframe:
                    signal = detect_engulfing(candle_data, cfg=engulf_cfg, verbose=True)

                    if signal:
                        # Cek apakah sinyal ini dilewati (skipped)
                        if signal.get("skip_reason"):
                            SignalRepo.upsert(signal)
                        else:
                            total_signals += 1

                            # =====================================================
                            # Eksekusi Order di MT5
                            # =====================================================
                            ticket_id, exec_skip_reason = execute_engulfing_order(signal, mt5_cfg, exec_cfg, ema_cfg)

                            # Flag is_confirmed menandakan OP dieksekusi di market
                            signal["is_confirmed"] = bool(ticket_id)
                            
                            if ticket_id:
                                signal["ticket_id"] = ticket_id
                                import json
                                try:
                                    notes_obj = json.loads(signal["notes"])
                                    notes_obj["ticket_id"] = ticket_id
                                    signal["notes"] = json.dumps(notes_obj)
                                except:
                                    pass
                            else:
                                signal["skip_reason"] = exec_skip_reason or "Eksekusi MT5 gagal"

                            # Simpan sinyal ke Supabase
                            SignalRepo.upsert(signal)

                            # Update statistik harian
                            today = datetime.now().strftime("%Y-%m-%d")
                            StatsRepo.update_daily(
                                symbol=signal["symbol"],
                                timeframe=signal["timeframe"],
                                date_str=today,
                                pattern_type=signal["pattern_type"],
                                confidence=signal["confidence_score"]
                            )

            # Status counter
            print(f"   📊 Total: {total_candles} candles | {total_signals} signals", end='\r')

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\n🛑 Scanner dihentikan oleh user.")
        print(f"   📊 Total: {total_candles} candles | {total_signals} engulfing signals")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        shutdown_mt5()


if __name__ == "__main__":
    main()
