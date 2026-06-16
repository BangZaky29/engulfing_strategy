import sys
import os
from datetime import datetime, timezone, timedelta

# Add root folder to path so database module is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import get_supabase

def get_trading_session_wib(dt: datetime) -> str:
    # Convert dt to WIB timezone (UTC+7)
    wib_tz = timezone(timedelta(hours=7))
    dt_wib = dt.astimezone(wib_tz)
    hour = dt_wib.hour
    
    sessions = []
    if 7 <= hour < 16:
        sessions.append("Asia")
    if 14 <= hour < 23:
        sessions.append("Euro")
    if 19 <= hour <= 23 or 0 <= hour < 4:
        sessions.append("NY")
        
    return "/".join(sessions) if sessions else "Off-Market"

def parse_iso(dt_str: str) -> datetime:
    # Handle standard ISO formats with timezone offsets or 'Z' suffix
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    return datetime.fromisoformat(dt_str)

def backfill():
    supabase = get_supabase()
    
    # 1. Backfill trade_analytics
    print("Backfilling trade_analytics...")
    res = supabase.table("trade_analytics").select("id, created_at").or_("trading_session.is.null,trading_session.eq.Unknown").execute()
    if res.data:
        print(f"Found {len(res.data)} rows in trade_analytics to backfill.")
        for row in res.data:
            dt = parse_iso(row["created_at"])
            session = get_trading_session_wib(dt)
            supabase.table("trade_analytics").update({"trading_session": session}).eq("id", row["id"]).execute()
    else:
        print("No rows to update in trade_analytics.")
            
    # 2. Backfill engulfing_signals
    print("Backfilling engulfing_signals...")
    res = supabase.table("engulfing_signals").select("id, created_at").or_("trading_session.is.null,trading_session.eq.Unknown").execute()
    if res.data:
        print(f"Found {len(res.data)} rows in engulfing_signals to backfill.")
        for row in res.data:
            dt = parse_iso(row["created_at"])
            session = get_trading_session_wib(dt)
            supabase.table("engulfing_signals").update({"trading_session": session}).eq("id", row["id"]).execute()
    else:
        print("No rows to update in engulfing_signals.")
            
    # 3. Backfill trade_active_logs
    print("Backfilling trade_active_logs...")
    res = supabase.table("trade_active_logs").select("id, created_at").or_("trading_session.is.null,trading_session.eq.Unknown").execute()
    if res.data:
        print(f"Found {len(res.data)} rows in trade_active_logs to backfill.")
        for row in res.data:
            dt = parse_iso(row["created_at"])
            session = get_trading_session_wib(dt)
            supabase.table("trade_active_logs").update({"trading_session": session}).eq("id", row["id"]).execute()
    else:
        print("No rows to update in trade_active_logs.")

    print("Backfill completed successfully!")

if __name__ == "__main__":
    backfill()
