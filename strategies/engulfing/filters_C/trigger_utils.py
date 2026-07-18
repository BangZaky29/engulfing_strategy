# =====================================================
# strategies/engulfing/filters_C/trigger_utils.py
# Helper functions for trigger calculation.
# =====================================================

def _get(candles: list[dict], shift: int, key: str) -> float:
    """Ambil OHLC value pada shift tertentu."""
    idx = len(candles) - shift
    if idx < 0 or idx >= len(candles):
        return 0.0
    return float(candles[idx].get(key, 0.0))

def _range_points(candles: list[dict], shift: int, point: float) -> float:
    high = _get(candles, shift, "high")
    low = _get(candles, shift, "low")
    if point <= 0:
        return 0.0
    return (high - low) / point

def _body_points(candles: list[dict], shift: int, point: float) -> float:
    open_ = _get(candles, shift, "open")
    close = _get(candles, shift, "close")
    if point <= 0:
        return 0.0
    return abs(close - open_) / point

def _upper_wick_points(candles: list[dict], shift: int, point: float) -> float:
    open_ = _get(candles, shift, "open")
    close = _get(candles, shift, "close")
    high = _get(candles, shift, "high")
    body_top = max(open_, close)
    if point <= 0:
        return 0.0
    return (high - body_top) / point

def _lower_wick_points(candles: list[dict], shift: int, point: float) -> float:
    open_ = _get(candles, shift, "open")
    close = _get(candles, shift, "close")
    low = _get(candles, shift, "low")
    body_bottom = min(open_, close)
    if point <= 0:
        return 0.0
    return (body_bottom - low) / point

def _normalized_body(body_pts: float) -> float:
    return body_pts if body_pts > 0.0 else 1.0

def _get_avg_previous_range(
    candles: list[dict], shift: int, count: int, point: float,
) -> float | None:
    """Return average range (points) dari `count` candle sebelum shift."""
    if count <= 0:
        count = 1
    if len(candles) <= shift + count:
        return None

    total = 0.0
    for i in range(1, count + 1):
        r = _range_points(candles, shift + i, point)
        if r <= 0.0:
            return None
        total += r

    return total / count
