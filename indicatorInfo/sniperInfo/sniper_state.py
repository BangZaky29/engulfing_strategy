# =====================================================
# indicatorInfo/sniperInfo/sniper_state.py
# State Management untuk Sniper Dual TF + Shared Trigger File
# =====================================================

import os
import json
import datetime
from dataclasses import dataclass, field
from typing import Optional


class SniperPhase:
    IDLE = "SNIPER_IDLE"                # Menunggu M30 trigger
    WAITING_CONFIRM = "SNIPER_WAITING"  # M30 sudah trigger, menunggu M5 konfirmasi


# Path ke shared trigger file (dibaca oleh RCS untuk recovery)
_SNIPER_DIR = os.path.dirname(os.path.abspath(__file__))
SNIPER_TRIGGER_FILE = os.path.join(_SNIPER_DIR, "sniper_trigger.json")


@dataclass
class SniperState:
    """Runtime state untuk Sniper dual-TF monitor."""

    phase: str = SniperPhase.IDLE

    # M30 (Primary) trigger info
    primary_direction: Optional[str] = None  # "BUY" atau "SELL"
    primary_trigger_time: Optional[datetime.datetime] = None
    primary_candle_ts: int = 0               # Unix timestamp candle M30 saat trigger

    # M5 (Confirm) trigger info
    confirm_direction: Optional[str] = None
    confirm_candle_ts: int = 0

    # Tracking candle terakhir (untuk deteksi pergantian candle)
    last_primary_candle_ts: int = 0
    last_confirm_candle_ts: int = 0

    def reset(self):
        """Reset ke IDLE, siap untuk siklus baru."""
        self.phase = SniperPhase.IDLE
        self.primary_direction = None
        self.primary_trigger_time = None
        self.primary_candle_ts = 0
        self.confirm_direction = None
        self.confirm_candle_ts = 0

    def set_primary_trigger(self, direction: str, candle_ts: int):
        """Set state ke WAITING_CONFIRM setelah M30 engulfing murni terdeteksi."""
        self.phase = SniperPhase.WAITING_CONFIRM
        self.primary_direction = direction
        self.primary_trigger_time = datetime.datetime.now()
        self.primary_candle_ts = candle_ts

    def set_confirmed(self, direction: str, candle_ts: int):
        """Set M5 confirmation data."""
        self.confirm_direction = direction
        self.confirm_candle_ts = candle_ts


def write_sniper_trigger(symbol: str, direction: str, tf_primary: str,
                          tf_confirm: str, primary_candle_ts: int,
                          confirm_candle_ts: int, m5_open: float = 0.0,
                          m5_high: float = 0.0, m5_low: float = 0.0, m5_close: float = 0.0):
    """
    Tulis trigger sniper confirmed ke shared JSON file.
    File ini akan dibaca oleh RCS engine untuk eksekusi recovery.
    Atomic write menggunakan os.replace untuk mencegah corrupt.
    """
    data = {
        "symbol": symbol,
        "direction": direction,
        "tf_primary": tf_primary,
        "tf_confirm": tf_confirm,
        "primary_candle_ts": primary_candle_ts,
        "confirm_candle_ts": confirm_candle_ts,
        "m5_open": m5_open,
        "m5_high": m5_high,
        "m5_low": m5_low,
        "m5_close": m5_close,
        "confirmed_at": datetime.datetime.now().isoformat(),
        "consumed": False,
        "consumed_by": None,
    }

    temp_file = f"{SNIPER_TRIGGER_FILE}.tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(temp_file, SNIPER_TRIGGER_FILE)
    except Exception as e:
        print(f"⚠️ [SNIPER] Gagal menulis sniper_trigger.json: {e}")


def clear_sniper_trigger():
    """Hapus shared trigger file (saat expired/invalidasi)."""
    if os.path.exists(SNIPER_TRIGGER_FILE):
        try:
            os.remove(SNIPER_TRIGGER_FILE)
        except Exception:
            pass
