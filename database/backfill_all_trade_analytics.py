import os
import sys
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure paths are correct
sys.path.insert(0, os.getcwd())
load_dotenv()

from database.supabase_client import get_supabase
from database.backfill_h1_historical import fetch_historical_h1_candles, _get_point, calculate_ema_series, find_latest_h1_state
from config.filter_c_config import FilterCConfig
from config.engulfing_config import EngulfingConfig

import MetaTrader5 as mt5

def backfill_all():
    if not mt5.initialize():
        print("❌ Gagal terhubung ke MT5!")
        return
    print("✅ MT5 terhubung.")
    
    supabase = get_supabase()
    fc_cfg = FilterCConfig()
    eng_cfg = EngulfingConfig()
    
    # Fetch all trades
    trades = []
    start = 0
    step = 1000
    while True:
        res = supabase.table("trade_analytics").select("*").range(start, start + step - 1).execute()
        chunk = res.data or []
        trades.extend(chunk)
        if len(chunk) < step:
            break
        start += step
        
    print(f"✅ Ditemukan {len(trades)} trades untuk diproses.")
    
    updated = 0
    for trade in trades:
        try:
            sym = trade.get("symbol")
            entry_time_str = trade.get("entry_time")
            ticket_id = trade.get("ticket_id")
            
            if not sym or not entry_time_str:
                continue
                
            notes_str = trade.get("notes") or "{}"
            if isinstance(notes_str, str):
                try:
                    notes = json.loads(notes_str)
                except:
                    notes = {}
            else:
                notes = dict(notes_str)
                
            # If it already has both fields, we can skip it, OR we can force recalculate.
            # We will force recalculate if h1_trigger_time is missing, or h1_ema_distance_pts is missing
            if "h1_ema_distance_pts" in notes and "h1_trigger_time" in notes:
                # Optionally skip to save time, but let's recalculate all to be clean if they don't have time
                pass

            dt = datetime.fromisoformat(entry_time_str.replace("Z", "+00:00"))
            h1_candles = fetch_historical_h1_candles(sym, dt, 250)
            
            if len(h1_candles) < 50:
                print(f"⚠️ Data historis H1 kurang untuk tiket {ticket_id}")
                continue
                
            point = _get_point(sym)
            h1_closes = [c["close"] for c in h1_candles]
            h1_ema = calculate_ema_series(h1_closes, 20)
            
            h1_res = find_latest_h1_state(h1_candles, point, h1_ema, fc_cfg)
            if not h1_res or h1_res.direction == 0:
                continue
                
            # Calc distance
            h1_time = h1_res.time
            if h1_time is None:
                continue
                
            try:
                idx = next(i for i, c in enumerate(h1_candles) if c["time"] == h1_time)
                h1_ema_val = h1_ema[idx]
                hc = h1_candles[idx]
            except StopIteration:
                continue
                
            dist_raw = abs(hc["open"] - h1_ema_val)
            dist_pts = round(dist_raw / point) if point > 0 else 0
            min_pts, max_pts = eng_cfg.get_ema_distance_limits(sym)
            
            status = "STRONG"
            if dist_pts < min_pts:
                status = "INVALID"
            elif dist_pts > max_pts:
                status = "VALID"
                
            notes["h1_ema_distance_pts"] = dist_pts
            notes["h1_ema_distance_status"] = status
            notes["h1_ema_distance_min"] = min_pts
            notes["h1_ema_distance_max"] = max_pts
            notes["h1_trigger_source"] = h1_res.source
            
            # FORMAT WAKTU: HH:MM
            if hasattr(h1_time, "strftime"):
                time_str = h1_time.strftime("%H:%M")
            else:
                time_str = datetime.fromtimestamp(h1_time, tz=timezone.utc).strftime("%H:%M")
            notes["h1_trigger_time"] = time_str
            
            supabase.table("trade_analytics").update({"notes": notes}).eq("id", trade["id"]).execute()
            updated += 1
            print(f"✅ Updated tiket {ticket_id}: {dist_pts} pts, Time: {time_str}")
            
        except Exception as e:
            print(f"❌ Gagal proses trade {trade.get('id')}: {e}")
            
    print(f"🎉 SUKSES! Berhasil meng-update {updated} trade dengan EMA Distance H1 dan Jam Trigger-nya!")

if __name__ == "__main__":
    backfill_all()
