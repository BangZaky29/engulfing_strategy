import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.supabase_client import get_supabase

def backfill():
    supabase = get_supabase()
    
    print("==================================================")
    print("1. Clearing fake M5 EMA Distances in engulfing_signals...")
    print("==================================================")
    
    res = supabase.table("engulfing_signals").select("*").execute()
    signals = res.data or []
    
    updated_signals = 0
    
    for sig in signals:
        notes_raw = sig.get("notes") or {}
        if isinstance(notes_raw, str):
            try:
                notes = json.loads(notes_raw)
            except Exception:
                notes = {}
        else:
            notes = dict(notes_raw)
            
        # We only want to keep ema_distance_pts if the signal itself is H1 (in which case it was calculated correctly by filter_ab_eval.py)
        # If the signal is M5 or M15, the ema_distance_pts might be fake (calculated by older script or fallback), so we delete it.
        # It should now be stored as h1_ema_distance_pts by the NEW code.
        
        needs_update = False
        if sig.get("timeframe") != "H1":
            keys_to_remove = ["ema_distance_pts", "ema_distance_status", "ema_distance_min", "ema_distance_max"]
            for k in keys_to_remove:
                if k in notes:
                    del notes[k]
                    needs_update = True
                    
        if needs_update:
            try:
                # Ensure it's a dict for Supabase update, supabase-py can handle dict for jsonb columns, but we can pass dict directly
                supabase.table("engulfing_signals").update({
                    "notes": notes
                }).eq("id", sig["id"]).execute()
                updated_signals += 1
            except Exception as e:
                print(f"Error updating signal id {sig.get('id')}: {e}")
                
    print(f"Cleared fake M5 EMA distances for {updated_signals} signals.")
    
    print("\n==================================================")
    print("2. Clearing fake M5 EMA Distances in trade_analytics...")
    print("==================================================")
    
    res_trades = supabase.table("trade_analytics").select("*").execute()
    trades = res_trades.data or []
    updated_trades = 0
    
    for trade in trades:
        notes_raw = trade.get("notes") or {}
        if isinstance(notes_raw, str):
            try:
                notes = json.loads(notes_raw)
            except Exception:
                notes = {}
        else:
            notes = dict(notes_raw)
            
        needs_update = False
        if trade.get("timeframe") != "H1":
            keys_to_remove = ["ema_distance_pts", "ema_distance_status", "ema_distance_min", "ema_distance_max"]
            for k in keys_to_remove:
                if k in notes:
                    del notes[k]
                    needs_update = True
                    
        if needs_update:
            try:
                supabase.table("trade_analytics").update({
                    "notes": notes
                }).eq("id", trade["id"]).execute()
                updated_trades += 1
            except Exception as e:
                pass
                
    print(f"Cleared fake M5 EMA distances for {updated_trades} trades.")
    print("==================================================")
    print("Backfill complete!")

if __name__ == "__main__":
    backfill()
