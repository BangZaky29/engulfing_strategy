"""Scanner WA Notifier - format & kirim pesan ringkasan trigger ke WA Group."""

import time
import hashlib
from datetime import datetime, timezone

from utils.colors import cprint, Colors
from database.supabase_client import execute_supabase


class ScannerNotifier:
    """Handle formatting dan pengiriman pesan scanner ke WA Group via wa_outbox."""

    # Urutan timeframe untuk sorting (kecil → besar)
    TF_ORDER = {"M1": 0, "M5": 1, "M15": 2, "M30": 3, "H1": 4, "H4": 5, "D1": 6, "W1": 7, "MN": 8}

    def __init__(self, group_jid: str):
        self.group_jid = group_jid
        self.last_sent_content_core = None
        self.last_sent_time = 0.0
        # Track dedupe_keys yang sudah berhasil dikirim (untuk mencegah retry spam)
        self._sent_dedupe_keys = set()

    def format_message(self, triggers: list, expired: list = None) -> tuple[str, str]:
        """Format pesan ringkasan WA dari triggers + expired.

        triggers format: (symbol, tf, pattern_name, direction, details, status)
            status: "new" | "active"
        expired format:  (symbol, tf, pattern_name, direction, details, candle_ts)

        Returns: (full_message, core_content_for_dedup)
        """
        if not triggers and not expired:
            return "", ""

        by_symbol = {}

        # Group active/new triggers by symbol
        for symbol, tf_str, pattern_name, direction, details, status in (triggers or []):
            if symbol not in by_symbol:
                by_symbol[symbol] = {"triggers": [], "expired": []}

            emoji = "🟢" if direction == "BUY" else "🔴"
            status_icon = "🆕" if status == "new" else "🔄"
            
            candle_time_str = ""
            if "candle_ts" in details:
                candle_time_str = f" | {datetime.fromtimestamp(details['candle_ts'], timezone.utc).strftime('%H.%M')}"

            detail_str = ""
            if details.get("streak"):
                detail_str = f" ({details['streak']}x{candle_time_str})"
            elif "c1_pips" in details:
                detail_str = f" (H {details['c1_pips']}{candle_time_str})"
            else:
                clean_time = candle_time_str.replace(" | ", "")
                if clean_time:
                    detail_str = f" ({clean_time})"

            by_symbol[symbol]["triggers"].append({
                "line": f"{emoji} {tf_str} : {pattern_name} {direction}{detail_str} {status_icon}",
                "core": f"{symbol}_{tf_str}_{pattern_name}_{direction}_{details.get('candle_ts', '')}",
                "tf_order": self.TF_ORDER.get(tf_str, 99)
            })

        # Group expired by symbol
        for symbol, tf_str, pattern_name, direction, details, candle_ts in (expired or []):
            if symbol not in by_symbol:
                by_symbol[symbol] = {"triggers": [], "expired": []}

            dir_label = "BUY" if direction == "BUY" else "SELL"
            by_symbol[symbol]["expired"].append({
                "line": f"🔕 {tf_str} : {pattern_name} {dir_label} _expired_",
                "core": f"EXP_{symbol}_{tf_str}_{pattern_name}",
                "tf_order": self.TF_ORDER.get(tf_str, 99)
            })

        # Build message lines & core content for deduplication
        lines = ["📡 *SCANNER UPDATE*"]
        core_parts = []
        for symbol, data in by_symbol.items():
            lines.append(f"   📌 *{symbol}*")
            # Sort & append active triggers
            data["triggers"].sort(key=lambda x: x["tf_order"])
            for entry in data["triggers"]:
                lines.append(entry["line"])
                core_parts.append(entry["core"])
            # Sort & append expired triggers
            if data["expired"]:
                data["expired"].sort(key=lambda x: x["tf_order"])
                for entry in data["expired"]:
                    lines.append(entry["line"])
                    core_parts.append(entry["core"])

        lines.append("")
        lines.append(f"⏰ {datetime.now().strftime('%H:%M WIB')} | 🆕 Baru | 🔄 Aktif | 🔕 Exp")

        return "\n".join(lines), "|".join(sorted(core_parts))

    def send(self, triggers: list, expired: list = None, force: bool = False):
        """Format & kirim ringkasan ke WA Group via wa_outbox.
        
        triggers format: (symbol, tf, pattern_name, direction, details, status)
        expired format:  (symbol, tf, pattern_name, direction, details, candle_ts)
        """
        if not triggers and not expired:
            return

        message, core_content = self.format_message(triggers, expired)
        if not message:
            return

        now = time.time()
        new_count = sum(1 for t in (triggers or []) if t[5] == "new")
        active_count = sum(1 for t in (triggers or []) if t[5] == "active")
        expired_count = len(expired or [])

        # ============================================================
        # IRONCLAD ANTI-SPAM: Cek berdasarkan KONTEN, bukan flag force
        # ============================================================
        
        # Jika core content PERSIS SAMA dengan yang terakhir dikirim → SKIP
        # (Ini mencegah spam bahkan jika engine salah menandai sebagai "new")
        if self.last_sent_content_core == core_content:
            return

        # Cooldown: minimal 30 detik antar pengiriman apapun
        if (now - self.last_sent_time) < 30:
            return

        # Hash dedupe_key berdasarkan CORE CONTENT saja (tanpa timestamp menit)
        # Ini memastikan pesan dengan isi yang sama TIDAK bisa dikirim 2x ke WA
        dedupe_hash = hashlib.md5(core_content.encode('utf-8')).hexdigest()[:16]
        dedupe_key = f'scanner_{dedupe_hash}'

        # Jika dedupe_key ini sudah pernah berhasil dikirim, skip
        if dedupe_key in self._sent_dedupe_keys:
            return

        payload = {
            'source_table': 'scanner_system',
            'event_type': 'SCANNER_TRIGGER',
            'group_jid': self.group_jid,
            'message_type': 'TEXT',
            'message': message,
            'dedupe_key': dedupe_key
        }

        try:
            execute_supabase(lambda sb: sb.table('wa_outbox').insert(payload).execute())
            self.last_sent_content_core = core_content
            self.last_sent_time = now
            self._sent_dedupe_keys.add(dedupe_key)

            log_parts = []
            if new_count: log_parts.append(f"{new_count} baru")
            if active_count: log_parts.append(f"{active_count} aktif")
            if expired_count: log_parts.append(f"{expired_count} expired")
            print(cprint(f"📲 Scanner summary terkirim ke {self.group_jid} ({', '.join(log_parts)})", Colors.GREEN))
        except Exception as e:
            err_str = str(e)
            if '23505' in err_str or 'duplicate' in err_str.lower():
                # Dedupe constraint di DB → pesan sudah pernah dikirim, track it
                self._sent_dedupe_keys.add(dedupe_key)
                self.last_sent_content_core = core_content
                self.last_sent_time = now
                # SILENT: jangan print error untuk duplikat — ini NORMAL
            else:
                print(cprint(f"⚠️ Gagal kirim scanner summary ke WA: {e}", Colors.RED))
