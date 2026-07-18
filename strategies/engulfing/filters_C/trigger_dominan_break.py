# =====================================================
# strategies/engulfing/filters_C/trigger_dominan_break.py
# Trigger 05 — Dominan Break (DB)
# =====================================================

from config.filter_c_config import FilterCConfig
from .f3_ema_utils import pass_ema_filter
from .trigger_utils import _get

# Direction Constants local
DIR_NONE = 0
DIR_BUY = 1
DIR_SELL = -1

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
