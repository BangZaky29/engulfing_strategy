# =====================================================
# strategies/engulfing/filters_B/f1_trigger.py
# F1: Engulfing Trigger Validations
# =====================================================

from utils.colors import cprint, ok, no

def check_engulfing_trigger_b(
    c1_open: float, c1_close: float,
    c2_open: float, c2_close: float,
    c2_high: float, c2_low: float,
    c2_is_doji: bool,
    ema_slow: float,
    verbose: bool = False,
    color: str = "",
) -> tuple[bool, str | None]:
    """
    Cek syarat dasar Engulfing Trigger berdasarkan open & close.
    C1 = Candle Engulfing (Candle terakhir yg close)
    C2 = Candle yg ditelan (Candle sebelumnya)
    """
    c1_is_bullish = c1_close > c1_open
    c2_is_bullish = c2_close > c2_open

    # 1. Bullish Engulfing
    if not c2_is_bullish and c1_is_bullish:
        # C2 bearish, C1 bullish. C1 harus menelan C2 ke atas.
        # F1 Tambahan: C1 Close harus di atas EMA Slow
        if c2_is_doji:
            valid = c1_close > c2_high and c1_close > ema_slow
            msg = f"Trigger Bullish Engulfing (C2 Doji): C1 Close ({c1_close}) > C2 High ({c2_high})"
        else:
            valid = c1_close >= c2_open and c1_close > ema_slow
            msg = f"Trigger Bullish Engulfing: C1 Close ({c1_close}) >= C2 Open ({c2_open})"
            
        if verbose:
            result = ok() if valid else no()
            print(cprint(f"   [F1_B] {msg} & Close > EMA({ema_slow:.2f}) -> ", color) + result)
        if valid:
            return True, "bullish_engulfing"
            
    # 2. Bearish Engulfing
    elif c2_is_bullish and not c1_is_bullish:
        # C2 bullish, C1 bearish. C1 harus menelan C2 ke bawah.
        # F1 Tambahan: C1 Close harus di bawah EMA Slow
        if c2_is_doji:
            valid = c1_close < c2_low and c1_close < ema_slow
            msg = f"Trigger Bearish Engulfing (C2 Doji): C1 Close ({c1_close}) < C2 Low ({c2_low})"
        else:
            valid = c1_close <= c2_open and c1_close < ema_slow
            msg = f"Trigger Bearish Engulfing: C1 Close ({c1_close}) <= C2 Open ({c2_open})"
            
        if verbose:
            result = ok() if valid else no()
            print(cprint(f"   [F1_B] {msg} & Close < EMA({ema_slow:.2f}) -> ", color) + result)
        if valid:
            return True, "bearish_engulfing"
            
    else:
        if verbose:
            print(cprint("   [F1_B] Trigger: Warna C1 dan C2 sama atau bukan setup engulfing -> ", color) + no())

    return False, None
