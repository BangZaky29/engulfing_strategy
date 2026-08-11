# =====================================================
# app/signal_processor.py
# Deteksi engulfing, eksekusi order, dan simpan log ke Supabase.
# =====================================================

import json
import copy
from datetime import datetime

from config.mt5_config import MT5Config, EMAConfig
from config.engulfing_config import EngulfingConfig
from config.execution_config import ExecutionConfig
from database import SignalRepo, StatsRepo
from mt5_client import execute_engulfing_order
from strategies.engulfing import detect_engulfing

def process_candle_signal(
    symbol: str, 
    tf: str, 
    target_tf: str,
    candle_data: dict,
    engulf_cfg: EngulfingConfig,
    mt5_cfg: MT5Config,
    exec_cfg: ExecutionConfig,
    ema_cfg: EMAConfig,
    clr: str
) -> int:
    """
    Jalankan deteksi engulfing, jika valid eksekusi dan catat signal.
    Return 1 jika sinyal dieksekusi (untuk counter total_signals), 0 jika tidak.
    """
    total_signals_added = 0
    signal = detect_engulfing(candle_data, cfg=engulf_cfg, verbose=False, color=clr)

    if signal:
        # Cek apakah sinyal ini dilewati (skipped)
        if signal.get("skip_reason"):
            if tf == target_tf:
                # Simpan skipped signal agar WA bisa mengirim notifikasi ke PRIVATE_JID
                # Jangan simpan jika pattern_type tidak valid (contoh: 'none' karena Doji)
                if signal.get("pattern_type") and signal.get("pattern_type") != "none":
                    SignalRepo.upsert(signal)
        else:
            is_h1_direct = False
            if tf == "H1" and engulf_cfg.h1_direct_execute_enabled:
                _, max_dist = engulf_cfg.get_ema_distance_limits(symbol)
                try:
                    notes_obj = json.loads(signal.get("notes", "{}"))
                    ema_dist = notes_obj.get("ema_distance_pts")
                    if ema_dist is not None and ema_dist <= max_dist:
                        is_h1_direct = True
                        notes_obj["h1_direct_execute"] = True
                        notes_obj["h1_direct_max_dist"] = max_dist
                        signal["notes"] = json.dumps(notes_obj)
                except Exception as e:
                    pass

            if tf == target_tf or is_h1_direct:
                total_signals_added += 1

                # =====================================================
                # Eksekusi Order di MT5
                # =====================================================
                ticket_id, exec_skip_reason = execute_engulfing_order(signal, mt5_cfg, exec_cfg, ema_cfg)

                # Flag is_confirmed menandakan OP dieksekusi di market
                signal["is_confirmed"] = bool(ticket_id)
                
                if ticket_id:
                    signal["ticket_id"] = ticket_id
                    try:
                        from mt5_client.position_tracker import PositionTracker
                        PositionTracker().register_system_ticket(
                            symbol=symbol,
                            ticket=ticket_id,
                            strategy="ENGULFING",
                            magic=exec_cfg.magic_number,
                            direction=str(signal.get("action_str", "BUY")).upper(),
                            volume=exec_cfg.get_lot_size(symbol),
                            open_price=signal.get("curr_close", 0.0)
                        )
                    except Exception as ex:
                        print(f"⚠️ Gagal register Engulfing ticket ke PositionTracker: {ex}")
                    try:
                        notes_obj = json.loads(signal["notes"])
                        notes_obj["ticket_id"] = ticket_id
                        # Inject TFM data ke notes jika ada
                        if signal.get("tfm_status"):
                            notes_obj["tfm_status"] = signal["tfm_status"]
                            notes_obj["tfm_bias"] = signal.get("tfm_bias")
                            notes_obj["tfm_snapshot"] = signal.get("tfm_snapshot")
                        signal["notes"] = json.dumps(notes_obj)
                    except Exception as e:
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
                        except Exception as e:
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
                except Exception as e:
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
                            except Exception as e:
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
                            except Exception as e:
                                notes_obj = {}
                            notes_obj["sync_with"] = other_tf
                            notes_obj["ticket_id"] = "INFO_SYNC"
                            sync_signal["notes"] = json.dumps(notes_obj)
                            
                            SignalRepo.upsert(sync_signal)

    return total_signals_added
