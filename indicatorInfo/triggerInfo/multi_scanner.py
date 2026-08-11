import os
import sys
import time
import json
import requests
import traceback
from datetime import datetime, timezone
import MetaTrader5 as mt5

# Add root directory to sys.path so it can find config, mt5_client, utils, etc.
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config.mt5_config import MT5Config
from mt5_client import init_mt5, shutdown_mt5
from utils.colors import cprint, Colors
from database.supabase_client import get_supabase

# =========================================================
# Pattern Detectors
# =========================================================

def detect_engulfing(candle_data: dict, point: float) -> str:
    c1_close, c1_open = candle_data["close_"], candle_data["open_"]
    c1_high, c1_low = candle_data["high_"], candle_data["low_"]
    c2_close, c2_open = candle_data["c2_close"], candle_data["c2_open"]
    c2_high, c2_low = candle_data["c2_high"], candle_data["c2_low"]

    c2_is_bear = c2_close < c2_open
    c2_is_bull = c2_close > c2_open
    c1_is_bull = c1_close > c1_open
    c1_is_bear = c1_close < c1_open

    if c2_is_bear and c1_is_bull and c1_close >= c2_high:
        return "BUY"
    if c2_is_bull and c1_is_bear and c1_close <= c2_low:
        return "SELL"
    return ""

def detect_marubozu(candle_data: dict, point: float, min_body_pct=90.0) -> str:
    # Requires candle_data to have body_pct
    if "body_pct" in candle_data and candle_data["body_pct"] >= min_body_pct:
        c1_close, c1_open = candle_data["close_"], candle_data["open_"]
        c1_high, c1_low = candle_data["high_"], candle_data["low_"]
        
        # Additional logic: check if riskRange > avgRange * 1.5
        # Since we only have basic candle data here, we do a simplistic version or 
        # assume it is handled before calling this if full history is available.
        # For this scanner, we just check body% and direction.
        if c1_close > c1_open: return "BUY"
        if c1_close < c1_open: return "SELL"
    return ""

def detect_same_candle(candles: list, min_streak=3) -> str:
    """Detects continuous same-colored candles. Requires a list of recent candles (latest first)."""
    if len(candles) < min_streak: return ""
    c1 = candles[0]
    c1_is_bull = c1['close'] > c1['open']
    c1_is_bear = c1['close'] < c1['open']
    if not c1_is_bull and not c1_is_bear: return "" # Doji
    
    streak = 0
    for c in candles:
        is_bull = c['close'] > c['open']
        is_bear = c['close'] < c['open']
        if (c1_is_bull and is_bull) or (c1_is_bear and is_bear):
            streak += 1
        else:
            break
            
    if streak >= min_streak:
        return f"BUY_{streak}" if c1_is_bull else f"SELL_{streak}"
    return ""

# =========================================================
# Scanner Engine
# =========================================================

class MultiPatternScanner:
    def __init__(self, symbols, timeframes, webhook_url=None):
        self.symbols = symbols
        self.timeframes = timeframes
        self.webhook_url = webhook_url or "http://localhost:3000/api/webhook/indicator"
        self.supabase = get_supabase()
        
        # Deduplication cache: {symbol_tf: {timestamp: [patterns]}}
        self.seen_triggers = {}
        
    def _tf_to_mt5(self, tf_str):
        mapping = {
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        return mapping.get(tf_str, mt5.TIMEFRAME_M5)

    def scan_symbol_tf(self, symbol, tf_str):
        tf_mt5 = self._tf_to_mt5(tf_str)
        # Ambil 10 candle terakhir
        rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 1, 10)
        if rates is None or len(rates) < 10:
            return

        # Prepare candle data for latest closed candle (index 8, since 9 is the oldest in array if ordered by time asc)
        # Actually mt5 returns ordered from oldest to newest. index -1 is the most recent closed (since we shifted by 1).
        c1 = rates[-1]
        c2 = rates[-2]
        
        c_time = datetime.fromtimestamp(c1['time'], timezone.utc)
        cache_key = f"{symbol}_{tf_str}_{c1['time']}"
        
        if cache_key not in self.seen_triggers:
            self.seen_triggers[cache_key] = []
            
        triggers_found = []
        point = mt5.symbol_info(symbol).point
        
        # Prepare data struct for engulfing
        c1_range = c1['high'] - c1['low']
        body = abs(c1['close'] - c1['open'])
        body_pct = (body / c1_range * 100) if c1_range > 0 else 0
        
        candle_data = {
            "close_": c1['close'], "open_": c1['open'], "high_": c1['high'], "low_": c1['low'],
            "c2_close": c2['close'], "c2_open": c2['open'], "c2_high": c2['high'], "c2_low": c2['low'],
            "body_pct": body_pct
        }
        
        # 1. Check Engulfing
        eng_dir = detect_engulfing(candle_data, point)
        if eng_dir and "Engulfing" not in self.seen_triggers[cache_key]:
            triggers_found.append(("Engulfing", eng_dir, {"body_pct": body_pct}))
            self.seen_triggers[cache_key].append("Engulfing")
            
        # 2. Check Marubozu
        mar_dir = detect_marubozu(candle_data, point)
        if mar_dir and "Marubozu" not in self.seen_triggers[cache_key]:
            triggers_found.append(("Marubozu", mar_dir, {"body_pct": body_pct}))
            self.seen_triggers[cache_key].append("Marubozu")
            
        # 3. Check Same Candle
        reversed_rates = list(reversed(rates))
        sc_res = detect_same_candle(reversed_rates)
        if sc_res and "SameCandle" not in self.seen_triggers[cache_key]:
            direction = "BUY" if "BUY" in sc_res else "SELL"
            streak = int(sc_res.split("_")[1])
            triggers_found.append(("SameCandle", direction, {"streak": streak}))
            self.seen_triggers[cache_key].append("SameCandle")

        # Push to Supabase and Webhook
        for pattern_name, direction, details in triggers_found:
            print(cprint(f"📡 [SCANNER] {symbol} {tf_str} -> {pattern_name} {direction}", Colors.CYAN))
            
            # Save to Supabase
            if self.supabase:
                try:
                    self.supabase.table("indicator_triggers").insert({
                        "symbol": symbol,
                        "timeframe": tf_str,
                        "pattern_name": pattern_name,
                        "direction": direction,
                        "trigger_time": c_time.isoformat(),
                        "details": details
                    }).execute()
                except Exception as e:
                    print(cprint(f"⚠️ Supabase Insert Error: {e}", Colors.YELLOW))
                    
            # Send Webhook
            payload = {
                "type": "INDICATOR_TRIGGER",
                "symbol": symbol,
                "timeframe": tf_str,
                "pattern": pattern_name,
                "direction": direction,
                "details": details,
                "timestamp": c_time.isoformat()
            }
            try:
                requests.post(self.webhook_url, json=payload, timeout=3)
            except Exception as e:
                pass # Silently ignore webhook failure

    def run_forever(self):
        print(cprint("🚀 MultiPatternScanner berjalan...", Colors.GREEN))
        while True:
            for sym in self.symbols:
                for tf in self.timeframes:
                    try:
                        self.scan_symbol_tf(sym, tf)
                    except Exception as e:
                        traceback.print_exc()
            
            # Clean up old seen keys to prevent memory leak
            current_time = time.time()
            keys_to_del = []
            for k in self.seen_triggers.keys():
                # Extract timestamp from key: symbol_tf_timestamp
                ts = int(k.split("_")[-1])
                if current_time - ts > 86400 * 2: # Older than 2 days
                    keys_to_del.append(k)
            for k in keys_to_del:
                del self.seen_triggers[k]
                
            time.sleep(5) # Fast scan interval (5 seconds)

if __name__ == "__main__":
    if not init_mt5():
        print("Gagal init MT5.")
        exit(1)
        
    scanner = MultiPatternScanner(
        symbols=["XAUUSD", "NASDAQ-100", "BTC"],
        timeframes=["M5", "M15", "M30", "H1", "H4", "D1"]
    )
    
    try:
        scanner.run_forever()
    except KeyboardInterrupt:
        print("Scanner dihentikan.")
    finally:
        shutdown_mt5()
