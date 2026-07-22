import sys
import os
import json
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
from database.supabase_client import get_supabase
from config.engulfing_config import EngulfingConfig
from config.filter_c_config import FilterCConfig
from strategies.engulfing.filters_C import _get_point
from strategies.engulfing.filters_C.f3_ema_utils import calculate_ema_series
from strategies.engulfing.filters_C.f2_bias_logic import find_latest_h1_state

def fetch_historical_h1_candles(symbol: str, dt: datetime, count: int) -> list[dict]:
    # Ensure dt is timezone aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
        
    rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H1, dt, count)
    if rates is None or len(rates) == 0:
        return []
        
    candles = []
    for r in rates:
        candles.append({
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "time": datetime.fromtimestamp(r["time"], tz=timezone.utc),
        })
    return candles

def backfill_historical():
    if not mt5.initialize():
        print("❌ MT5 init failed")
        return
        
    print("✅ MT5 terhubung.")
    
    supabase = get_supabase()
    cfg = EngulfingConfig()
    fc_cfg = FilterCConfig()
    
    print("Memulai backfill historical data (menarik data dari MT5)...")
    
    # Fetch ALL signals using pagination
    signals = []
    start = 0
    step = 1000
    while True:
        res = supabase.table("engulfing_signals").select("*").range(start, start + step - 1).execute()
        chunk = res.data or []
        signals.extend(chunk)
        if len(chunk) < step:
            break
        start += step
        
    print(f"Ditemukan total {len(signals)} sinyal di database.")
    
    updated_signals = 0
    signal_map = {}
    
    for sig in signals:
        notes_str = sig.get("notes") or {}
        if isinstance(notes_str, str):
            try:
                notes = json.loads(notes_str)
            except:
                notes = {}
        else:
            notes = dict(notes_str)
            
        # Jika sudah ada data H1, skip
        if "h1_ema_distance_pts" in notes:
            continue
            
        sym = sig.get("symbol")
        created_at = sig.get("created_at")
        ticket_id = sig.get("ticket_id") or notes.get("ticket_id")
        
        if not sym or not created_at:
            continue
            
        try:
            # Parse datetime
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            
            # Ambil 250 candle H1 ke belakang dari waktu eksekusi sinyal tersebut
            h1_candles = fetch_historical_h1_candles(sym, dt, 250)
            
            if len(h1_candles) < 50:
                print(f"Warning: Data H1 kurang untuk {sym} pada {dt}")
                continue
                
            point = _get_point(sym)
            h1_closes = [c["close"] for c in h1_candles]
            h1_ema = calculate_ema_series(h1_closes, 20)
            
            # Cari state H1
            h1_res = find_latest_h1_state(h1_candles, point, h1_ema, fc_cfg)
            if not h1_res or h1_res.direction == 0:
                continue
                
            h1_time = h1_res.time
            
            if h1_time:
                # Find the index of the h1_time candle in the candles list to get its EMA and Open
                try:
                    idx = next(i for i, c in enumerate(h1_candles) if c["time"] == h1_time)
                    h1_ema_val = h1_ema[idx]
                    hc = h1_candles[idx]
                except StopIteration:
                    continue
                    
                dist_raw = abs(hc["open"] - h1_ema_val)
                dist_pts = round(dist_raw / point) if point > 0 else 0
                min_pts, max_pts = cfg.get_ema_distance_limits(sym)
                
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

                
                # Update ke database
                supabase.table("engulfing_signals").update({"notes": notes}).eq("id", sig["id"]).execute()
                updated_signals += 1
                
                if ticket_id:
                    try:
                        signal_map[int(ticket_id)] = (dist_pts, status, min_pts, max_pts)
                    except:
                        pass
        except Exception as e:
            print(f"Error memproses sinyal ID {sig['id']}: {e}")
            
    print(f"✅ Selesai update {updated_signals} sinyal di engulfing_signals.")
    
    # Fetch ALL trade analytics using pagination
    trades = []
    start = 0
    while True:
        res_trades = supabase.table("trade_analytics").select("*").range(start, start + step - 1).execute()
        chunk = res_trades.data or []
        trades.extend(chunk)
        if len(chunk) < step:
            break
        start += step
        
    print(f"Ditemukan total {len(trades)} trade di database.")
    updated_trades = 0
    
    for trade in trades:
        notes_str = trade.get("notes") or {}
        if isinstance(notes_str, str):
            try:
                notes = json.loads(notes_str)
            except:
                notes = {}
        else:
            notes = dict(notes_str)
            
        if "h1_ema_distance_pts" in notes:
            continue
            
        ticket_id = trade.get("ticket_id") or notes.get("ticket_id")
        if ticket_id:
            try:
                tid = int(ticket_id)
                if tid in signal_map:
                    dist_pts, status, min_pts, max_pts = signal_map[tid]
                    notes["h1_ema_distance_pts"] = dist_pts
                    notes["h1_ema_distance_status"] = status
                    notes["h1_ema_distance_min"] = min_pts
                    notes["h1_ema_distance_max"] = max_pts
                    
                    supabase.table("trade_analytics").update({"notes": notes}).eq("id", trade["id"]).execute()
                    updated_trades += 1
            except Exception as e:
                pass
                
    print(f"✅ Selesai update {updated_trades} data di trade_analytics.")

if __name__ == "__main__":
    backfill_historical()
