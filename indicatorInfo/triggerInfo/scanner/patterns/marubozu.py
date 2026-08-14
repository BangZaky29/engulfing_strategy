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
            c1_pips = int(round((c1_close - candle_data["low_"]) / point)) if point > 0 else 0
            return [("BUY", {"body_pct": round(body_pct, 1), "c1_pips": c1_pips})]
        if c1_close < c1_open:
            c1_pips = int(round((candle_data["high_"] - c1_close) / point)) if point > 0 else 0
            return [("SELL", {"body_pct": round(body_pct, 1), "c1_pips": c1_pips})]
        return []
