# =====================================================
# strategies/engulfing/filters_C/trigger_scanner.py
# Scan semua trigger untuk mendapatkan state terbaru.
# =====================================================

from __future__ import annotations
from config.filter_c_config import FilterCConfig

from .trigger_utils import _range_points
from .trigger_engulfing import is_bullish_engulfing, is_bearish_engulfing
from .trigger_marubozu import is_bullish_marubozu, is_bearish_marubozu
from .trigger_ict import is_bullish_ict, is_bearish_ict
from .trigger_pinbar import is_bullish_pinbar, is_bearish_pinbar
from .trigger_dominan_break import check_dominan_break

# Direction Constants
DIR_NONE = 0
DIR_BUY = 1
DIR_SELL = -1
DIR_MIXED = 2

def get_trigger_state(
    candles: list[dict], shift: int, point: float,
    ema_values: list[float], cfg: FilterCConfig, tf: str
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

    if cfg.get_use_engulfing(tf):
        engulf_buy = is_bullish_engulfing(candles, shift, ema_values, use_ema)
        engulf_sell = is_bearish_engulfing(candles, shift, ema_values, use_ema)

    if cfg.get_use_marubozu(tf):
        marubozu_buy = is_bullish_marubozu(candles, shift, point, ema_values, use_ema, cfg)
        marubozu_sell = is_bearish_marubozu(candles, shift, point, ema_values, use_ema, cfg)

    if cfg.get_use_ict(tf):
        ict_buy = is_bullish_ict(candles, shift, ema_values, use_ema)
        ict_sell = is_bearish_ict(candles, shift, ema_values, use_ema)

    if cfg.get_use_pinbar(tf):
        pinbar_buy = is_bullish_pinbar(candles, shift, point, ema_values, use_ema, cfg)
        pinbar_sell = is_bearish_pinbar(candles, shift, point, ema_values, use_ema, cfg)

    if cfg.get_use_dominan_break(tf):
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
        if cfg.get_use_multi_trigger(tf):
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

def find_latest_trigger(
    candles: list[dict], point: float,
    ema_values: list[float], cfg: FilterCConfig, tf: str
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
    for shift in range(max_shift, 0, -1):
        state = get_trigger_state(candles, shift, point, ema_values, cfg, tf)
        if state is not None:
            found = state

    return found
