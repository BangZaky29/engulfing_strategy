# =====================================================
# main.py - Entry point: Engulfing Pattern Scanner
# Realtime MT5 → Supabase
# =====================================================

import time
import json
import copy
from datetime import datetime

from config.settings import validate_env, POLL_INTERVAL
from config.mt5_config import MT5Config, EMAConfig
from config.engulfing_config import EngulfingConfig
from config.execution_config import ExecutionConfig
from config.filter_c_config import FilterCConfig

from mt5_client import init_mt5, shutdown_mt5, get_closed_candles, execute_engulfing_order
from mt5_client.trade_monitor import check_closed_trades
from database import CandleRepo, SignalRepo, StatsRepo
from strategies.engulfing import detect_engulfing
from utils.colors import Colors, cprint, candle_color


def print_banner(mt5_cfg: MT5Config, ema_cfg: EMAConfig):
    print("=" * 60)
    print("🕯️  ENGULFING PATTERN SCANNER (MODULAR)")
    print(f"   Symbols   : {', '.join(mt5_cfg.symbols)}")
    
    # Tampilkan timeframe eksekusi spesifik per mata uang
    tf_str_list = [f"{sym}({mt5_cfg.get_symbol_timeframe(sym)})" for sym in mt5_cfg.symbols]
    print(f"   Execute TF: {', '.join(tf_str_list)}")
    print(f"   Info TFs  : {', '.join(mt5_cfg.info_timeframes)}")
    print(f"   EMA       : {ema_cfg.labels['fast']} / {ema_cfg.labels['slow']}")
    print(f"   Database  : Supabase (metaTrader5)")
    print("=" * 60)


def print_tfm_trigger_status(fc_cfg: FilterCConfig):
    for tf in ["M5", "M15", "H1"]:
        print(cprint(f"   TF {tf}", Colors.CYAN))
        
        db_val = fc_cfg.get_use_dominan_break(tf)
        eng_val = fc_cfg.get_use_engulfing(tf)
        mar_val = fc_cfg.get_use_marubozu(tf)
        pin_val = fc_cfg.get_use_pinbar(tf)
        ict_val = fc_cfg.get_use_ict(tf)
        
        print(cprint(f"   * DB = {'Aktif (True)' if db_val else 'Non-Aktif (False)'}", Colors.CYAN))
        print(cprint(f"   * Engulfing = {'Aktif (True)' if eng_val else 'Non-Aktif (False)'}", Colors.CYAN))
        print(cprint(f"   * Marobosho = {'Aktif (True)' if mar_val else 'Non-Aktif (False)'}", Colors.CYAN))
        print(cprint(f"   * Pinbar = {'Aktif (True)' if pin_val else 'Non-Aktif (False)'}", Colors.CYAN))
        print(cprint(f"   * ITC = {'Aktif (True)' if ict_val else 'Non-Aktif (False)'}", Colors.CYAN))


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
    fc_cfg = FilterCConfig() if engulf_cfg.filter_c_tfm_enabled else None

    print_banner(mt5_cfg, ema_cfg)

    if engulf_cfg.filter_c_tfm_enabled and fc_cfg:
        print(cprint("📡 [TF Monitor] Filter C AKTIF — H1 Bias + M15 Confirm + M5 Trigger", Colors.CYAN))
        print(cprint(f"   EMA Filter: {'ON' if fc_cfg.use_ema_filter else 'OFF'} | Lookback: {fc_cfg.trigger_lookback_bars} bars", Colors.CYAN))
        print(cprint(f"   Blocking: {'ON (WAIT/LATE = skip)' if fc_cfg.filter_c_blocking else 'OFF (tag only)'}", Colors.CYAN))
        print_tfm_trigger_status(fc_cfg)

    # 3. Inisialisasi MT5
    if not init_mt5(mt5_cfg):
        return

    # =====================================================
    # 4. Main Loop - Polling candle baru
    # =====================================================
    last_candle_time = {}  # dict to store last candle time per timeframe
    last_tfm_snapshot = {}  # dict to store last TFM snapshot per symbol
    total_candles = 0
    total_signals = 0

    print(f"\n🔄 Memulai scan realtime (interval: {POLL_INTERVAL}s)...\n")

    try:
        while True:
            # 1. Cek apakah ada trade yang sudah close (SL/TP) untuk upload screenshot
            check_closed_trades(mt5_cfg, ema_cfg)

            # =====================================================
            # 1.5 TF Monitor — Periodic Snapshot Log
            # =====================================================
            if engulf_cfg.filter_c_tfm_enabled and fc_cfg:
                try:
                    from strategies.engulfing.filters_C import check_tf_monitor
                    for symbol in mt5_cfg.symbols:
                        tfm_result = check_tf_monitor(symbol, cfg=fc_cfg)
                        snapshot = tfm_result.get("snapshot", "")
                        is_new = tfm_result.get("is_new_event", False)

                        if is_new and snapshot and snapshot != last_tfm_snapshot.get(symbol):
                            print(cprint(f"📡 {snapshot}", Colors.CYAN))
                            last_tfm_snapshot[symbol] = snapshot

                            # Insert TFM status change ke Supabase untuk WA notification
                            tfm_signal = {
                                "symbol": symbol,
                                "timeframe": f"TFM_{tfm_result['status']}",
                                "signal_time": datetime.now(),
                                "pattern_type": "bullish_engulfing" if "Buy" in tfm_result.get("bias_column", "") else "bearish_engulfing",
                                "prev_open": 0, "prev_close": 0, "prev_high": 0, "prev_low": 0,
                                "curr_open": 0, "curr_close": 0, "curr_high": 0, "curr_low": 0,
                                "engulf_ratio": 0, "volume": 0,
                                "ema_fast_value": 0, "ema_slow_value": 0,
                                "ema_trend": tfm_result["status"],
                                "confidence_score": 0,
                                "is_confirmed": True,
                                "ticket_id": None,
                                "notes": json.dumps({
                                    "ticket_id": "TFM_STATUS_CHANGE",
                                    "tfm_status": tfm_result["status"],
                                    "tfm_bias": tfm_result["bias_column"],
                                    "tfm_snapshot": snapshot,
                                    "grade": "N/A", "action_str": "NONE",
                                    "body_pct": 0, "cp_pct": 0, "sl_pct_used": 0,
                                    "rr_ratio": 0, "sl_pts": 0, "ring_pts": 0,
                                    "op_price": 0, "sl_price": 0, "tp_price": None,
                                    "total_score": 0, "market_state": "TFM",
                                    "trading_session": "",
                                }),
                            }
                            SignalRepo.upsert(tfm_signal)

                except Exception as e:
                    pass  # TFM error non-blocking

            for symbol in mt5_cfg.symbols:
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

                    # Tentukan warna berdasarkan arah candle (dipakai seluruh blok)
                    clr = candle_color(candle_data["is_bullish"])
                    warna = "🟩" if candle_data["is_bullish"] else "🟥"
                    
                    # Clean tabular terminal log dihapus agar tidak spam
                    # time_str = current_time.strftime("%H:%M:%S") if hasattr(current_time, 'strftime') else current_time
                    # log_line = (
                    #     f"[{time_str}] {warna} {symbol} ({tf}) | "
                    #     f"O: {candle_data['open_']:.5f} H: {candle_data['high_']:.5f} "
                    #     f"L: {candle_data['low_']:.5f} C: {candle_data['close_']:.5f} | "
                    #     f"EMA: {candle_data['ema_fast']:.5f}/{candle_data['ema_slow']:.5f}"
                    # )
                    # print(cprint(log_line, clr))

                    # =====================================================
                    # Simpan candle ke Supabase
                    # =====================================================
                    CandleRepo.upsert(candle_data)

                    # =====================================================
                    # Deteksi pola Engulfing
                    # =====================================================
                    if tf == target_tf or tf in mt5_cfg.info_timeframes:
                        signal = detect_engulfing(candle_data, cfg=engulf_cfg, verbose=False, color=clr)

                        if signal:
                            # Cek apakah sinyal ini dilewati (skipped)
                            if signal.get("skip_reason"):
                                if tf == target_tf:
                                    # Simpan skipped signal agar WA bisa mengirim notifikasi ke PRIVATE_JID
                                    SignalRepo.upsert(signal)
                            else:
                                if tf == target_tf:
                                    total_signals += 1

                                    # =====================================================
                                    # Eksekusi Order di MT5
                                    # =====================================================
                                    ticket_id, exec_skip_reason = execute_engulfing_order(signal, mt5_cfg, exec_cfg, ema_cfg)

                                    # Flag is_confirmed menandakan OP dieksekusi di market
                                    signal["is_confirmed"] = bool(ticket_id)
                                    
                                    if ticket_id:
                                        signal["ticket_id"] = ticket_id
                                        try:
                                            notes_obj = json.loads(signal["notes"])
                                            notes_obj["ticket_id"] = ticket_id
                                            # Inject TFM data ke notes jika ada
                                            if signal.get("tfm_status"):
                                                notes_obj["tfm_status"] = signal["tfm_status"]
                                                notes_obj["tfm_bias"] = signal.get("tfm_bias")
                                                notes_obj["tfm_snapshot"] = signal.get("tfm_snapshot")
                                            signal["notes"] = json.dumps(notes_obj)
                                        except:
                                            pass
                                    else:
                                        signal["skip_reason"] = exec_skip_reason or "Eksekusi MT5 gagal"
                                        signal["skip_reasons"] = [signal["skip_reason"]]
                                        if exec_skip_reason and "Ada posisi aktif" in exec_skip_reason:
                                            # Bypass Supabase filter agar info ini dikirim ke WA
                                            signal["is_confirmed"] = True
                                            signal["ticket_id"] = None
                                            try:
                                                notes_obj = json.loads(signal.get("notes", "{}"))
                                                notes_obj["ticket_id"] = "INFO_ACTIVE"
                                                notes_obj["skip_reason"] = signal["skip_reason"]
                                                notes_obj["skip_reasons"] = signal["skip_reasons"]
                                                notes_obj["active_position_info"] = exec_skip_reason
                                                if signal.get("tfm_status"):
                                                    notes_obj["tfm_status"] = signal["tfm_status"]
                                                    notes_obj["tfm_bias"] = signal.get("tfm_bias")
                                                    notes_obj["tfm_snapshot"] = signal.get("tfm_snapshot")
                                                if signal.get("m5_trigger_source"):
                                                    notes_obj["m5_trigger_source"] = signal["m5_trigger_source"]
                                                signal["notes"] = json.dumps(notes_obj)
                                            except:
                                                pass

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
                                else:
                                    # Info Signal M15 / H1
                                    # Simpan signal info ke DB (WA bot akan broadcast ini)
                                    
                                    signal["is_confirmed"] = True
                                    signal["ticket_id"] = None
                                    try:
                                        notes_obj = json.loads(signal.get("notes", "{}"))
                                    except:
                                        notes_obj = {}
                                    notes_obj["ticket_id"] = f"INFO_{tf}"
                                    signal["notes"] = json.dumps(notes_obj)
                                    
                                    SignalRepo.upsert(signal)
                                    
                                    # --- Pengecekan Sync dengan TF Info lainnya ---
                                    recent_signals = None
                                    
                                    for other_tf in mt5_cfg.info_timeframes:
                                        if other_tf == tf:
                                            continue
                                            
                                        if recent_signals is None:
                                            recent_signals = SignalRepo.get_recent(symbol=symbol, limit=20)
                                        
                                        # Cari signal terbaru dari other_tf yang is_confirmed=True dan tidak skipped
                                        latest_other = next((s for s in recent_signals if s.get("timeframe") == other_tf and s.get("is_confirmed") and not s.get("skip_reason")), None)
                                        
                                        if latest_other and latest_other.get("pattern_type") == signal["pattern_type"]:
                                            # Jika ditemukan sinyal dengan arah yang sama (Sync)
                                            
                                            # Hindari insert sync berulang-ulang di waktu yang berdekatan
                                            # (Cek apakah sudah ada INFO_SYNC untuk pasangan ini di 24 jam terakhir)
                                            latest_sync = None
                                            for s in recent_signals:
                                                try:
                                                    s_notes = json.loads(s.get("notes", "{}"))
                                                except:
                                                    s_notes = {}
                                                if s_notes.get("ticket_id") == "INFO_SYNC" and s.get("pattern_type") == signal["pattern_type"]:
                                                    latest_sync = s
                                                    break
                                            
                                            is_new_sync = True
                                            if latest_sync:
                                                # Cek selisih waktu
                                                if hasattr(latest_sync.get("signal_time"), "timestamp") and hasattr(signal.get("signal_time"), "timestamp"):
                                                    time_diff = abs(signal["signal_time"].timestamp() - latest_sync["signal_time"].timestamp())
                                                    if time_diff < 14400: # 4 jam
                                                        is_new_sync = False
                                            
                                            if is_new_sync:
                                                sync_signal = copy.deepcopy(signal)
                                                # Modifikasi key agar unik (timeframe gabungan)
                                                sync_signal["timeframe"] = f"SYNC_{tf}_{other_tf}"
                                                sync_signal["ticket_id"] = None
                                                
                                                try:
                                                    notes_obj = json.loads(sync_signal.get("notes", "{}"))
                                                except:
                                                    notes_obj = {}
                                                notes_obj["sync_with"] = other_tf
                                                notes_obj["ticket_id"] = "INFO_SYNC"
                                                sync_signal["notes"] = json.dumps(notes_obj)
                                                
                                                SignalRepo.upsert(sync_signal)

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
        shutdown_mt5()


if __name__ == "__main__":
    main()
