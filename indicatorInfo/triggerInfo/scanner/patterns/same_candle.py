"""Same Candle (streak) pattern detector."""

import os
from . import BasePattern, register_pattern


@register_pattern
class SameCandlePattern(BasePattern):
    """Deteksi continuous same-colored candles (streak)."""

    @property
    def name(self) -> str:
        return "SameCandle"

    @property
    def min_streak(self) -> int:
        """Minimum streak dari .env, default 8."""
        return int(os.getenv("SCANNER_SAME_CANDLE_MIN_STREAK", "8"))

    def detect(self, candle_data: dict, rates: list, point: float) -> list:
        """Deteksi streak candle warna sama.
        
        rates: list of candle dicts, latest first (sudah di-reverse dari MT5).
        """
        min_s = self.min_streak
        if len(rates) < min_s:
            return []

        c1 = rates[0]
        c1_is_bull = c1['close'] > c1['open']
        c1_is_bear = c1['close'] < c1['open']
        if not c1_is_bull and not c1_is_bear:
            return []  # Doji

        streak = 0
        for c in rates:
            is_bull = c['close'] > c['open']
            is_bear = c['close'] < c['open']
            if (c1_is_bull and is_bull) or (c1_is_bear and is_bear):
                streak += 1
            else:
                break

        if streak >= min_s:
            direction = "BUY" if c1_is_bull else "SELL"
            return [(direction, {"streak": streak})]
        return []
