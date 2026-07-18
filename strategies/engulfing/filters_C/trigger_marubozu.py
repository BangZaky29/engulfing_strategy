# =====================================================
# strategies/engulfing/filters_C/trigger_marubozu.py
# Trigger 02 — Marubozu
# =====================================================

from config.filter_c_config import FilterCConfig
from .f3_ema_utils import pass_ema_filter
from .trigger_utils import _get, _range_points, _upper_wick_points, _lower_wick_points, _get_avg_previous_range

def is_bullish_marubozu(
    candles: list[dict], shift: int, point: float,
    ema_values: list[float], use_ema_filter: bool,
    cfg: FilterCConfig,
) -> bool:
    c1_open = _get(candles, shift, "open")
    c1_close = _get(candles, shift, "close")

    if c1_close <= c1_open:
        return False

    range_pts = _range_points(candles, shift, point)
    upper_wick = _upper_wick_points(candles, shift, point)
    lower_wick = _lower_wick_points(candles, shift, point)

    if upper_wick > cfg.marubozu_wick_buffer_points:
        return False
    if lower_wick > cfg.marubozu_wick_buffer_points:
        return False

    avg_range = _get_avg_previous_range(candles, shift, cfg.marubozu_compare_candles, point)
    if avg_range is None:
        return False
    if range_pts < (avg_range * cfg.marubozu_range_multiplier):
        return False

    return pass_ema_filter(ema_values, shift, True, c1_open, c1_close, use_ema_filter)

def is_bearish_marubozu(
    candles: list[dict], shift: int, point: float,
    ema_values: list[float], use_ema_filter: bool,
    cfg: FilterCConfig,
) -> bool:
    c1_open = _get(candles, shift, "open")
    c1_close = _get(candles, shift, "close")

    if c1_close >= c1_open:
        return False

    range_pts = _range_points(candles, shift, point)
    upper_wick = _upper_wick_points(candles, shift, point)
    lower_wick = _lower_wick_points(candles, shift, point)

    if upper_wick > cfg.marubozu_wick_buffer_points:
        return False
    if lower_wick > cfg.marubozu_wick_buffer_points:
        return False

    avg_range = _get_avg_previous_range(candles, shift, cfg.marubozu_compare_candles, point)
    if avg_range is None:
        return False
    if range_pts < (avg_range * cfg.marubozu_range_multiplier):
        return False

    return pass_ema_filter(ema_values, shift, False, c1_open, c1_close, use_ema_filter)
