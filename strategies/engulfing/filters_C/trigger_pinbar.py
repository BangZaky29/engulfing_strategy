# =====================================================
# strategies/engulfing/filters_C/trigger_pinbar.py
# Trigger 04 — Pinbar
# =====================================================

from config.filter_c_config import FilterCConfig
from .f3_ema_utils import pass_ema_filter
from .trigger_utils import _get, _range_points, _body_points, _upper_wick_points, _lower_wick_points, _normalized_body

def is_bullish_pinbar(
    candles: list[dict], shift: int, point: float,
    ema_values: list[float], use_ema_filter: bool,
    cfg: FilterCConfig,
) -> bool:
    c1_open = _get(candles, shift, "open")
    c1_close = _get(candles, shift, "close")
    range_pts = _range_points(candles, shift, point)
    body_pts = _normalized_body(_body_points(candles, shift, point))
    upper_wick = _upper_wick_points(candles, shift, point)
    lower_wick = _lower_wick_points(candles, shift, point)

    if range_pts < cfg.pinbar_min_range_points:
        return False
    if lower_wick < (body_pts * cfg.pinbar_wick_body_multiplier):
        return False
    if upper_wick > body_pts:
        return False

    return pass_ema_filter(ema_values, shift, True, c1_open, c1_close, use_ema_filter)

def is_bearish_pinbar(
    candles: list[dict], shift: int, point: float,
    ema_values: list[float], use_ema_filter: bool,
    cfg: FilterCConfig,
) -> bool:
    c1_close = _get(candles, shift, "close")
    range_pts = _range_points(candles, shift, point)
    body_pts = _normalized_body(_body_points(candles, shift, point))
    upper_wick = _upper_wick_points(candles, shift, point)
    lower_wick = _lower_wick_points(candles, shift, point)

    if range_pts < cfg.pinbar_min_range_points:
        return False
    if upper_wick < (body_pts * cfg.pinbar_wick_body_multiplier):
        return False
    if lower_wick > body_pts:
        return False

    c1_open = _get(candles, shift, "open")
    return pass_ema_filter(ema_values, shift, True, c1_open, c1_close, use_ema_filter)
