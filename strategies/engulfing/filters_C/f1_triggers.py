# =====================================================
# strategies/engulfing/filters_C/f1_triggers.py
# 5 Trigger Detectors: Engulfing, Marubozu, ICT, Pinbar, Dominan Break
# Transfer 1:1 dari TriggerLogic.mqh
# =====================================================

from __future__ import annotations
from config.filter_c_config import FilterCConfig
from .f3_ema_utils import pass_ema_filter, get_ema_value

# =====================================================
# Direction Constants
# =====================================================
DIR_NONE = 0
DIR_BUY = 1
DIR_SELL = -1
DIR_MIXED = 2


# =====================================================
# Candle Helper Functions
# Candles = list of dict, index 0 = oldest, -1 = newest
# shift=1 = last closed candle, shift=2 = before that, dst.
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


# =====================================================
# Trigger 01 — Engulfing
# C2 bearish, C1 bullish, Close C1 >= Open C2 (Buy)
# C2 bullish, C1 bearish, Close C1 <= Open C2 (Sell)
# =====================================================
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


# =====================================================
# Trigger 02 — Marubozu
# Bullish: wick ≤ buffer, range ≥ multiplier × avg previous range
# =====================================================
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


# =====================================================
# Trigger 03 — ICT
# Buy: C2 bearish, C1 low < C2 low, C1 close > C2 open
# Sell: C2 bullish, C1 high > C2 high, C1 close < C2 open
# =====================================================
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


# =====================================================
# Trigger 04 — Pinbar
# Buy: lower_wick >= 4x body, upper_wick <= body, range >= 600pts
# Sell: upper_wick >= 4x body, lower_wick <= body, range >= 600pts
# =====================================================
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


# =====================================================
# Trigger 05 — Dominan Break (DB)
# Master candle: candle paling besar/dominan.
# Buy  = close break > High Master (candle ke-3 sampai ke-20)
# Sell = close break < Low Master
# Break candle ke-2 TIDAK valid.
# =====================================================
def check_dominan_break(
    candles: list[dict], shift: int, point: float,
    ema_values: list[float], use_ema_filter: bool,
    cfg: FilterCConfig,
) -> tuple[int, int]:
    """
    Return (direction, break_number).
    direction = DIR_NONE jika tidak ada DB.
    """
    if not cfg.use_dominan_break:
        return DIR_NONE, 0

    min_candles = max(cfg.db_min_candles, 3)
    max_candles = max(cfg.db_max_candles, min_candles)

    total_bars = len(candles)
    if total_bars <= shift + max_candles + 2:
        max_candles = total_bars - shift - 3
    if max_candles < min_candles:
        return DIR_NONE, 0

    buffer = cfg.db_buffer_points * point
    break_close = _get(candles, shift, "close")
    if break_close <= 0.0:
        return DIR_NONE, 0

    # Scan dari max ke min → pilih base paling panjang/solid
    for count in range(max_candles, min_candles - 1, -1):
        master_shift = shift + count
        master_high = _get(candles, master_shift, "high")
        master_low = _get(candles, master_shift, "low")

        if master_high <= 0.0 or master_low <= 0.0:
            continue

        buy_break = break_close > (master_high + buffer)
        sell_break = break_close < (master_low - buffer)

        if not buy_break and not sell_break:
            continue

        # Cek semua candle antara master dan break masih inside range
        previous_inside = True
        for i in range(1, count):
            c = _get(candles, shift + i, "close")
            if c <= 0.0:
                previous_inside = False
                break
            if c > (master_high + buffer) or c < (master_low - buffer):
                previous_inside = False
                break

        if not previous_inside:
            continue

        break_open = _get(candles, shift, "open")

        if buy_break:
            if pass_ema_filter(ema_values, shift, True, break_open, break_close, use_ema_filter):
                return DIR_BUY, count

        if sell_break:
            if pass_ema_filter(ema_values, shift, False, break_open, break_close, use_ema_filter):
                return DIR_SELL, count

    return DIR_NONE, 0


# =====================================================
# Master Orchestrator: Get Trigger State on Shift
# =====================================================
def get_trigger_state(
    candles: list[dict], shift: int, point: float,
    ema_values: list[float], cfg: FilterCConfig,
) -> dict | None:
    """
    Scan semua 5 trigger pada shift tertentu.
    Return dict {direction, source, time, range_points} atau None.
    
    Transfer dari TFM_GetTriggerStateOnShift() di TriggerLogic.mqh.
    """
    if shift < 1 or shift >= len(candles):
        return None

    # Ambil waktu candle
    idx = len(candles) - shift
    signal_time = candles[idx].get("time")
    if not signal_time:
        return None

    use_ema = cfg.use_ema_filter

    engulf_buy = engulf_sell = False
    marubozu_buy = marubozu_sell = False
    ict_buy = ict_sell = False
    pinbar_buy = pinbar_sell = False
    db_buy = db_sell = False
    db_number = 0

    if cfg.use_engulfing:
        engulf_buy = is_bullish_engulfing(candles, shift, ema_values, use_ema)
        engulf_sell = is_bearish_engulfing(candles, shift, ema_values, use_ema)

    if cfg.use_marubozu:
        marubozu_buy = is_bullish_marubozu(candles, shift, point, ema_values, use_ema, cfg)
        marubozu_sell = is_bearish_marubozu(candles, shift, point, ema_values, use_ema, cfg)

    if cfg.use_ict:
        ict_buy = is_bullish_ict(candles, shift, ema_values, use_ema)
        ict_sell = is_bearish_ict(candles, shift, ema_values, use_ema)

    if cfg.use_pinbar:
        pinbar_buy = is_bullish_pinbar(candles, shift, point, ema_values, use_ema, cfg)
        pinbar_sell = is_bearish_pinbar(candles, shift, point, ema_values, use_ema, cfg)

    if cfg.use_dominan_break:
        db_dir, db_num = check_dominan_break(candles, shift, point, ema_values, use_ema, cfg)
        db_buy = db_dir == DIR_BUY
        db_sell = db_dir == DIR_SELL
        db_number = db_num

    # Hitung total valid triggers
    total_valid = 0
    if engulf_buy or engulf_sell:
        total_valid += 1
    if marubozu_buy or marubozu_sell:
        total_valid += 1
    if ict_buy or ict_sell:
        total_valid += 1
    if pinbar_buy or pinbar_sell:
        total_valid += 1
    if db_buy or db_sell:
        total_valid += 1

    if total_valid <= 0:
        return None

    any_buy = engulf_buy or marubozu_buy or ict_buy or pinbar_buy or db_buy
    any_sell = engulf_sell or marubozu_sell or ict_sell or pinbar_sell or db_sell

    if any_buy and not any_sell:
        direction = DIR_BUY
    elif any_sell and not any_buy:
        direction = DIR_SELL
    else:
        direction = DIR_MIXED

    # Build trigger label
    parts = []
    if engulf_buy or engulf_sell:
        parts.append("Engulfing")
    if marubozu_buy or marubozu_sell:
        parts.append("Marubozu")
    if ict_buy or ict_sell:
        parts.append("ICT")
    if pinbar_buy or pinbar_sell:
        parts.append("Pinbar")
    if db_buy or db_sell:
        parts.append(f"DB-{db_number}")

    trigger_list = "+".join(parts)
    source = trigger_list

    if total_valid > 1:
        if cfg.use_multi_trigger:
            source = "Multi:" + trigger_list
        else:
            # Priority: Engulfing > Marubozu > ICT > Pinbar > DB
            if engulf_buy or engulf_sell:
                source = "Engulfing"
                direction = DIR_BUY if engulf_buy else DIR_SELL
            elif marubozu_buy or marubozu_sell:
                source = "Marubozu"
                direction = DIR_BUY if marubozu_buy else DIR_SELL
            elif ict_buy or ict_sell:
                source = "ICT"
                direction = DIR_BUY if ict_buy else DIR_SELL
            elif pinbar_buy or pinbar_sell:
                source = "Pinbar"
                direction = DIR_BUY if pinbar_buy else DIR_SELL
            elif db_buy or db_sell:
                source = f"DB-{db_number}"
                direction = DIR_BUY if db_buy else DIR_SELL

    return {
        "direction": direction,
        "source": source,
        "time": signal_time,
        "range_points": _range_points(candles, shift, point),
    }


# =====================================================
# Find Latest Trigger State
# Scan dari lookback, return state terbaru.
# Transfer dari TFM_FindLatestTriggerState()
# =====================================================
def find_latest_trigger(
    candles: list[dict], point: float,
    ema_values: list[float], cfg: FilterCConfig,
) -> dict | None:
    """
    Scan semua shift dari lookback ke shift=1.
    Return trigger state terbaru (paling dekat ke sekarang).
    """
    total_bars = len(candles)
    if total_bars < 10:
        return None

    max_shift = cfg.trigger_lookback_bars
    extra = max(cfg.marubozu_compare_candles, cfg.db_max_candles)
    max_allowed = total_bars - extra - 2
    max_shift = min(max_shift, max_allowed)

    if max_shift < 1:
        return None

    found = None
    # Scan dari jauh ke dekat, terus override → akhirnya dapat yang paling baru
    for shift in range(max_shift, 0, -1):
        state = get_trigger_state(candles, shift, point, ema_values, cfg)
        if state is not None:
            found = state

    return found
