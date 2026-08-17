# =====================================================
# app/bot.py
# Modul utama untuk menjalankan loop polling.
# =====================================================

import time
from config.settings import POLL_INTERVAL
from config.mt5_config import MT5Config, EMAConfig
from config.engulfing_config import EngulfingConfig
from config.execution_config import ExecutionConfig
from config.filter_c_config import FilterCConfig
from config.trading_schedule import is_trading_active, get_trading_status_text
from config.daily_guard import check_daily_target, get_daily_guard_status_text
from config.company_daily_guard import (
    check_company_daily_target,
    get_company_guard_status_text,
    should_send_company_notif,
)

from mt5_client import shutdown_mt5, get_closed_candles
from mt5_client.trade_monitor import check_closed_trades
from database import CandleRepo
from utils.colors import Colors, cprint, candle_color

from .initializer import startup_checks
from .tfm_logger import log_tfm_snapshot
from .signal_processor import process_candle_signal
from .engulfing_notifier import notify_engulfing_system_status, notify_company_target_reached


def run_bot():
    """Loop utama bot untuk memantau market secara realtime."""
    # 1. Load Configurations
    mt5_cfg = MT5Config()
    ema_cfg = EMAConfig()
    engulf_cfg = EngulfingConfig()
    exec_cfg = ExecutionConfig()
    fc_cfg = FilterCConfig() if engulf_cfg.filter_c_tfm_enabled else None

    # 2. Inisialisasi
    if not startup_checks(mt5_cfg, ema_cfg, exec_cfg, engulf_cfg, fc_cfg):
        return

    # 3. Main Loop Variables
    last_candle_time = {}  # dict to store last candle time per timeframe
    last_tfm_snapshot = {}  # dict to store last TFM snapshot per symbol
    total_candles = 0
    total_signals = 0

    print(f"\n🔄 Memulai scan realtime (interval: {POLL_INTERVAL}s)...")
    print(f"⏰ Trading Schedule  : {get_trading_status_text()}")
    print(f"🛡️ Daily Guard       : {get_daily_guard_status_text()}")
    print(f"🏂 Company Guard     : {get_company_guard_status_text()}\n")

    # Inisialisasi AutoTrading Guard
    from mt5_client.autotrading_guard import init_autotrading_state, check_and_notify_autotrading_change
    init_autotrading_state()

    # Kirim Notifikasi Sistem Aktif ke WA Outbox
    notify_engulfing_system_status('START')

    try:
        while True:
            check_and_notify_autotrading_change("MALING")
            # A. Cek trade yang sudah closed (SL/TP)
            check_closed_trades(mt5_cfg, ema_cfg)

            # B. TF Monitor — Periodic Snapshot Log
            if engulf_cfg.filter_c_tfm_enabled and fc_cfg:
                for symbol in mt5_cfg.symbols:
                    log_tfm_snapshot(symbol, fc_cfg, last_tfm_snapshot)

            # C. Cek Trading Schedule & Daily Target Guard
            # 1. Cek schedule jam kerja (individu per Tuyul)
            schedule_active = is_trading_active()

            # 2. Cek Company Daily Target (gabungan semua Tuyul)
            company_allowed, company_reason = check_company_daily_target()
            if not company_allowed and company_reason:
                # Kirim notif WA hanya sekali per hari
                if should_send_company_notif():
                    print(cprint(f"\n🏁 [COMPANY TARGET] {company_reason}", Colors.MAGENTA))
                    notify_company_target_reached(company_reason)

            # 3. Cek Individual Daily Guard (opsional, fallback)
            daily_allowed, daily_reason = check_daily_target()
            if not daily_allowed and daily_reason:
                print(cprint(f"   🛡️ [MALING Guard] {daily_reason}", Colors.YELLOW))

            # Bot boleh execute jika: jam kerja aktif DAN company target belum hit DAN individual guard belum hit
            trading_active = schedule_active and company_allowed and daily_allowed

            from mt5_client.position_tracker import PositionTracker, notify_system_paused_due_manual
            tracker = PositionTracker()

            # D. Scan Tiap Mata Uang dan Timeframe
            for symbol in mt5_cfg.symbols:
                snapshot = tracker.poll_positions(symbol)
                if tracker.has_manual_positions(symbol):
                    notify_system_paused_due_manual(symbol, snapshot.manual_count, snapshot.total_manual_floating)
                    continue

                target_tf = mt5_cfg.get_symbol_timeframe(symbol)
                
                # Pastikan target_tf ikut di-scan
                tfs_to_scan = set(mt5_cfg.timeframes)
                tfs_to_scan.add(target_tf)
                
                # Tambahkan semua TF info ke set scan
                for info_tf in mt5_cfg.info_timeframes:
                    tfs_to_scan.add(info_tf)

                for tf in tfs_to_scan:
                    # Ambil data candle
                    candle_data = get_closed_candles(symbol, mt5_cfg, ema_cfg, tf_label=tf, verbose=False)

                    if candle_data is None:
                        continue

                    current_time = candle_data["timestamp"]
                    tf_key = f"{symbol}_{tf}"

                    # Skip jika candle sama dengan sebelumnya
                    if tf_key in last_candle_time and current_time == last_candle_time[tf_key]:
                        continue

                    # =====================================================
                    # Candle baru terdeteksi!
                    # =====================================================
                    total_candles += 1
                    last_candle_time[tf_key] = current_time

                    # Tentukan warna berdasarkan arah candle
                    clr = candle_color(candle_data["is_bullish"])
                    
                    # Simpan candle ke Supabase
                    CandleRepo.upsert(candle_data)

                    # Deteksi pola Engulfing (hanya jika di dalam jam trading aktif)
                    if trading_active and (tf == target_tf or tf in mt5_cfg.info_timeframes):
                        added_sig = process_candle_signal(
                            symbol, tf, target_tf, candle_data,
                            engulf_cfg, mt5_cfg, exec_cfg, ema_cfg, clr
                        )
                        total_signals += added_sig

            # Heartbeat (Overwrites line to avoid spam)
            print(cprint(f"   📊 Heartbeat: {total_candles} candles scanned | {total_signals} executions", Colors.GRAY), end='\r', flush=True)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        # Clear heartbeat line
        print(" " * 80, end='\r')
        print(f"   📊 Total Run: {total_candles} candles scanned | {total_signals} executions")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Kirim Notifikasi Sistem Dimatikan ke WA Outbox
        notify_engulfing_system_status('STOP')
        shutdown_mt5()
