import os
import sys
import time
import json
import traceback
from datetime import datetime, timezone
import MetaTrader5 as mt5
from dotenv import load_dotenv

# Add root directory to sys.path so it can find config, mt5_client, utils, etc.
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config.mt5_config import MT5Config
from mt5_client import init_mt5, shutdown_mt5
from utils.colors import cprint, Colors
from database.supabase_client import get_supabase, execute_supabase
import uuid

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
    if "body_pct" in candle_data and candle_data["body_pct"] >= min_body_pct:
        c1_close, c1_open = candle_data["close_"], candle_data["open_"]
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
    def __init__(self, symbols, timeframes):
        self.symbols = symbols
        self.timeframes = timeframes
        self.supabase = get_supabase()
        self.group_jid = os.getenv("SCANNER_GROUP_JID", "120363410782502082@g.us")
        
        # Deduplication cache: {cache_key: [pattern_names]}
        self.seen_triggers = {}
        
        # Active triggers state: trigger tetap aktif sampai candle berganti DAN pattern hilang
        # Key: f"{symbol}_{tf}" → Value: (symbol, tf, pattern_name, direction, details, candle_timestamp)
        self.active_triggers = {}
        
        # Track candle timestamp terakhir per symbol+tf untuk deteksi pergantian candle
        # Key: f"{symbol}_{tf}" → Value: candle_timestamp (int)
        self.last_candle_time = {}
        
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
            return []

        c1 = rates[-1]
        c2 = rates[-2]
        
        c_time = datetime.fromtimestamp(c1['time'], timezone.utc)
        candle_ts = int(c1['time'])
        cache_key = f"{symbol}_{tf_str}_{candle_ts}"
        active_key = f"{symbol}_{tf_str}"
        
        if cache_key not in self.seen_triggers:
            self.seen_triggers[cache_key] = []
        
        # Deteksi apakah candle sudah berganti dibanding siklus sebelumnya
        prev_candle_ts = self.last_candle_time.get(active_key)
        candle_changed = (prev_candle_ts is not None and candle_ts != prev_candle_ts)
        self.last_candle_time[active_key] = candle_ts
            
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
            triggers_found.append(("Engulfing", eng_dir, {"body_pct": round(body_pct, 1)}))
            self.seen_triggers[cache_key].append("Engulfing")
            
        # 2. Check Marubozu
        mar_dir = detect_marubozu(candle_data, point)
        if mar_dir and "Marubozu" not in self.seen_triggers[cache_key]:
            triggers_found.append(("Marubozu", mar_dir, {"body_pct": round(body_pct, 1)}))
            self.seen_triggers[cache_key].append("Marubozu")
            
        # 3. Check Same Candle
        reversed_rates = list(reversed(rates))
        sc_res = detect_same_candle(reversed_rates)
        if sc_res and "SameCandle" not in self.seen_triggers[cache_key]:
            direction = "BUY" if "BUY" in sc_res else "SELL"
            streak = int(sc_res.split("_")[1])
            triggers_found.append(("SameCandle", direction, {"streak": streak}))
            self.seen_triggers[cache_key].append("SameCandle")

        # Print ke terminal & simpan ke Supabase
        for pattern_name, direction, details in triggers_found:
            print(cprint(f"📡 [SCANNER] {symbol} {tf_str} -> {pattern_name} {direction}", Colors.CYAN))
            
            # Save to Supabase indicator_triggers table
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

        # =========================================================
        # Update active_triggers state
        # =========================================================
        if triggers_found:
            # Ada trigger baru → update active_triggers dengan trigger terbaru
            # Simpan semua pattern yang aktif di symbol+tf ini
            for pattern_name, direction, details in triggers_found:
                at_key = f"{active_key}_{pattern_name}"
                self.active_triggers[at_key] = (symbol, tf_str, pattern_name, direction, details, candle_ts)
        elif candle_changed:
            # Candle sudah berganti tapi TIDAK ada trigger baru → hapus & catat sebagai expired
            keys_to_remove = [k for k in self.active_triggers if k.startswith(f"{active_key}_")]
            for k in keys_to_remove:
                expired_data = self.active_triggers[k]
                self.expired_this_cycle.append(expired_data)  # (symbol, tf, pattern, dir, details, ts)
                del self.active_triggers[k]
                print(cprint(f"🔕 [EXPIRED] {expired_data[0]} {expired_data[1]} → {expired_data[2]} {expired_data[3]} (candle berganti)", Colors.YELLOW))
        # Jika candle belum berganti dan tidak ada trigger baru → active_triggers tetap (carry over)

        return triggers_found

    def _format_summary_message(self, all_triggers: list, expired_triggers: list = None) -> str:
        """Gabungkan semua trigger (baru + aktif + expired) menjadi 1 pesan ringkasan WA.
        
        all_triggers format: (symbol, tf_str, pattern_name, direction, details, status)
        status: "new" = trigger baru, "active" = carry over
        expired_triggers format: (symbol, tf_str, pattern_name, direction, details, candle_ts)
        """
        if not all_triggers and not expired_triggers:
            return ""

        # Definisi urutan timeframe untuk sorting
        tf_order = {"M1": 0, "M5": 1, "M15": 2, "M30": 3, "H1": 4, "H4": 5, "D1": 6, "W1": 7, "MN": 8}

        # Group by symbol: trigger aktif
        by_symbol = {}
        for symbol, tf_str, pattern_name, direction, details, status in (all_triggers or []):
            if symbol not in by_symbol:
                by_symbol[symbol] = {"triggers": [], "expired": []}
            
            emoji = "🟢" if direction == "BUY" else "🔴"
            status_icon = "🆕" if status == "new" else "🔄"
            detail_str = ""
            if details.get("streak"):
                detail_str = f" ({details['streak']}x)"
            elif details.get("body_pct"):
                detail_str = f" ({details['body_pct']}%)"
            
            by_symbol[symbol]["triggers"].append({
                "line": f"  {emoji} {tf_str} → {pattern_name} {direction}{detail_str} {status_icon}",
                "tf_order": tf_order.get(tf_str, 99)
            })
        
        # Group expired by symbol
        for symbol, tf_str, pattern_name, direction, details, candle_ts in (expired_triggers or []):
            if symbol not in by_symbol:
                by_symbol[symbol] = {"triggers": [], "expired": []}
            
            dir_emoji = "BUY" if direction == "BUY" else "SELL"
            by_symbol[symbol]["expired"].append({
                "line": f"  🔕 {tf_str} → {pattern_name} {dir_emoji} _expired_",
                "tf_order": tf_order.get(tf_str, 99)
            })

        lines = ["📡 *MULTI-PATTERN SCANNER* 📡", "━━━━━━━━━━━━━━━━━"]
        for symbol, data in by_symbol.items():
            lines.append(f"📌 *{symbol}*")
            # Sort & append active triggers
            data["triggers"].sort(key=lambda x: x["tf_order"])
            for entry in data["triggers"]:
                lines.append(entry["line"])
            # Sort & append expired triggers
            if data["expired"]:
                data["expired"].sort(key=lambda x: x["tf_order"])
                for entry in data["expired"]:
                    lines.append(entry["line"])
            lines.append("")
        
        lines.append("━━━━━━━━━━━━━━━━━")
        lines.append("🆕 _Baru_ │ 🔄 _Aktif_ │ 🔕 _Expired_")
        lines.append(f"⏰ {datetime.now().strftime('%H:%M:%S WIB')}")
        lines.append("_Tanya Bro Ai untuk analisa lebih lanjut._")
        
        return "\n".join(lines)

    def _send_wa_summary(self, all_triggers: list, expired_triggers: list = None):
        """Kirim ringkasan trigger ke WA Group melalui wa_outbox.
        
        all_triggers: (symbol, tf, pattern_name, direction, details, status)
        expired_triggers: (symbol, tf, pattern_name, direction, details, candle_ts)
        """
        if not all_triggers and not expired_triggers:
            return
        
        message = self._format_summary_message(all_triggers, expired_triggers)
        if not message:
            return

        # Hitung trigger per kategori untuk log
        new_count = sum(1 for t in (all_triggers or []) if t[5] == "new")
        active_count = sum(1 for t in (all_triggers or []) if t[5] == "active")
        expired_count = len(expired_triggers or [])

        payload = {
            'source_table': 'scanner_system',
            'event_type': 'SCANNER_TRIGGER',
            'group_jid': self.group_jid,
            'message_type': 'TEXT',
            'message': message,
            'dedupe_key': f'scanner_{int(time.time())}_{uuid.uuid4().hex[:8]}'
        }

        try:
            execute_supabase(lambda sb: sb.table('wa_outbox').insert(payload).execute())
            log_parts = []
            if new_count: log_parts.append(f"{new_count} baru")
            if active_count: log_parts.append(f"{active_count} aktif")
            if expired_count: log_parts.append(f"{expired_count} expired")
            print(cprint(f"📲 Scanner summary terkirim ke {self.group_jid} ({', '.join(log_parts)})", Colors.GREEN))
        except Exception as e:
            print(cprint(f"⚠️ Gagal kirim scanner summary ke WA: {e}", Colors.RED))

    def run_forever(self):
        print(cprint("🚀 MultiPatternScanner berjalan...", Colors.GREEN))
        while True:
            new_triggers_this_cycle = []
            self.expired_this_cycle = []  # Reset setiap siklus
            
            for sym in self.symbols:
                for tf in self.timeframes:
                    try:
                        triggers = self.scan_symbol_tf(sym, tf)
                        for pattern_name, direction, details in triggers:
                            new_triggers_this_cycle.append((sym, tf, pattern_name, direction, details))
                    except Exception as e:
                        traceback.print_exc()
            
            # Kirim pesan jika ada trigger BARU atau ada trigger EXPIRED
            has_new = len(new_triggers_this_cycle) > 0
            has_expired = len(self.expired_this_cycle) > 0
            
            if has_new or has_expired:
                # Bangun daftar gabungan: trigger baru (🆕) + trigger aktif lama (🔄)
                combined_triggers = []
                
                # 1. Tambahkan semua trigger BARU dengan status="new"
                new_keys = set()
                for sym, tf, pattern_name, direction, details in new_triggers_this_cycle:
                    combined_triggers.append((sym, tf, pattern_name, direction, details, "new"))
                    new_keys.add(f"{sym}_{tf}_{pattern_name}")
                
                # 2. Tambahkan trigger AKTIF (carry over) yang bukan dari siklus ini
                for at_key, (sym, tf, pattern_name, direction, details, candle_ts) in self.active_triggers.items():
                    trigger_id = f"{sym}_{tf}_{pattern_name}"
                    if trigger_id not in new_keys:
                        combined_triggers.append((sym, tf, pattern_name, direction, details, "active"))
                
                self._send_wa_summary(combined_triggers, self.expired_this_cycle if has_expired else None)
            
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
            
            # Clean up old active_triggers (candle timestamp > 2 hari)
            at_keys_to_del = []
            for k, (_, _, _, _, _, candle_ts) in self.active_triggers.items():
                if current_time - candle_ts > 86400 * 2:
                    at_keys_to_del.append(k)
            for k in at_keys_to_del:
                del self.active_triggers[k]
                
            time.sleep(5) # Fast scan interval (5 seconds)

if __name__ == "__main__":
    # Load .env file from root directory
    env_path = os.path.join(root_dir, ".env")
    load_dotenv(env_path)

    if not init_mt5():
        print("Gagal init MT5.")
        exit(1)
        
    # Read from .env, with fallbacks
    symbols_str = os.getenv("SCANNER_SYMBOLS", "XAUUSD,NASDAQ-100,BTC")
    timeframes_str = os.getenv("SCANNER_TIMEFRAMES", "M5,M15,M30,H1,H4,D1")
    
    symbols_list = [s.strip() for s in symbols_str.split(",") if s.strip()]
    timeframes_list = [t.strip() for t in timeframes_str.split(",") if t.strip()]
        
    scanner = MultiPatternScanner(
        symbols=symbols_list,
        timeframes=timeframes_list
    )
    
    try:
        scanner.run_forever()
    except KeyboardInterrupt:
        print("Scanner dihentikan.")
    finally:
        shutdown_mt5()
