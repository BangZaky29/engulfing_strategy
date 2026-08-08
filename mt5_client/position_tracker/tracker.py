# =====================================================
# mt5_client/position_tracker/tracker.py
# Mesin Sentral: Memantau semua posisi di MT5 broker
# Membedakan OP sistem vs OP manual per-symbol
# =====================================================

import os
import time
import MetaTrader5 as mt5
from datetime import datetime, timezone
from typing import Optional
from threading import Lock

from .models import TrackedPosition, PositionOrigin, PositionSnapshot, ClosedManualSummary


class PositionTracker:
    """
    Singleton yang memantau semua posisi aktif di MT5 broker.

    Mekanisme:
    1. Strategi memanggil register_system_ticket() saat membuka OP
    2. poll_positions() membaca MT5 → bandingkan dengan known tickets
    3. Posisi yang tidak dikenali (magic=0 atau bukan di known list) = MANUAL
    4. Posisi yang hilang dari poll sebelumnya = baru ditutup
    """

    _instance: Optional["PositionTracker"] = None
    _lock = Lock()

    def __new__(cls) -> "PositionTracker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Config
        self.enabled = os.getenv("POSITION_TRACKER_ENABLED", "true").lower() == "true"
        self.pause_on_manual = os.getenv("POSITION_TRACKER_PAUSE_ON_MANUAL", "true").lower() == "true"

        # Known system magic numbers (auto-loaded dari config strategi)
        self._known_magics: set[int] = set()
        self._load_known_magics()

        # Registered system tickets: {ticket: TrackedPosition}
        self._system_tickets: dict[int, TrackedPosition] = {}

        # Previous snapshot per symbol: {symbol: {ticket: TrackedPosition}}
        self._prev_snapshot: dict[str, dict[int, TrackedPosition]] = {}

        # Closed manual positions per symbol: {symbol: [TrackedPosition]}
        self._closed_manual: dict[str, list[TrackedPosition]] = {}

        # Event callbacks
        self._on_manual_open_callbacks = []
        self._on_manual_close_callbacks = []
        self._on_all_manual_cleared_callbacks = []

        # Throttle notifikasi: {symbol: last_notif_time}
        self._last_manual_open_notif: dict[str, float] = {}
        self._notif_throttle_sec = 30  # Min 30 detik antar notif OP manual terbuka

    def _load_known_magics(self):
        """Load magic numbers yang dikenali sebagai SYSTEM dari env."""
        # Magic dari RCS config
        rcs_magics = [
            os.getenv("RCS_MAGIC_OP1", "901001"),
            os.getenv("RCS_MAGIC_OP2", "901002"),
            os.getenv("RCS_MAGIC_OP3", "901003"),
        ]
        for m in rcs_magics:
            try:
                self._known_magics.add(int(m))
            except (ValueError, TypeError):
                pass

        # Magic dari ITR config
        itr_magic = os.getenv("ITR_MAGIC_NUMBER", "")
        if itr_magic:
            try:
                self._known_magics.add(int(itr_magic))
            except (ValueError, TypeError):
                pass

        # Magic dari Engulfing config
        eng_magic = os.getenv("EXECUTION_MAGIC_NUMBER", "")
        if eng_magic:
            try:
                self._known_magics.add(int(eng_magic))
            except (ValueError, TypeError):
                pass

        # Override manual dari env
        extra = os.getenv("KNOWN_SYSTEM_MAGICS", "")
        if extra:
            for m in extra.split(","):
                m = m.strip()
                if m:
                    try:
                        self._known_magics.add(int(m))
                    except (ValueError, TypeError):
                        pass

        # Per-symbol RCS magics (contoh: XAUUSD_RCS_MAGIC_OP1)
        rcs_symbols = os.getenv("RCS_SYMBOL", "")
        if rcs_symbols:
            for sym in rcs_symbols.split(","):
                sym = sym.strip()
                if not sym:
                    continue
                for suffix in ["RCS_MAGIC_OP1", "RCS_MAGIC_OP2", "RCS_MAGIC_OP3"]:
                    val = os.getenv(f"{sym}_{suffix}", "")
                    if val:
                        try:
                            self._known_magics.add(int(val))
                        except (ValueError, TypeError):
                            pass

    def add_known_magic(self, magic: int):
        """Tambah magic number yang dikenali sebagai SYSTEM secara runtime."""
        self._known_magics.add(magic)

    def register_system_ticket(
        self,
        symbol: str,
        ticket: int,
        strategy: str,
        magic: int,
        direction: str = "",
        volume: float = 0.0,
        open_price: float = 0.0,
    ):
        """
        Daftarkan ticket yang baru dibuka oleh sistem.
        Dipanggil oleh strategi setelah berhasil membuka OP.
        """
        if not self.enabled:
            return

        tracked = TrackedPosition(
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            volume=volume,
            open_price=open_price,
            open_time=datetime.now(),
            magic_number=magic,
            comment=f"{strategy}_SYSTEM",
            origin=PositionOrigin.SYSTEM,
            strategy=strategy,
        )
        self._system_tickets[ticket] = tracked
        self.add_known_magic(magic)

    def unregister_system_ticket(self, ticket: int):
        """Hapus ticket dari daftar sistem (saat posisi ditutup oleh strategi)."""
        self._system_tickets.pop(ticket, None)

    def _classify_position(self, pos) -> TrackedPosition:
        """
        Klasifikasi satu posisi MT5 menjadi TrackedPosition.
        Menentukan apakah SYSTEM atau MANUAL berdasarkan:
        1. Apakah ticket ada di _system_tickets (registered)
        2. Apakah magic_number ada di _known_magics
        """
        ticket = pos.ticket
        magic = pos.magic
        symbol = pos.symbol

        # 1. Cek apakah ticket sudah di-register oleh strategi
        if ticket in self._system_tickets:
            existing = self._system_tickets[ticket]
            existing.current_profit = pos.profit
            existing.current_swap = pos.swap
            existing.current_commission = pos.commission if hasattr(pos, 'commission') else 0.0
            existing.volume = pos.volume
            return existing

        # 2. Cek magic number
        if magic != 0 and magic in self._known_magics:
            origin = PositionOrigin.SYSTEM
            strategy = self._guess_strategy_from_magic(magic)
        else:
            origin = PositionOrigin.MANUAL
            strategy = "UNKNOWN"

        direction = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        open_time = datetime.fromtimestamp(pos.time)

        return TrackedPosition(
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            volume=pos.volume,
            open_price=pos.price_open,
            open_time=open_time,
            magic_number=magic,
            comment=pos.comment if hasattr(pos, 'comment') else "",
            origin=origin,
            strategy=strategy,
            current_profit=pos.profit,
            current_swap=pos.swap,
            current_commission=pos.commission if hasattr(pos, 'commission') else 0.0,
        )

    def _guess_strategy_from_magic(self, magic: int) -> str:
        """Tebak strategi berdasarkan magic number."""
        rcs_magics = set()
        for key in ["RCS_MAGIC_OP1", "RCS_MAGIC_OP2", "RCS_MAGIC_OP3"]:
            val = os.getenv(key, "")
            if val:
                try:
                    rcs_magics.add(int(val))
                except (ValueError, TypeError):
                    pass
        # Also check per-symbol RCS magics
        rcs_symbols = os.getenv("RCS_SYMBOL", "")
        if rcs_symbols:
            for sym in rcs_symbols.split(","):
                sym = sym.strip()
                if not sym:
                    continue
                for suffix in ["RCS_MAGIC_OP1", "RCS_MAGIC_OP2", "RCS_MAGIC_OP3"]:
                    val = os.getenv(f"{sym}_{suffix}", "")
                    if val:
                        try:
                            rcs_magics.add(int(val))
                        except (ValueError, TypeError):
                            pass

        if magic in rcs_magics:
            return "RCS"

        itr_magic = os.getenv("ITR_MAGIC_NUMBER", "")
        if itr_magic and magic == int(itr_magic):
            return "ITR"

        eng_magic = os.getenv("EXECUTION_MAGIC_NUMBER", "")
        if eng_magic and magic == int(eng_magic):
            return "ENGULFING"

        return "UNKNOWN"

    def poll_positions(self, symbol: str) -> PositionSnapshot:
        """
        Poll semua posisi aktif di broker untuk symbol tertentu.
        Deteksi posisi baru (manual/system) dan posisi yang baru ditutup.

        Returns: PositionSnapshot dengan klasifikasi lengkap.
        """
        if not self.enabled:
            return PositionSnapshot(symbol=symbol, timestamp=datetime.now())

        all_positions = mt5.positions_get(symbol=symbol)
        if all_positions is None:
            all_positions = ()

        current_tickets: dict[int, TrackedPosition] = {}
        system_list = []
        manual_list = []
        total_sys_float = 0.0
        total_man_float = 0.0

        for pos in all_positions:
            tracked = self._classify_position(pos)
            current_tickets[tracked.ticket] = tracked

            if tracked.origin == PositionOrigin.SYSTEM:
                system_list.append(tracked)
                total_sys_float += tracked.net_profit
            else:
                manual_list.append(tracked)
                total_man_float += tracked.net_profit

        # Deteksi posisi yang baru muncul (tidak ada di snapshot sebelumnya)
        prev = self._prev_snapshot.get(symbol, {})
        new_manual = []
        for ticket, tracked in current_tickets.items():
            if ticket not in prev and tracked.origin == PositionOrigin.MANUAL:
                new_manual.append(tracked)

        # Deteksi posisi yang hilang (ditutup)
        closed_manual = []
        for ticket, old_tracked in prev.items():
            if ticket not in current_tickets and old_tracked.origin == PositionOrigin.MANUAL:
                # Posisi manual baru saja ditutup — ambil profit dari history
                old_tracked.is_closed = True
                old_tracked.close_time = datetime.now()
                # Ambil profit aktual dari history broker
                self._fill_closed_profit(old_tracked)
                closed_manual.append(old_tracked)

        # Simpan closed manual untuk kalkulasi nanti
        if symbol not in self._closed_manual:
            self._closed_manual[symbol] = []
        self._closed_manual[symbol].extend(closed_manual)

        # Deteksi system tickets yang hilang → unregister
        for ticket, old_tracked in prev.items():
            if ticket not in current_tickets and old_tracked.origin == PositionOrigin.SYSTEM:
                self.unregister_system_ticket(ticket)

        # Emit callbacks untuk manual open
        if new_manual:
            now = time.time()
            last = self._last_manual_open_notif.get(symbol, 0)
            if now - last >= self._notif_throttle_sec:
                self._last_manual_open_notif[symbol] = now
                for cb in self._on_manual_open_callbacks:
                    try:
                        cb(symbol, new_manual)
                    except Exception as e:
                        print(f"⚠️ PositionTracker callback error (manual_open): {e}")

        # Emit callbacks untuk manual close
        if closed_manual:
            for cb in self._on_manual_close_callbacks:
                try:
                    cb(symbol, closed_manual)
                except Exception as e:
                    print(f"⚠️ PositionTracker callback error (manual_close): {e}")

        # Emit all_manual_cleared jika sebelumnya ada manual, sekarang 0
        prev_had_manual = any(
            t.origin == PositionOrigin.MANUAL for t in prev.values()
        )
        if prev_had_manual and len(manual_list) == 0:
            for cb in self._on_all_manual_cleared_callbacks:
                try:
                    cb(symbol)
                except Exception as e:
                    print(f"⚠️ PositionTracker callback error (all_cleared): {e}")

        # Update snapshot
        self._prev_snapshot[symbol] = current_tickets

        return PositionSnapshot(
            symbol=symbol,
            timestamp=datetime.now(),
            system_positions=system_list,
            manual_positions=manual_list,
            total_system_floating=total_sys_float,
            total_manual_floating=total_man_float,
        )

    def _fill_closed_profit(self, tracked: TrackedPosition):
        """
        Ambil profit aktual dari MT5 history deals untuk posisi yang baru ditutup.
        Ini menjamin akurasi presisi dari broker.
        """
        try:
            deals = mt5.history_deals_get(position=tracked.ticket)
            if deals:
                total_profit = 0.0
                total_swap = 0.0
                total_commission = 0.0
                for deal in deals:
                    total_profit += deal.profit
                    total_swap += deal.swap
                    total_commission += deal.commission
                tracked.close_profit = total_profit
                tracked.close_swap = total_swap
                tracked.close_commission = total_commission
        except Exception:
            # Fallback: gunakan last known floating
            tracked.close_profit = tracked.current_profit
            tracked.close_swap = tracked.current_swap
            tracked.close_commission = tracked.current_commission

    # =========================================================
    # Public Query Methods
    # =========================================================

    def get_manual_positions(self, symbol: str) -> list[TrackedPosition]:
        """Ambil semua posisi MANUAL yang masih aktif untuk symbol."""
        snapshot = self._prev_snapshot.get(symbol, {})
        return [
            t for t in snapshot.values()
            if t.origin == PositionOrigin.MANUAL
        ]

    def get_all_positions(self, symbol: str) -> list[TrackedPosition]:
        """Ambil semua posisi aktif (sistem + manual) untuk symbol."""
        snapshot = self._prev_snapshot.get(symbol, {})
        return list(snapshot.values())

    def get_total_floating(self, symbol: str) -> float:
        """Total floating profit/loss (sistem + manual) untuk symbol."""
        snapshot = self._prev_snapshot.get(symbol, {})
        return sum(t.net_profit for t in snapshot.values())

    def get_manual_floating(self, symbol: str) -> float:
        """Total floating profit/loss hanya dari posisi MANUAL."""
        snapshot = self._prev_snapshot.get(symbol, {})
        return sum(
            t.net_profit for t in snapshot.values()
            if t.origin == PositionOrigin.MANUAL
        )

    def has_manual_positions(self, symbol: str) -> bool:
        """Apakah ada posisi MANUAL yang masih aktif untuk symbol?"""
        snapshot = self._prev_snapshot.get(symbol, {})
        return any(t.origin == PositionOrigin.MANUAL for t in snapshot.values())

    def get_manual_count(self, symbol: str) -> int:
        """Jumlah posisi MANUAL aktif untuk symbol."""
        snapshot = self._prev_snapshot.get(symbol, {})
        return sum(1 for t in snapshot.values() if t.origin == PositionOrigin.MANUAL)

    def get_closed_manual_summary(
        self, symbol: str, since: datetime | None = None
    ) -> ClosedManualSummary:
        """
        Ringkasan OP manual yang sudah ditutup untuk symbol.
        Data profit diambil langsung dari MT5 history deals (presisi broker).

        Args:
            symbol: Pair mata uang
            since: Hanya hitung yang ditutup setelah waktu ini (opsional)
        """
        closed_list = self._closed_manual.get(symbol, [])

        if since:
            closed_list = [
                p for p in closed_list
                if p.close_time and p.close_time >= since
            ]

        summary = ClosedManualSummary(
            total_count=len(closed_list),
            positions=closed_list,
        )

        for p in closed_list:
            summary.total_profit += p.close_profit
            summary.total_swap += p.close_swap
            summary.total_commission += p.close_commission

        return summary

    def is_symbol_clear(self, symbol: str) -> bool:
        """
        Apakah symbol benar-benar bersih? (0 posisi aktif, termasuk manual)
        Digunakan oleh RCS unfreeze check.
        """
        snapshot = self._prev_snapshot.get(symbol, {})
        return len(snapshot) == 0

    def clear_closed_manual(self, symbol: str):
        """Reset daftar closed manual untuk symbol (setelah siklus selesai)."""
        self._closed_manual[symbol] = []

    # =========================================================
    # Event Registration
    # =========================================================

    def on_manual_open(self, callback):
        """Register callback saat OP manual baru terdeteksi. callback(symbol, positions)"""
        self._on_manual_open_callbacks.append(callback)

    def on_manual_close(self, callback):
        """Register callback saat OP manual ditutup. callback(symbol, closed_positions)"""
        self._on_manual_close_callbacks.append(callback)

    def on_all_manual_cleared(self, callback):
        """Register callback saat semua OP manual di symbol sudah ditutup. callback(symbol)"""
        self._on_all_manual_cleared_callbacks.append(callback)

    # =========================================================
    # Debug / Diagnostics
    # =========================================================

    def get_status_text(self, symbol: str) -> str:
        """Status ringkas untuk logging terminal."""
        snapshot = self._prev_snapshot.get(symbol, {})
        sys_count = sum(1 for t in snapshot.values() if t.origin == PositionOrigin.SYSTEM)
        man_count = sum(1 for t in snapshot.values() if t.origin == PositionOrigin.MANUAL)
        man_float = sum(
            t.net_profit for t in snapshot.values() if t.origin == PositionOrigin.MANUAL
        )

        if man_count > 0:
            return f"⚠️ OP Manual: {man_count} | Floating: ${man_float:.2f} | Sistem: {sys_count}"
        return f"✅ Bersih | Sistem: {sys_count}"

    def get_known_magics_text(self) -> str:
        """Daftar magic numbers yang dikenali untuk logging."""
        return ", ".join(str(m) for m in sorted(self._known_magics))
