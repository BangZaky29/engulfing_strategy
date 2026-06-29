# =====================================================
# strategies/engulfing/filters_C/f3_ema_utils.py
# EMA calculation, filter, dan relation text
# Transfer dari Utils.mqh (bagian EMA)
# =====================================================

from __future__ import annotations
from config.filter_c_config import FilterCConfig


def calculate_ema_series(closes: list[float], period: int) -> list[float]:
    """
    Hitung EMA series dari list close prices.
    Index 0 = oldest, index -1 = newest.
    Return list EMA values dengan panjang sama.
    """
    if not closes or period <= 0:
        return []

    ema_values = [0.0] * len(closes)
    multiplier = 2.0 / (period + 1)

    # Seed EMA dengan SMA dari period pertama
    if len(closes) < period:
        sma = sum(closes) / len(closes)
        ema_values[0] = sma
        start = 1
    else:
        sma = sum(closes[:period]) / period
        for i in range(period):
            ema_values[i] = sma
        start = period

    for i in range(start, len(closes)):
        ema_values[i] = (closes[i] - ema_values[i - 1]) * multiplier + ema_values[i - 1]

    return ema_values


def get_ema_value(ema_values: list[float], shift: int) -> float:
    """
    Ambil EMA value pada shift tertentu.
    shift=1 = candle closed terakhir, shift=2 = sebelumnya, dst.
    ema_values index 0 = oldest, -1 = newest.
    """
    if not ema_values or shift < 0:
        return 0.0

    # shift=1 → index = len-1, shift=2 → index = len-2
    idx = len(ema_values) - shift
    if idx < 0 or idx >= len(ema_values):
        return 0.0

    return ema_values[idx]


def pass_ema_filter(
    ema_values: list[float],
    shift: int,
    is_buy: bool,
    open_price: float,
    close_price: float,
    use_ema_filter: bool,
) -> bool:
    """
    Cek apakah trigger lolos EMA filter.
    Jika use_ema_filter=False, selalu return True (semua trigger tampil).
    Jika use_ema_filter=True, filter trigger yang melawan EMA.

    Untuk validasi OP di M5, baik open maupun close harus berada di satu sisi EMA.
    Jika candle body (open-close) cross EMA, trigger tidak valid.
    """
    if not use_ema_filter:
        return True

    ema_val = get_ema_value(ema_values, shift)
    if ema_val <= 0.0:
        return False

    if is_buy:
        return open_price > ema_val and close_price > ema_val
    else:
        return open_price < ema_val and close_price < ema_val


def ema_relation_text(
    direction: int,
    close_price: float,
    ema_value: float,
    use_ema_filter: bool,
) -> str:
    """
    Return "Trend" atau "Rev" berdasarkan relasi trigger vs EMA.
    
    Transfer dari TFM_EMARelationText() di Utils.mqh.
    
    Jika UseEMAFilter=True → semua trigger yang lolos pasti Trend.
    Jika UseEMAFilter=False → cek posisi close vs EMA.
    """
    DIR_BUY = 1
    DIR_SELL = -1

    if direction != DIR_BUY and direction != DIR_SELL:
        return ""

    # Jika EMA filter ON, trigger yang lolos pasti searah EMA
    if use_ema_filter:
        return "Trend"

    if ema_value <= 0.0:
        return ""

    if direction == DIR_BUY:
        is_trend = close_price > ema_value
    else:
        is_trend = close_price < ema_value

    return "Trend" if is_trend else "Rev"
