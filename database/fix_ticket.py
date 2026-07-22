import os
import sys
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure paths are correct
sys.path.insert(0, os.getcwd())
load_dotenv()

from mt5_client.supabase_client import get_supabase
from database.backfill_h1_historical import fetch_historical_h1_candles, _get_point, calculate_ema_series, find_latest_h1_state
from config.filter_c_config import FilterCConfig

def fix_ticket():
    ticket_id = 869047289
    supabase = get_supabase()
    
    # 1. Fetch trade_analytics
    res = supabase.table("trade_analytics").select("*").eq("ticket_id", ticket_id).execute()
    if not res.data:
        print(f"❌ Tiket {ticket_id} tidak ditemukan di trade_analytics!")
        return
        
    trade = res.data[0]
    sym = trade.get("symbol")
    entry_time_str = trade.get("entry_time")
    
    print(f"✅ Ditemukan tiket {ticket_id} untuk symbol {sym} pada {entry_time_str}")
    
    if not sym or not entry_time_str:
        print("❌ Symbol atau entry_time kosong!")
        return
        
    # 2. Parse datetime
    dt = datetime.fromisoformat(entry_time_str.replace("Z", "+00:00"))
    
    # 3. Fetch candles from MT5
    fc_cfg = FilterCConfig()
    print("Meminta data H1 historis dari MT5...")
    h1_candles = fetch_historical_h1_candles(sym, dt, 250)
    
    if len(h1_candles) < 50:
        print("❌ Data H1 dari MT5 kurang (kurang dari 50 candle).")
        return
        
    # 4. Calculate EMA
    point = _get_point(sym)
    h1_closes = [c["close"] for c in h1_candles]
    h1_ema = calculate_ema_series(h1_closes, 20)
    
    # 5. Find H1 State (EMA Distance etc)
    h1_res = find_latest_h1_state(h1_candles, point, h1_ema, fc_cfg)
    
    if not h1_res or h1_res.direction == 0:
        print("❌ Tidak ditemukan valid trigger H1 historis pada jam tersebut!")
        return
        
    dist_pts = h1_res.ema_distance_pts
    status = h1_res.status
    
    # limits (min, max) from config
    # Assuming XAUUSD is 0 to 2000, NASDAQ is 0 to 7500, etc.
    from config.engulfing_config import EngulfingConfig
    eng_cfg = EngulfingConfig()
    min_pts, max_pts = eng_cfg.get_ema_distance_limits(sym)
    
    print(f"✅ H1 State Ditemukan! Jarak EMA: {dist_pts} pts | Status: {status}")
    
    # 6. Update Database
    notes_str = trade.get("notes") or "{}"
    if isinstance(notes_str, str):
        notes = json.loads(notes_str)
    else:
        notes = dict(notes_str)
        
    notes["h1_ema_distance_pts"] = dist_pts
    notes["h1_ema_distance_status"] = status
    notes["h1_ema_distance_min"] = min_pts
    notes["h1_ema_distance_max"] = max_pts
    
    supabase.table("trade_analytics").update({"notes": notes}).eq("id", trade["id"]).execute()
    print(f"🎉 SUKSES! Tiket {ticket_id} berhasil diupdate dengan EMA Distance: {dist_pts} pts ({status})")

if __name__ == "__main__":
    fix_ticket()
