"""Marubozu pattern detector."""

import os
from . import BasePattern, register_pattern


@register_pattern
class MarubozuPattern(BasePattern):
    """Deteksi Marubozu candle pattern (candle dengan body besar, shadow kecil)."""

    @property
    def name(self) -> str:
        return "Marubozu"

    @property
    def min_body_pct(self) -> float:
        """Minimum body percentage dari .env, default 90%."""
        return float(os.getenv("SCANNER_MARUBOZU_MIN_BODY_PCT", "90"))

    def detect(self, candle_data: dict, rates: list, point: float) -> list:
        body_pct = candle_data.get("body_pct", 0)
        if body_pct < self.min_body_pct:
            return []

        c1_close, c1_open = candle_data["close_"], candle_data["open_"]

        if c1_close > c1_open:
            return [("BUY", {"body_pct": round(body_pct, 1)})]
        if c1_close < c1_open:
            return [("SELL", {"body_pct": round(body_pct, 1)})]
        return []
