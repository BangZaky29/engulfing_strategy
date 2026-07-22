import os
import sys
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure paths are correct
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from database.supabase_client import get_supabase
from config.engulfing_config import EngulfingConfig
from config.filter_c_config import FilterCConfig

def fix_ticket_871461760(target_ticket=871461760):
    supabase = get_supabase()
    eng_cfg = EngulfingConfig()
    fc_cfg = FilterCConfig()
    
    print(f"==================================================")
    print(f"Memproses perbaikan tiket #{target_ticket}...")
    print(f"==================================================")
    
    res = supabase.table("trade_analytics").select("*").eq("ticket_id", target_ticket).execute()
    if not res.data:
        print(f"❌ Tiket {target_ticket} tidak ditemukan di trade_analytics!")
        return False
        
    trade = res.data[0]
    sym = trade.get("symbol")
    entry_time_str = trade.get("entry_time")
    notes_raw = trade.get("notes") or {}
    
    if isinstance(notes_raw, str):
        try:
            notes = json.loads(notes_raw)
        except Exception:
            notes = {}
    else:
        notes = dict(notes_raw)
        
    # 1. Coba ambil dari engulfing_signals terlebih dahulu
    dist_pts = None
    status = None
    min_pts = None
    max_pts = None
    h1_time_str = None
    
    sig_res = supabase.table("engulfing_signals").select("*").eq("ticket_id", target_ticket).execute()
    if sig_res.data and len(sig_res.data) > 0:
        sig = sig_res.data[0]
        sig_notes_raw = sig.get("notes") or {}
        if isinstance(sig_notes_raw, str):
            try:
                sig_notes = json.loads(sig_notes_raw)
            except Exception:
                sig_notes = {}
        else:
            sig_notes = dict(sig_notes_raw)
            
        dist_pts = sig_notes.get("ema_distance_pts") or sig_notes.get("h1_ema_distance_pts")
        status = sig_notes.get("ema_distance_status") or sig_notes.get("h1_ema_distance_status")
        min_pts = sig_notes.get("ema_distance_min") or sig_notes.get("h1_ema_distance_min")
        max_pts = sig_notes.get("ema_distance_max") or sig_notes.get("h1_ema_distance_max")
        h1_time_str = sig_notes.get("h1_trigger_time")
        
        if dist_pts is not None:
            print(f"✅ Ditemukan data dari engulfing_signals untuk #{target_ticket}: {dist_pts} pts ({status})")

    # 2. Jika di signal tidak ada, kalkulasi historis menggunakan MT5
    if dist_pts is None and sym and entry_time_str:
        print("⚠️ Data di signal tidak lengkap, mencoba kalkulasi via MT5 historical candles...")
        try:
            import MetaTrader5 as mt5
            from database.backfill_h1_historical import fetch_historical_h1_candles, _get_point, calculate_ema_series, find_latest_h1_state
            
            if mt5.initialize():
                dt = datetime.fromisoformat(entry_time_str.replace("Z", "+00:00"))
                h1_candles = fetch_historical_h1_candles(sym, dt, 250)
                if len(h1_candles) >= 50:
                    point = _get_point(sym)
                    h1_closes = [c["close"] for c in h1_candles]
                    h1_ema = calculate_ema_series(h1_closes, 20)
                    h1_res = find_latest_h1_state(h1_candles, point, h1_ema, fc_cfg)
                    if h1_res and h1_res.direction != 0 and h1_res.time:
                        try:
                            idx = next(i for i, c in enumerate(h1_candles) if c["time"] == h1_res.time)
                            h1_ema_val = h1_ema[idx]
                            hc = h1_candles[idx]
                            dist_raw = abs(hc["open"] - h1_ema_val)
                            dist_pts = round(dist_raw / point) if point > 0 else 0
                            min_pts, max_pts = eng_cfg.get_ema_distance_limits(sym)
                            status = "STRONG"
                            if dist_pts < min_pts:
                                status = "INVALID"
                            elif dist_pts > max_pts:
                                status = "VALID"
                            
                            if hasattr(h1_res.time, "strftime"):
                                h1_time_str = h1_res.time.strftime("%H:%M")
                            else:
                                h1_time_str = datetime.fromtimestamp(h1_res.time, tz=timezone.utc).strftime("%H:%M")
                            print(f"✅ Kalkulasi MT5 sukses: {dist_pts} pts ({status}) jam {h1_time_str}")
                        except StopIteration:
                            pass
        except Exception as ex:
            print(f"⚠️ Gagal kalkulasi via MT5: {ex}")

    # 3. Update notes ke trade_analytics
    if dist_pts is not None:
        notes["ema_distance_pts"] = dist_pts
        notes["h1_ema_distance_pts"] = dist_pts
        notes["ema_distance_status"] = status
        notes["h1_ema_distance_status"] = status
        if min_pts is not None:
            notes["ema_distance_min"] = min_pts
            notes["h1_ema_distance_min"] = min_pts
        if max_pts is not None:
            notes["ema_distance_max"] = max_pts
            notes["h1_ema_distance_max"] = max_pts
        if h1_time_str is not None:
            notes["h1_trigger_time"] = h1_time_str
            
        supabase.table("trade_analytics").update({"notes": notes}).eq("id", trade["id"]).execute()
        print(f"🎉 SUKSES UPDATE Tiket #{target_ticket}: EMA Distance = {dist_pts} pts | Status = {status} | Trigger Time = {h1_time_str}")
        return True
    else:
        print(f"❌ Gagal mendapatkan nilai EMA Distance untuk tiket #{target_ticket}")
        return False

def backfill_all_missing_trades():
    supabase = get_supabase()
    res = supabase.table("trade_analytics").select("*").order("id", desc=True).limit(200).execute()
    trades = res.data or []
    fixed_count = 0
    for t in trades:
        tid = t.get("ticket_id")
        notes_raw = t.get("notes") or {}
        if isinstance(notes_raw, str):
            try:
                notes = json.loads(notes_raw)
            except Exception:
                notes = {}
        else:
            notes = dict(notes_raw)
            
        if "ema_distance_pts" not in notes and "h1_ema_distance_pts" not in notes and tid:
            print(f"\nTrade #{tid} belum memiliki EMA distance, memproses...")
            if fix_ticket_871461760(tid):
                fixed_count += 1
                
    print(f"\n==================================================")
    print(f"Selesai backfill {fixed_count} trade yang sebelumnya tidak memiliki EMA distance.")
    print(f"==================================================")

if __name__ == "__main__":
    fix_ticket_871461760(871461760)
    backfill_all_missing_trades()
