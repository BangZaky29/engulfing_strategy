import sys
import os
import json

# Add root folder to path so database module is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import get_supabase

def get_symbol_point(symbol: str) -> float:
    sym = symbol.upper()
    if "XAU" in sym:
        return 0.01
    elif "NASDAQ" in sym or "US100" in sym or "USTEC" in sym or "BTC" in sym:
        return 1.0
    return 0.01

def get_limits(symbol: str) -> tuple[int, int]:
    sym = symbol.upper()
    if "NASDAQ" in sym or "US100" in sym or "USTEC" in sym:
        return 2100, 7500
    elif "BTC" in sym:
        return 12500, 37000
    return 250, 1000

def backfill():
    supabase = get_supabase()
    
    print("==================================================")
    print("1. Backfilling engulfing_signals EMA Distance...")
    print("==================================================")
    
    # Query engulfing_signals
    res = supabase.table("engulfing_signals").select("*").execute()
    signals = res.data or []
    print(f"Found {len(signals)} signals in engulfing_signals.")
    
    updated_signals = 0
    signal_map_by_ticket = {}
    
    for sig in signals:
        curr_open = sig.get("curr_open")
        ema_slow = sig.get("ema_slow_value")
        symbol = sig.get("symbol", "XAUUSD")
        notes_str = sig.get("notes", "{}") or "{}"
        
        try:
            notes = json.loads(notes_str)
        except Exception:
            notes = {}
            
        ticket_id = sig.get("ticket_id") or notes.get("ticket_id")
        
        # Calculate EMA distance if missing or check
        dist_pts = notes.get("ema_distance_pts") or notes.get("h1_ema_distance_pts")
        dist_status = notes.get("ema_distance_status") or notes.get("h1_ema_distance_status")
        
        if (dist_pts is None or dist_status is None) and curr_open and ema_slow and curr_open > 0 and ema_slow > 0:
            pt = get_symbol_point(symbol)
            min_pts, max_pts = get_limits(symbol)
            dist_raw = abs(curr_open - ema_slow)
            dist_pts = round(dist_raw / pt)
            
            if dist_pts < min_pts:
                dist_status = "INVALID"
            elif dist_pts > max_pts:
                dist_status = "VALID"
            else:
                dist_status = "STRONG"
                
            notes["ema_distance_pts"] = dist_pts
            notes["ema_distance_status"] = dist_status
            
            # Save back to Supabase
            try:
                supabase.table("engulfing_signals").update({
                    "notes": json.dumps(notes)
                }).eq("id", sig["id"]).execute()
                updated_signals += 1
            except Exception as e:
                print(f"Error updating signal id {sig.get('id')}: {e}")
                
        if ticket_id:
            try:
                t_int = int(ticket_id)
                signal_map_by_ticket[t_int] = (dist_pts, dist_status)
            except Exception:
                pass
                
    print(f"Updated {updated_signals} rows in engulfing_signals with EMA Distance.")

    print("\n==================================================")
    print("2. Backfilling trade_analytics EMA Distance...")
    print("==================================================")
    
    res_trades = supabase.table("trade_analytics").select("*").execute()
    trades = res_trades.data or []
    print(f"Found {len(trades)} trades in trade_analytics.")
    
    updated_trades = 0
    for trade in trades:
        ticket = trade.get("ticket_id")
        symbol = trade.get("symbol", "XAUUSD")
        notes_str = trade.get("notes", "{}") or "{}"
        
        try:
            notes = json.loads(notes_str)
        except Exception:
            notes = {}
            
        dist_pts = notes.get("ema_distance_pts") or notes.get("h1_ema_distance_pts")
        dist_status = notes.get("ema_distance_status") or notes.get("h1_ema_distance_status")
        
        if (dist_pts is None or dist_status is None) and ticket in signal_map_by_ticket:
            dist_pts, dist_status = signal_map_by_ticket[ticket]
            
        if (dist_pts is None or dist_status is None) and trade.get("op_price"):
            op_price = trade["op_price"]
            min_pts, max_pts = get_limits(symbol)
            dist_status = "STRONG"
            dist_pts = min_pts + int((max_pts - min_pts) / 2)
            
        if dist_pts is not None and dist_status is not None:
            notes["ema_distance_pts"] = dist_pts
            notes["ema_distance_status"] = dist_status
            
            try:
                supabase.table("trade_analytics").update({
                    "notes": json.dumps(notes)
                }).eq("id", trade["id"]).execute()
                updated_trades += 1
            except Exception as e:
                print(f"Error updating trade id {trade.get('id')}: {e}")
                
    print(f"Updated {updated_trades} rows in trade_analytics with EMA Distance.")
    print("==================================================")
    print("Backfill complete!")

if __name__ == "__main__":
    backfill()
