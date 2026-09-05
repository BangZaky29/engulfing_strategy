# =====================================================
# indicatorInfo/sniperInfo/sniper_notifier.py
# Notifikasi WA untuk Sniper Info → SNIPER_GROUP_JID
# =====================================================

import time
import hashlib
from datetime import datetime

from utils.colors import cprint, Colors
from database.supabase_client import execute_supabase


from config.sniper_config import SniperConfig

class SniperNotifier:
    """Handle pengiriman notifikasi Sniper ke WA Group via wa_outbox."""

    def __init__(self, config: SniperConfig):
        self.config = config
        self._sent_dedupe_keys = set()
        self.last_sent_time = 0.0

    def notify_primary_trigger(self, symbol: str, direction: str, tf_primary: str, tf_confirm: str):
        """
        Kirim notifikasi saat M30 (primary) engulfing murni terdeteksi.
        Info: Menunggu M5 (confirm) konfirmasi.
        """
        emoji = "🟢" if direction == "BUY" else "🔴"
        message = (
            f"🔫 *SNIPER ALERT*\n"
            f"   📌 *{symbol}*\n"
            f"   {emoji} {tf_primary} Engulfing Murni {direction} terdeteksi\n"
            f"   ⏳ Menunggu konfirmasi {tf_confirm} Engulfing Murni...\n"
            f"\n"
            f"⏰ {datetime.now().strftime('%H:%M WIB')}"
        )
        self._send(message, f"sniper_primary_{symbol}_{direction}_{int(time.time())}")

    def notify_confirmed(self, symbol: str, direction: str, tf_primary: str, tf_confirm: str):
        """
        Kirim notifikasi saat Sniper CONFIRMED (M30+M5 sinkron engulfing murni).
        """
        emoji = "🟢" if direction == "BUY" else "🔴"
        message = (
            f"🎯 *SNIPER CONFIRMED!*\n"
            f"   📌 *{symbol}*\n"
            f"   {emoji} {tf_primary}-{tf_confirm} Engulfing Murni {direction}\n"
            f"   💥 Trigger Sniper aktif — menunggu RCS Recovery\n"
            f"\n"
            f"⏰ {datetime.now().strftime('%H:%M WIB')}"
        )
        self._send(message, f"sniper_confirmed_{symbol}_{direction}_{int(time.time())}")

    def notify_expired(self, symbol: str, tf_primary: str, tf_confirm: str):
        """
        Kirim notifikasi saat sniper expired (M5 tidak konfirmasi sebelum M30 candle baru).
        """
        message = (
            f"⏰ *SNIPER EXPIRED*\n"
            f"   📌 *{symbol}*\n"
            f"   {tf_confirm} tidak mengkonfirmasi sebelum {tf_primary} candle baru.\n"
            f"   🔄 Reset — menunggu trigger {tf_primary} berikutnya.\n"
            f"\n"
            f"⏰ {datetime.now().strftime('%H:%M WIB')}\n\n"
            f"[SNIPER]"
        )
        self._send(message, f"sniper_expired_{symbol}_{int(time.time())}", self.config.group_jid)

    def notify_startup(self, acc_info: dict, symbols: list):
        """Kirim notifikasi saat bot sniper menyala."""
        sym_str = ", ".join(symbols)
        msg = (
            f"🚀 *SNIPER ENGINE STARTED*\n"
            f"Akun: {acc_info.get('name', 'Unknown')}\n"
            f"Saldo: ${acc_info.get('balance', 0):.2f}\n"
            f"Symbols: {sym_str}\n"
            f"TF: {self.config.tf_primary} → {self.config.tf_confirm}\n"
            f"Entry: {self.config.entry_percent}%\n"
            f"TP: {self.config.tp_percent}%\n"
            f"EMA Filter: M30={'ON' if self.config.ema_filter_primary_enabled else 'OFF'}, M5={'ON' if self.config.ema_filter_confirm_enabled else 'OFF'}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M WIB')}\n\n"
            f"[SNIPER]"
        )
        self._send(msg, f"sniper_startup_{int(time.time())}", self.config.group_jid)

    def notify_op_signal(self, symbol: str, direction: str, ticket: int, entry_price: float, sl: float, tp: float):
        """Kirim notifikasi saat pending order dipasang atau limit tersentuh."""
        emoji = "🟢" if direction == "BUY" else "🔴"
        msg = (
            f"🛒 *SNIPER OP SIGNAL*\n"
            f"   📌 *{symbol}* - {direction} {emoji}\n"
            f"   Ticket: #{ticket}\n"
            f"   Entry: {entry_price:.5f}\n"
            f"   SL: {sl:.5f}\n"
            f"   TP: {tp:.5f}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M WIB')}\n\n"
            f"[SNIPER]"
        )
        self._send(msg, f"sniper_op_{ticket}_{int(time.time())}", self.config.op_group_jid)

    def notify_profit_loss(self, symbol: str, ticket: int, profit: float, pips: int, img_url: str):
        """Kirim notifikasi saat order diclose (SL/TP) beserta gambar."""
        is_profit = profit > 0
        status_str = "PROFIT 🤑" if is_profit else "LOSS 😭"
        emoji = "📈" if is_profit else "📉"
        
        msg = (
            f"{emoji} *SNIPER {status_str}*\n"
            f"   📌 *{symbol}*\n"
            f"   Ticket: #{ticket}\n"
            f"   Hasil: ${profit:.2f} ({pips} pts)\n\n"
            f"📷 Chart: {img_url if img_url else 'No Image'}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M WIB')}\n\n"
            f"[SNIPER]"
        )
        target_jid = self.config.profit_group_jid if is_profit else self.config.loss_group_jid
        self._send(msg, f"sniper_close_{ticket}_{int(time.time())}", target_jid)

    def _send(self, message: str, dedupe_key: str, target_jid: str):
        """Kirim pesan ke WA via Supabase wa_outbox."""
        # Cooldown minimal 5 detik
        now = time.time()
        if (now - self.last_sent_time) < 5:
            return

        # Hash dedupe key
        hashed = hashlib.md5(dedupe_key.encode("utf-8")).hexdigest()[:16]
        full_key = f"sniper_{hashed}"

        if full_key in self._sent_dedupe_keys:
            return

        payload = {
            "source_table": "sniper_system",
            "event_type": "SNIPER_TRIGGER",
            "group_jid": target_jid,
            "message_type": "TEXT",
            "message": message,
            "dedupe_key": full_key,
        }

        try:
            execute_supabase(
                lambda sb: sb.table("wa_outbox").insert(payload).execute()
            )
            self.last_sent_time = now
            self._sent_dedupe_keys.add(full_key)
            print(cprint(f"📲 [SNIPER] Notifikasi terkirim ke {target_jid}", Colors.GREEN))
        except Exception as e:
            err_str = str(e)
            if "23505" in err_str or "duplicate" in err_str.lower():
                self._sent_dedupe_keys.add(full_key)
                self.last_sent_time = now
            else:
                print(cprint(f"⚠️ [SNIPER] Gagal kirim notif WA: {e}", Colors.RED))
