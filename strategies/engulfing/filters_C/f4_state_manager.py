# =====================================================
# strategies/engulfing/filters_C/f4_state_manager.py
# State tracking, age calculation, event key dedup
# Transfer dari Config.mqh (state) + Utils.mqh (age/format)
# =====================================================

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from .f3_ema_utils import ema_relation_text, get_ema_value

# Direction Constants
DIR_NONE = 0
DIR_BUY = 1
DIR_SELL = -1
DIR_MIXED = 2


@dataclass
class TFMState:
    """
    State trigger pada satu timeframe.
    Mirror dari TFM_State struct di Config.mqh.
    """
    direction: int = DIR_NONE
    source: str = "Wait"
    time: datetime | None = None
    range_points: float = 0.0


def clear_state() -> TFMState:
    return TFMState(direction=DIR_NONE, source="Wait", time=None, range_points=0.0)


def direction_to_string(direction: int) -> str:
    if direction == DIR_BUY:
        return "Buy"
    if direction == DIR_SELL:
        return "Sell"
    if direction == DIR_MIXED:
        return "Mixed"
    return "Wait"


def state_equals(a: TFMState, b: TFMState) -> bool:
    return (
        a.direction == b.direction
        and a.source == b.source
        and a.time == b.time
    )


def state_key(state: TFMState) -> str:
    """Build dedup key dari state."""
    time_val = int(state.time.timestamp()) if state.time else 0
    return f"{state.direction}:{state.source}:{time_val}"


def state_age_candles(state: TFMState, candles: list[dict]) -> int:
    """
    Hitung umur trigger dalam candle (berapa candle closed setelah trigger).
    
    Transfer dari TFM_StateAgeCandles() di Utils.mqh.
    
    candles: list of dicts, index 0 = oldest, -1 = newest.
    Shift=1 = last closed candle.
    """
    if state.time is None:
        return 0

    if not candles:
        return 0

    # Cari shift: candle mana yang time-nya match dengan state.time
    trigger_time = state.time
    trigger_shift = -1

    for i in range(len(candles)):
        candle_time = candles[i].get("time")
        if candle_time and candle_time == trigger_time:
            trigger_shift = len(candles) - i  # convert index to shift
            break

    if trigger_shift < 0:
        # Fallback: cari yang paling dekat
        for i in range(len(candles) - 1, -1, -1):
            candle_time = candles[i].get("time")
            if candle_time and candle_time <= trigger_time:
                trigger_shift = len(candles) - i
                break

    if trigger_shift < 0:
        return 0

    # Age = shift - 1 (shift=1 artinya age=0 = trigger di candle closed terakhir)
    age = trigger_shift - 1
    return max(age, 0)


def format_time_hhmm(dt: datetime | None) -> str:
    if dt is None:
        return "--:--"
    return dt.strftime("%H:%M")


def state_marker_text(
    state: TFMState,
    candles: list[dict],
    ema_values: list[float],
    use_ema_filter: bool,
    is_new: bool,
) -> str:
    """
    Format marker text: (N) 09:00 (Trend) atau (2) 09:00
    
    Transfer dari TFM_StateMarkerText() di Utils.mqh.
    """
    if state.direction == DIR_NONE or state.time is None:
        return ""

    trigger_time = format_time_hhmm(state.time)
    age = state_age_candles(state, candles)

    # Cari close price dan ema value pada waktu trigger
    close_price = 0.0
    ema_val = 0.0
    if state.time and candles:
        for i, c in enumerate(candles):
            if c.get("time") == state.time:
                close_price = float(c.get("close", 0.0))
                shift = len(candles) - i
                ema_val = get_ema_value(ema_values, shift)
                break

    ema_text = ema_relation_text(state.direction, close_price, ema_val, use_ema_filter)

    # Trigger baru atau masih fresh (age=0)
    if age <= 0:
        marker = f" (N) {trigger_time}"
        if ema_text:
            marker += f" ({ema_text})"
        return marker

    return f" ({age}) {trigger_time}"


def state_text(
    tf_name: str,
    state: TFMState,
    candles: list[dict],
    ema_values: list[float],
    use_ema_filter: bool,
    is_new: bool,
) -> str:
    """
    Build text representation: "H1 Buy-Multi:Engulfing+DB-4 (N) 09:00 (Trend)"
    
    Transfer dari TFM_StateText() di Utils.mqh.
    """
    if state.direction == DIR_NONE:
        return f"{tf_name} Wait"

    direction_str = direction_to_string(state.direction)
    marker = state_marker_text(state, candles, ema_values, use_ema_filter, is_new)

    return f"{tf_name} {direction_str}-{state.source}{marker}"


class TFMonitorStateManager:
    """
    Manages persistent state across poll cycles.
    Tracks H1, M15, M5 states, event key dedup, dan new markers.
    
    Mirror dari global state variables di Config.mqh.
    """

    def __init__(self):
        self.h1_state = clear_state()
        self.m15_state = clear_state()
        self.m5_state = clear_state()

        self.last_notified_h1 = clear_state()
        self.last_notified_m15 = clear_state()
        self.last_notified_m5 = clear_state()

        self.last_event_key = ""
        self.last_snapshot = ""
        self.has_snapshot = False

        self.h1_new = False
        self.m15_new = False
        self.m5_new = False

        # Per-TF last closed candle time tracking
        self.last_closed_time: dict[str, datetime | None] = {
            "H1": None, "M15": None, "M5": None,
        }
        self.state_ready: dict[str, bool] = {
            "H1": False, "M15": False, "M5": False,
        }

    def should_rescan(self, tf: str, last_candle_time: datetime | None) -> bool:
        """
        Cek apakah perlu re-scan TF ini.
        Re-scan hanya jika pertama kali ATAU candle closed berubah.
        Transfer dari TFM_UpdateStateByIndex() optimisasi scan.
        """
        if not self.state_ready.get(tf, False):
            return True
        if last_candle_time is None:
            return True
        return self.last_closed_time.get(tf) != last_candle_time

    def mark_scanned(self, tf: str, last_candle_time: datetime | None):
        """Tandai TF ini sudah di-scan."""
        self.last_closed_time[tf] = last_candle_time
        self.state_ready[tf] = True

    def detect_new_markers(self):
        """Deteksi mana state yang berubah dari notif terakhir."""
        self.h1_new = not state_equals(self.h1_state, self.last_notified_h1)
        self.m15_new = not state_equals(self.m15_state, self.last_notified_m15)
        self.m5_new = not state_equals(self.m5_state, self.last_notified_m5)

    def save_notified_states(self, event_key: str, snapshot: str):
        """Simpan state saat ini sebagai last notified."""
        self.last_notified_h1 = TFMState(
            direction=self.h1_state.direction,
            source=self.h1_state.source,
            time=self.h1_state.time,
            range_points=self.h1_state.range_points,
        )
        self.last_notified_m15 = TFMState(
            direction=self.m15_state.direction,
            source=self.m15_state.source,
            time=self.m15_state.time,
            range_points=self.m15_state.range_points,
        )
        self.last_notified_m5 = TFMState(
            direction=self.m5_state.direction,
            source=self.m5_state.source,
            time=self.m5_state.time,
            range_points=self.m5_state.range_points,
        )
        self.last_event_key = event_key
        self.last_snapshot = snapshot
        self.has_snapshot = True
