"""Scanner WA Notifier - format & kirim pesan ringkasan trigger ke WA Group."""

import time
import uuid
from datetime import datetime

from utils.colors import cprint, Colors
from database.supabase_client import execute_supabase


class ScannerNotifier:
    """Handle formatting dan pengiriman pesan scanner ke WA Group via wa_outbox."""

    # Urutan timeframe untuk sorting (kecil → besar)
    TF_ORDER = {"M1": 0, "M5": 1, "M15": 2, "M30": 3, "H1": 4, "H4": 5, "D1": 6, "W1": 7, "MN": 8}

    def __init__(self, group_jid: str):
        self.group_jid = group_jid

    def format_message(self, triggers: list, expired: list = None) -> str:
        """Format pesan ringkasan WA dari triggers + expired.

        triggers format: (symbol, tf, pattern_name, direction, details, status)
            status: "new" | "active"
        expired format:  (symbol, tf, pattern_name, direction, details, candle_ts)
        """
        if not triggers and not expired:
            return ""

        by_symbol = {}

        # Group active/new triggers by symbol
        for symbol, tf_str, pattern_name, direction, details, status in (triggers or []):
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
                "tf_order": self.TF_ORDER.get(tf_str, 99)
            })

        # Group expired by symbol
        for symbol, tf_str, pattern_name, direction, details, candle_ts in (expired or []):
            if symbol not in by_symbol:
                by_symbol[symbol] = {"triggers": [], "expired": []}

            dir_label = "BUY" if direction == "BUY" else "SELL"
            by_symbol[symbol]["expired"].append({
                "line": f"  🔕 {tf_str} → {pattern_name} {dir_label} _expired_",
                "tf_order": self.TF_ORDER.get(tf_str, 99)
            })

        # Build message lines
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

    def send(self, triggers: list, expired: list = None):
        """Format & kirim ringkasan ke WA Group via wa_outbox.
        
        triggers format: (symbol, tf, pattern_name, direction, details, status)
        expired format:  (symbol, tf, pattern_name, direction, details, candle_ts)
        """
        if not triggers and not expired:
            return

        message = self.format_message(triggers, expired)
        if not message:
            return

        # Hitung per kategori untuk log
        new_count = sum(1 for t in (triggers or []) if t[5] == "new")
        active_count = sum(1 for t in (triggers or []) if t[5] == "active")
        expired_count = len(expired or [])

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
