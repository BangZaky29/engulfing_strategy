# =====================================================
# strategies/engulfing/filters_C/trigger_engulfing.py
# Trigger 01 — Engulfing
# =====================================================

from .f3_ema_utils import pass_ema_filter
from .trigger_utils import _get

def is_bullish_engulfing(
    candles: list[dict], shift: int,
    ema_values: list[float], use_ema_filter: bool,
) -> bool:
    c1_open = _get(candles, shift, "open")
    c1_close = _get(candles, shift, "close")
    c2_open = _get(candles, shift + 1, "open")
    c2_close = _get(candles, shift + 1, "close")

    c2_bearish = c2_close < c2_open
    c1_bullish = c1_close > c1_open
    engulf = c1_close >= c2_open

    if not c2_bearish or not c1_bullish or not engulf:
        return False

    return pass_ema_filter(ema_values, shift, True, c1_open, c1_close, use_ema_filter)

def is_bearish_engulfing(
    candles: list[dict], shift: int,
    ema_values: list[float], use_ema_filter: bool,
) -> bool:
    c1_open = _get(candles, shift, "open")
    c1_close = _get(candles, shift, "close")
    c2_open = _get(candles, shift + 1, "open")
    c2_close = _get(candles, shift + 1, "close")

    c2_bullish = c2_close > c2_open
    c1_bearish = c1_close < c1_open
    engulf = c1_close <= c2_open

    if not c2_bullish or not c1_bearish or not engulf:
        return False

    return pass_ema_filter(ema_values, shift, False, c1_open, c1_close, use_ema_filter)
