"""Engulfing pattern detector."""

from . import BasePattern, register_pattern


@register_pattern
class EngulfingPattern(BasePattern):
    """Deteksi Bullish/Bearish Engulfing candle pattern."""

    @property
    def name(self) -> str:
        return "Engulfing"

    def detect(self, candle_data: dict, rates: list, point: float) -> list:
        c1_close, c1_open = candle_data["close_"], candle_data["open_"]
        c2_close, c2_open = candle_data["c2_close"], candle_data["c2_open"]
        c2_high, c2_low = candle_data["c2_high"], candle_data["c2_low"]

        c2_is_bear = c2_close < c2_open
        c2_is_bull = c2_close > c2_open
        c1_is_bull = c1_close > c1_open
        c1_is_bear = c1_close < c1_open

        body_pct = candle_data.get("body_pct", 0)

        if c2_is_bear and c1_is_bull and c1_close >= c2_high:
            return [("BUY", {"body_pct": round(body_pct, 1)})]
        if c2_is_bull and c1_is_bear and c1_close <= c2_low:
            return [("SELL", {"body_pct": round(body_pct, 1)})]
        return []
