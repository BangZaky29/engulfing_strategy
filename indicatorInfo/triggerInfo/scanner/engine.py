"""
MultiPatternScanner Engine - scan loop utama dengan state management.

Responsibilities:
- Loop scan semua symbol × timeframe × pattern
- Manage active_triggers, seen_triggers, expired state
- Delegate notifikasi ke ScannerNotifier
"""

import os
import json
import time
import traceback
from datetime import datetime, timezone

import MetaTrader5 as mt5

from utils.colors import cprint, Colors
from database.supabase_client import get_supabase

from .patterns import get_all_patterns
from .notifier import ScannerNotifier


class MultiPatternScanner:
    """Mesin scanner multi-pattern dengan active trigger tracking & state persistence."""

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

        # Path file state untuk persistent caching antar restart
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.state_file_path = os.path.abspath(os.path.join(current_dir, "..", "scanner_state.json"))

        # Pastikan seluruh symbol terpilih di Market Watch MT5
        for sym in self.symbols:
            mt5.symbol_select(sym, True)

        # Notifier
        group_jid = os.getenv("SCANNER_GROUP_JID", "120363410782502082@g.us")
        self.notifier = ScannerNotifier(group_jid)

        # ============================================================
        # STATE MANAGEMENT - Ironclad Deduplication
        # ============================================================
        
        # PRIMARY DEDUP: Set berisi string "SYMBOL_TF_CANDLETS_PATTERN"
        # Ini adalah guard UTAMA. Jika key sudah ada di set ini,
        # pattern TIDAK akan dideteksi ulang, di-print, atau dikirim.
        self._detected_keys = set()

        # Active triggers: {f"{symbol}_{tf}_{pattern}": (symbol, tf, pattern, dir, details, candle_ts)}
        self.active_triggers = {}

        # Track candle timestamp terakhir: {f"{symbol}_{tf}": candle_ts}
        self.last_candle_time = {}

        # Expired dalam siklus ini (di-reset tiap siklus)
        self.expired_this_cycle = []

        # Load state tersimpan dari disk (agar kebal amnesia saat restart/watchdog)
        self._load_state()

    def _load_state(self):
        """Memuat state scanner dari file JSON lokal jika ada."""
        if not os.path.exists(self.state_file_path):
            return

        try:
            with open(self.state_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Load detected_keys (primary dedup set)
            saved_detected = data.get("detected_keys", [])
            if isinstance(saved_detected, list):
                self._detected_keys = set(saved_detected)
            
            # Backward compat: migrate old seen_triggers format to detected_keys
            old_seen = data.get("seen_triggers", {})
            for cache_key, pattern_names in old_seen.items():
                if isinstance(pattern_names, list):
                    # cache_key = "SYMBOL_TF_CANDLETS", pattern_names = ["Engulfing", ...]
                    for pname in pattern_names:
                        self._detected_keys.add(f"{cache_key}_{pname}")

            self.last_candle_time = data.get("last_candle_time", {})

            # Reconstruct active_triggers (memastikan tuple format)
            raw_active = data.get("active_triggers", {})
            reconstructed_active = {}
            for k, val in raw_active.items():
                if isinstance(val, (list, tuple)) and len(val) >= 6:
                    reconstructed_active[k] = tuple(val[:6])
            self.active_triggers = reconstructed_active

            print(cprint(
                f"💾 [SCANNER] State scanner berhasil dimuat dari disk "
                f"({len(self._detected_keys)} detected keys, {len(self.active_triggers)} active triggers).",
                Colors.GREEN
            ))
        except Exception as e:
            print(cprint(f"⚠️ Gagal memuat scanner_state.json: {e}", Colors.YELLOW))

    def _save_state(self):
        """Menyimpan state scanner saat ini ke file JSON secara atomic."""
        # Convert details dicts to ensure JSON-safe types (no numpy)
        safe_active = {}
        for k, val in self.active_triggers.items():
            if isinstance(val, (list, tuple)) and len(val) >= 6:
                sym, tf, pname, direction, details, cts = val[:6]
                # Deep-convert details to pure Python types
                safe_details = {}
                for dk, dv in details.items():
                    try:
                        safe_details[dk] = float(dv) if isinstance(dv, float) else int(dv) if isinstance(dv, int) else dv
                        # Force Python native via repr roundtrip for numpy types
                        if hasattr(dv, 'item'):
                            safe_details[dk] = dv.item()
                    except (TypeError, ValueError):
                        safe_details[dk] = str(dv)
                safe_active[k] = [sym, tf, pname, direction, safe_details, int(cts) if hasattr(cts, 'item') else cts]

        data = {
            "detected_keys": list(self._detected_keys),
            "active_triggers": safe_active,
            "last_candle_time": self.last_candle_time,
            "updated_at": datetime.now().isoformat()
        }
        temp_file = f"{self.state_file_path}.tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(temp_file, self.state_file_path)
        except Exception as e:
            print(cprint(f"⚠️ Gagal menyimpan scanner_state.json: {e}", Colors.YELLOW))

    def scan_symbol_tf(self, symbol: str, tf_str: str):
        """Scan 1 symbol pada 1 timeframe, jalankan semua pattern dari registry."""
        tf_mt5 = self.TF_MAPPING.get(tf_str, mt5.TIMEFRAME_M5)

        # Pastikan symbol aktif di Market Watch MT5
        mt5.symbol_select(symbol, True)

        # Ambil 10 candle terakhir (dengan retry jika history belum di-download oleh terminal MT5)
        rates = None
        for _ in range(3):
            rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 1, 10)
            if rates is not None and len(rates) >= 10:
                break
            time.sleep(0.2)

        if rates is None or len(rates) < 10:
            err = mt5.last_error()
            count = len(rates) if rates is not None else 0
            print(cprint(f"⚠️ [SCANNER] Data candle {symbol} {tf_str} tidak cukup/gagal diambil ({count}/10): {err}", Colors.YELLOW))
            return []

        c1 = rates[-1]
        c2 = rates[-2]

        c_time = datetime.fromtimestamp(c1['time'], timezone.utc)
        candle_ts = int(c1['time'])
        active_key = f"{symbol}_{tf_str}"

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

        sym_info = mt5.symbol_info(symbol)
        point = sym_info.point if sym_info and getattr(sym_info, 'point', 0) > 0 else 0.00001
        reversed_rates = list(reversed(rates))

        # === Run semua pattern dari registry ===
        triggers_found = []
        for pattern in self.patterns:
            # PRIMARY DEDUP CHECK (ironclad set-based)
            dedup_key = f"{symbol}_{tf_str}_{candle_ts}_{pattern.name}"
            if dedup_key in self._detected_keys:
                continue  # SUDAH terdeteksi → skip sepenuhnya

            results = pattern.detect(candle_data, reversed_rates, point)
            for direction, details in results:
                # Convert numpy types to pure Python immediately
                safe_details = {}
                for dk, dv in details.items():
                    if hasattr(dv, 'item'):
                        safe_details[dk] = dv.item()
                    else:
                        safe_details[dk] = dv
                safe_details['candle_ts'] = candle_ts
                
                triggers_found.append((pattern.name, direction, safe_details))
                # Mark as detected IMMEDIATELY in the set
                self._detected_keys.add(dedup_key)

        # Print ke terminal & simpan ke Supabase HANYA untuk trigger BARU
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
            keys_to_remove = [k for k in list(self.active_triggers.keys()) if k.startswith(f"{active_key}_")]
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

        # Tampilkan Banner Akun MT5 saat Startup Scanner
        if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
            from mt5_client.multi_account_dispatcher import get_multi_account_funds_info
            funds_list = get_multi_account_funds_info("SCANNER")
            print("==================================================")
            print(cprint(f"💰 INFORMASI DANA & KESEHATAN AKUN SCANNER MT5:", Colors.CYAN))
            for f in funds_list:
                if not f.get('connected'):
                    print(cprint(f"⚠️ [{f['key']}] Gagal audit akun {f['name']}: {f.get('error')}", Colors.YELLOW))
                    continue
                print(cprint(f"🔹 [{f['key']}] {f['name']} (Login: {f['login']} | Server: {f['server']})", Colors.CYAN))
                print(cprint(f"   • Tipe Akun      : {f['account_type']}", Colors.CYAN))
                print(cprint(f"   • Balance / Eq   : ${f['balance']:.2f} / ${f['equity']:.2f}", Colors.CYAN))
                print(cprint(f"   • Free Margin    : ${f['margin_free']:.2f} (Margin Level: {f['health_status']})", Colors.CYAN))
                print(cprint(f"   • Leverage Akun  : {f['leverage']} | Ping: {f['ping_str']} | AutoTrading: {f['autotrading']}", Colors.CYAN))
            print("==================================================")
        else:
            from mt5_client.money_management import get_account_funds_info
            funds_info = get_account_funds_info()
            print("==================================================")
            print(cprint(f"💰 DANA & KESEHATAN AKUN SCANNER MT5:", Colors.CYAN))
            print(cprint(f"   • Tipe Akun      : {funds_info['account_type']} (Login: {funds_info['account_number']} | Server: {funds_info['server']})", Colors.CYAN))
            print(cprint(f"   • Balance / Eq   : ${funds_info['balance']:.2f} / ${funds_info['equity']:.2f}", Colors.CYAN))
            print(cprint(f"   • Free Margin    : ${funds_info['margin_free']:.2f} (Margin Level: {funds_info['health_status']})", Colors.CYAN))
            print(cprint(f"   • Leverage Akun  : {funds_info['leverage']} | Ping: {funds_info['ping_str']} | AutoTrading: {funds_info['autotrading']}", Colors.CYAN))
            print("==================================================")
        print(cprint(f"🚀 MultiPatternScanner berjalan... ({len(pattern_names)} patterns: {', '.join(pattern_names)})", Colors.GREEN))
        print(cprint(f"📊 Symbols: {', '.join(self.symbols)} | Timeframes: {', '.join(self.timeframes)}", Colors.CYAN))
        print("--------------------------------------------------")

        cycle_count = 0
        while True:
            try:
                cycle_count += 1
                new_triggers_this_cycle = []
                self.expired_this_cycle = []

                for sym in self.symbols:
                    for tf in self.timeframes:
                        try:
                            triggers = self.scan_symbol_tf(sym, tf)
                            for pattern_name, direction, details in triggers:
                                new_triggers_this_cycle.append((sym, tf, pattern_name, direction, details))
                        except Exception as e:
                            print(cprint(f"⚠️ Error scanning {sym} {tf}: {e}", Colors.YELLOW))

                # Kirim pesan HANYA jika ada trigger BARU atau EXPIRED
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
                    for at_key, item in self.active_triggers.items():
                        if isinstance(item, (list, tuple)) and len(item) >= 6:
                            sym, tf, pattern_name, direction, details, candle_ts = item[:6]
                            trigger_id = f"{sym}_{tf}_{pattern_name}"
                            if trigger_id not in new_keys:
                                combined_triggers.append((sym, tf, pattern_name, direction, details, "active"))

                    self.notifier.send(
                        combined_triggers,
                        self.expired_this_cycle if has_expired else None,
                        force=has_new  # Force send jika ada sinyal BARU
                    )

                # Simpan state ke disk secara berkala
                if has_new or has_expired or (cycle_count % 12 == 0):
                    self._save_state()

                # Cleanup old data (> 2 hari) - jalankan setiap 60 siklus (~5 menit)
                if cycle_count % 60 == 0:
                    self._cleanup_old_data()

            except Exception as loop_err:
                print(cprint(f"⚠️ Exception di scanner loop: {loop_err}", Colors.RED))
                traceback.print_exc()

            time.sleep(5)

    def _cleanup_old_data(self):
        """Bersihkan detected_keys dan active_triggers yang sudah > 2 hari."""
        try:
            current_time = time.time()
            max_age = 86400 * 2

            # Cleanup _detected_keys: parse candle_ts dari key "SYMBOL_TF_CANDLETS_PATTERN"
            keys_to_del = set()
            for key in self._detected_keys:
                parts = key.split("_")
                # Format: SYMBOL_TF_CANDLETS_PATTERN → candle_ts adalah bagian ke-3 (index 2)
                # Tapi symbol bisa mengandung underscore, jadi cari timestamp yang berupa angka besar
                for part in parts:
                    if part.isdigit() and len(part) >= 9:  # Unix timestamp >= 9 digits
                        ts = int(part)
                        if ts > 1_000_000_000 and current_time - ts > max_age:
                            keys_to_del.add(key)
                        break
            self._detected_keys -= keys_to_del

            # Cleanup active_triggers
            at_keys_to_del = []
            for k, val in list(self.active_triggers.items()):
                if isinstance(val, (list, tuple)) and len(val) >= 6:
                    candle_ts = val[5]
                    if isinstance(candle_ts, (int, float)) and current_time - candle_ts > max_age:
                        at_keys_to_del.append(k)
            for k in at_keys_to_del:
                del self.active_triggers[k]

            if keys_to_del or at_keys_to_del:
                print(cprint(
                    f"🧹 [CLEANUP] Dihapus {len(keys_to_del)} detected keys, {len(at_keys_to_del)} active triggers (> 2 hari)",
                    Colors.CYAN
                ))
        except Exception as e:
            print(cprint(f"⚠️ Error in _cleanup_old_data: {e}", Colors.YELLOW))
