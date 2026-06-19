# =====================================================
# strategies/engulfing/filters/f1_trigger.py
# F1: Engulfing Trigger Validations
# =====================================================

from utils.colors import cprint, ok, no

def check_engulfing_trigger(
    c1_open: float, c1_close: float,
    c2_open: float, c2_close: float,
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
        valid = c1_close >= c2_open and c1_close > ema_slow
        if verbose:
            result = ok() if valid else no()
            print(cprint(
                f"   [F1] Trigger Bullish Engulfing: C1 Close ({c1_close}) >= C2 Open ({c2_open}) "
                f"& Close > EMA({ema_slow:.2f}) -> ", color
            ) + result)
        if valid:
            return True, "bullish_engulfing"
            
    # 2. Bearish Engulfing
    elif c2_is_bullish and not c1_is_bullish:
        # C2 bullish, C1 bearish. C1 harus menelan C2 ke bawah.
        # F1 Tambahan: C1 Close harus di bawah EMA Slow
        valid = c1_close <= c2_open and c1_close < ema_slow
        if verbose:
            result = ok() if valid else no()
            print(cprint(
                f"   [F1] Trigger Bearish Engulfing: C1 Close ({c1_close}) <= C2 Open ({c2_open}) "
                f"& Close < EMA({ema_slow:.2f}) -> ", color
            ) + result)
        if valid:
            return True, "bearish_engulfing"
            
    else:
        if verbose:
            print(cprint("   [F1] Trigger: Warna C1 dan C2 sama atau bukan setup engulfing -> ", color) + no())

    return False, None
