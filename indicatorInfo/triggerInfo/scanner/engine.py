"""
MultiPatternScanner Engine - scan loop utama dengan state management.

Responsibilities:
- Loop scan semua symbol × timeframe × pattern
- Manage active_triggers, seen_triggers, expired state
- Delegate notifikasi ke ScannerNotifier
"""

import os
import time
import traceback
from datetime import datetime, timezone

import MetaTrader5 as mt5

from utils.colors import cprint, Colors
from database.supabase_client import get_supabase

from .patterns import get_all_patterns
from .notifier import ScannerNotifier


class MultiPatternScanner:
    """Mesin scanner multi-pattern dengan active trigger tracking."""

    TF_MAPPING = {
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }

    def __init__(self, symbols: list, timeframes: list):
        self.symbols = symbols
        self.timeframes = timeframes
        self.supabase = get_supabase()
        self.patterns = get_all_patterns()

        # Notifier
        group_jid = os.getenv("SCANNER_GROUP_JID", "120363410782502082@g.us")
        self.notifier = ScannerNotifier(group_jid)

        # Deduplication: {f"{symbol}_{tf}_{candle_ts}": [pattern_names]}
        self.seen_triggers = {}

        # Active triggers: {f"{symbol}_{tf}_{pattern}": (symbol, tf, pattern, dir, details, candle_ts)}
        self.active_triggers = {}

        # Track candle timestamp terakhir: {f"{symbol}_{tf}": candle_ts}
        self.last_candle_time = {}

        # Expired dalam siklus ini (di-reset tiap siklus)
        self.expired_this_cycle = []

    def scan_symbol_tf(self, symbol: str, tf_str: str):
        """Scan 1 symbol pada 1 timeframe, jalankan semua pattern dari registry."""
        tf_mt5 = self.TF_MAPPING.get(tf_str, mt5.TIMEFRAME_M5)

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

        # Deteksi pergantian candle
        prev_candle_ts = self.last_candle_time.get(active_key)
        candle_changed = (prev_candle_ts is not None and candle_ts != prev_candle_ts)
        self.last_candle_time[active_key] = candle_ts

        # Prepare candle data struct
        c1_range = c1['high'] - c1['low']
        body = abs(c1['close'] - c1['open'])
        body_pct = (body / c1_range * 100) if c1_range > 0 else 0

        candle_data = {
            "close_": c1['close'], "open_": c1['open'], "high_": c1['high'], "low_": c1['low'],
            "c2_close": c2['close'], "c2_open": c2['open'], "c2_high": c2['high'], "c2_low": c2['low'],
            "body_pct": body_pct
        }

        point = mt5.symbol_info(symbol).point
        reversed_rates = list(reversed(rates))

        # === Run semua pattern dari registry ===
        triggers_found = []
        for pattern in self.patterns:
            if pattern.name in self.seen_triggers[cache_key]:
                continue  # Sudah terdeteksi di candle ini

            results = pattern.detect(candle_data, reversed_rates, point)
            for direction, details in results:
                triggers_found.append((pattern.name, direction, details))
                self.seen_triggers[cache_key].append(pattern.name)

        # Print ke terminal & simpan ke Supabase
        for pattern_name, direction, details in triggers_found:
            print(cprint(f"📡 [SCANNER] {symbol} {tf_str} -> {pattern_name} {direction}", Colors.CYAN))

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

        # === Update active_triggers state ===
        if triggers_found:
            for pattern_name, direction, details in triggers_found:
                at_key = f"{active_key}_{pattern_name}"
                self.active_triggers[at_key] = (symbol, tf_str, pattern_name, direction, details, candle_ts)
        elif candle_changed:
            # Candle berganti tanpa trigger baru → expired
            keys_to_remove = [k for k in self.active_triggers if k.startswith(f"{active_key}_")]
            for k in keys_to_remove:
                expired_data = self.active_triggers[k]
                self.expired_this_cycle.append(expired_data)
                del self.active_triggers[k]
                print(cprint(
                    f"🔕 [EXPIRED] {expired_data[0]} {expired_data[1]} → {expired_data[2]} {expired_data[3]} (candle berganti)",
                    Colors.YELLOW
                ))

        return triggers_found

    def run_forever(self):
        """Main scan loop - berjalan terus sampai di-stop."""
        # Log registered patterns
        pattern_names = [p.name for p in self.patterns]
        print(cprint(f"🚀 MultiPatternScanner berjalan... ({len(pattern_names)} patterns: {', '.join(pattern_names)})", Colors.GREEN))

        while True:
            new_triggers_this_cycle = []
            self.expired_this_cycle = []

            for sym in self.symbols:
                for tf in self.timeframes:
                    try:
                        triggers = self.scan_symbol_tf(sym, tf)
                        for pattern_name, direction, details in triggers:
                            new_triggers_this_cycle.append((sym, tf, pattern_name, direction, details))
                    except Exception as e:
                        traceback.print_exc()

            # Kirim pesan jika ada trigger BARU atau EXPIRED
            has_new = len(new_triggers_this_cycle) > 0
            has_expired = len(self.expired_this_cycle) > 0

            if has_new or has_expired:
                combined_triggers = []

                # 1. Trigger BARU (🆕)
                new_keys = set()
                for sym, tf, pattern_name, direction, details in new_triggers_this_cycle:
                    combined_triggers.append((sym, tf, pattern_name, direction, details, "new"))
                    new_keys.add(f"{sym}_{tf}_{pattern_name}")

                # 2. Trigger AKTIF carry over (🔄)
                for at_key, (sym, tf, pattern_name, direction, details, candle_ts) in self.active_triggers.items():
                    trigger_id = f"{sym}_{tf}_{pattern_name}"
                    if trigger_id not in new_keys:
                        combined_triggers.append((sym, tf, pattern_name, direction, details, "active"))

                self.notifier.send(combined_triggers, self.expired_this_cycle if has_expired else None)

            # Cleanup old data (> 2 hari)
            self._cleanup_old_data()

            time.sleep(5)

    def _cleanup_old_data(self):
        """Bersihkan seen_triggers dan active_triggers yang sudah > 2 hari."""
        current_time = time.time()
        max_age = 86400 * 2

        # Cleanup seen_triggers
        keys_to_del = []
        for k in self.seen_triggers.keys():
            ts = int(k.split("_")[-1])
            if current_time - ts > max_age:
                keys_to_del.append(k)
        for k in keys_to_del:
            del self.seen_triggers[k]

        # Cleanup active_triggers
        at_keys_to_del = []
        for k, (_, _, _, _, _, candle_ts) in self.active_triggers.items():
            if current_time - candle_ts > max_age:
                at_keys_to_del.append(k)
        for k in at_keys_to_del:
            del self.active_triggers[k]
