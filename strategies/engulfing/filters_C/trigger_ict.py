# =====================================================
# strategies/engulfing/filters_C/trigger_ict.py
# Trigger 03 — ICT
# =====================================================

from .f3_ema_utils import pass_ema_filter
from .trigger_utils import _get

def is_bullish_ict(
    candles: list[dict], shift: int,
    ema_values: list[float], use_ema_filter: bool,
) -> bool:
    c1_open = _get(candles, shift, "open")
    c1_low = _get(candles, shift, "low")
    c1_close = _get(candles, shift, "close")
    c2_open = _get(candles, shift + 1, "open")
    c2_low = _get(candles, shift + 1, "low")
    c2_close = _get(candles, shift + 1, "close")

    c2_bearish = c2_close < c2_open
    low_break = c1_low < c2_low
    close_above_c2_open = c1_close > c2_open

    if not c2_bearish or not low_break or not close_above_c2_open:
        return False

    return pass_ema_filter(ema_values, shift, True, c1_open, c1_close, use_ema_filter)

def is_bearish_ict(
    candles: list[dict], shift: int,
    ema_values: list[float], use_ema_filter: bool,
) -> bool:
    c1_open = _get(candles, shift, "open")
    c1_high = _get(candles, shift, "high")
    c1_close = _get(candles, shift, "close")
    c2_open = _get(candles, shift + 1, "open")
    c2_high = _get(candles, shift + 1, "high")
    c2_close = _get(candles, shift + 1, "close")

    c2_bullish = c2_close > c2_open
    high_break = c1_high > c2_high
    close_below_c2_open = c1_close < c2_open

    if not c2_bullish or not high_break or not close_below_c2_open:
        return False

    return pass_ema_filter(ema_values, shift, False, c1_open, c1_close, use_ema_filter)
