import sys
import os
from datetime import datetime, timezone, timedelta

# Add root folder to path so database module is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import get_supabase
from strategies.engulfing.signal_builder import get_trading_session_wib

def get_broker_timezone_offset(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    year = dt_utc.year
    w_march31 = datetime(year, 3, 31, tzinfo=timezone.utc).weekday()
    last_sun_march = datetime(year, 3, 31 - (w_march31 + 1) % 7, 1, 0, tzinfo=timezone.utc)
    w_oct31 = datetime(year, 10, 31, tzinfo=timezone.utc).weekday()
    last_sun_oct = datetime(year, 10, 31 - (w_oct31 + 1) % 7, 1, 0, tzinfo=timezone.utc)
    if last_sun_march <= dt_utc < last_sun_oct:
        return 3
    return 2

def parse_iso(dt_str: str) -> datetime:
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    return datetime.fromisoformat(dt_str)

def backfill():
    supabase = get_supabase()
    
    # 1. Backfill candles (correct timestamp timezone offset)
    print("Correcting and backfilling candles table timestamps...")
    res = supabase.table("candles").select("id, timestamp, created_at").execute()
    if res.data:
        print(f"Found {len(res.data)} rows in candles to process.")
        updated_count = 0
        deleted_count = 0
        for row in res.data:
            if not isinstance(row, dict): continue
            ts = parse_iso(str(row["timestamp"]))
            created_at = parse_iso(str(row["created_at"]))
            diff = ts - created_at
            if diff > timedelta(minutes=10):
                offset = get_broker_timezone_offset(created_at)
                correct_ts = ts - timedelta(hours=offset)
                try:
                    supabase.table("candles").update({"timestamp": correct_ts.isoformat()}).eq("id", row["id"]).execute()
                    updated_count += 1
                except Exception as e:
                    err_msg = str(e)
                    if "23505" in err_msg or "duplicate key" in err_msg:
                        print(f"Duplicate candle detected for ID {row['id']}. Deleting duplicate...")
                        supabase.table("candles").delete().eq("id", row["id"]).execute()
                        deleted_count += 1
                    else:
                        raise e
        print(f"Corrected {updated_count} rows, deleted {deleted_count} duplicate rows in candles.")
    else:
        print("No candles rows found.")
        
    # 2. Backfill engulfing_signals (correct signal_time and update session)
    print("Correcting and backfilling engulfing_signals...")
    res = supabase.table("engulfing_signals").select("id, signal_time, created_at").execute()
    if res.data:
        print(f"Found {len(res.data)} rows in engulfing_signals to process.")
        corrected_count = 0
        deleted_count = 0
        for row in res.data:
            if not isinstance(row, dict): continue
            sig_time = parse_iso(str(row["signal_time"]))
            created_at = parse_iso(str(row["created_at"]))
            diff = sig_time - created_at
            
            # If stored signal_time is naive-converted broker time, it will be ahead of created_at
            is_deleted = False
            if diff > timedelta(minutes=10):
                offset = get_broker_timezone_offset(created_at)
                correct_sig_time = sig_time - timedelta(hours=offset)
                try:
                    supabase.table("engulfing_signals").update({"signal_time": correct_sig_time.isoformat()}).eq("id", row["id"]).execute()
                    corrected_count += 1
                    sig_time = correct_sig_time
                except Exception as e:
                    err_msg = str(e)
                    if "23505" in err_msg or "duplicate key" in err_msg:
                        print(f"Duplicate signal detected for ID {row['id']}. Deleting duplicate...")
                        supabase.table("engulfing_signals").delete().eq("id", row["id"]).execute()
                        deleted_count += 1
                        is_deleted = True
                    else:
                        raise e
            
            if not is_deleted:
                # Recalculate session based on correct signal_time
                session = get_trading_session_wib(sig_time)
                supabase.table("engulfing_signals").update({"trading_session": session}).eq("id", row["id"]).execute()
        print(f"Corrected {corrected_count} timestamps, deleted {deleted_count} duplicate rows, and updated all sessions in engulfing_signals.")
    else:
        print("No engulfing_signals rows found.")
        
    # 3. Backfill trade_analytics (update sessions based on created_at / entry_time)
    print("Backfilling trade_analytics sessions...")
    res = supabase.table("trade_analytics").select("id, created_at").execute()
    if res.data:
        print(f"Found {len(res.data)} rows in trade_analytics.")
        for row in res.data:
            if not isinstance(row, dict): continue
            dt = parse_iso(str(row["created_at"]))
            session = get_trading_session_wib(dt)
            supabase.table("trade_analytics").update({"trading_session": session}).eq("id", row["id"]).execute()
        print("Finished updating sessions in trade_analytics.")
    else:
        print("No rows in trade_analytics.")
            
    # 4. Backfill trade_active_logs (update sessions based on created_at)
    print("Backfilling trade_active_logs sessions...")
    res = supabase.table("trade_active_logs").select("id, created_at").execute()
    if res.data:
        print(f"Found {len(res.data)} rows in trade_active_logs.")
        for row in res.data:
            if not isinstance(row, dict): continue
            dt = parse_iso(str(row["created_at"]))
            session = get_trading_session_wib(dt)
            supabase.table("trade_active_logs").update({"trading_session": session}).eq("id", row["id"]).execute()
        print("Finished updating sessions in trade_active_logs.")
    else:
        print("No rows in trade_active_logs.")

    print("Backfill completed successfully!")

if __name__ == "__main__":
    backfill()
