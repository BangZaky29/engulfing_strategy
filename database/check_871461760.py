import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.supabase_client import get_supabase

def check():
    sb = get_supabase()
    res = sb.table('trade_analytics').select('*').eq('ticket_id', 871461760).execute()
    print("TRADE ANALYTICS FOR 871461760:")
    print(json.dumps(res.data, indent=2))

    res_sig = sb.table('engulfing_signals').select('*').eq('ticket_id', 871461760).execute()
    print("\nENGULFING SIGNALS FOR 871461760:")
    print(json.dumps(res_sig.data, indent=2))

if __name__ == "__main__":
    check()
