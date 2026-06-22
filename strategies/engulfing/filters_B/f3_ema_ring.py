# strategies/engulfing/filters_B/f3_ema_ring.py
# F3_B: EMA Ring Filter — Validasi seluruh range C1 & C2 terhadap EMA_20

from utils.colors import Colors, cprint

def check_ema_ring_b(
    c1_high: float, c1_low: float,
    c2_high: float, c2_low: float,
    ema_20: float,
    pattern_type: str,
    verbose: bool = False,
    color: str = "",
) -> bool:
    """
    Validasi: Seluruh range (high-low) candle C1 dan C2 harus
    BENAR-BENAR berada di satu sisi EMA_20.
    Candle yang cross atau menyentuh EMA_20 -> INVALID.
    """
    if pattern_type == "bullish_engulfing":
        # Semua harga harus di atas EMA
        valid = (c1_low > ema_20) and (c2_low > ema_20)
        if verbose:
            if valid:
                print(cprint(f"   [F3_B] EMA Ring: C1 Low ({c1_low:.5f}) > EMA ({ema_20:.5f}) ✅ | C2 Low ({c2_low:.5f}) > EMA ({ema_20:.5f}) ✅ -> OK", color))
            else:
                print(cprint(f"   [F3_B] EMA Ring: C1 Low ({c1_low:.5f}) atau C2 Low ({c2_low:.5f}) touch/cross EMA ({ema_20:.5f}) -> SKIP ❌", Colors.YELLOW))
    else:
        # Semua harga harus di bawah EMA
        valid = (c1_high < ema_20) and (c2_high < ema_20)
        if verbose:
            if valid:
                print(cprint(f"   [F3_B] EMA Ring: C1 High ({c1_high:.5f}) < EMA ({ema_20:.5f}) ✅ | C2 High ({c2_high:.5f}) < EMA ({ema_20:.5f}) ✅ -> OK", color))
            else:
                print(cprint(f"   [F3_B] EMA Ring: C1 High ({c1_high:.5f}) atau C2 High ({c2_high:.5f}) touch/cross EMA ({ema_20:.5f}) -> SKIP ❌", Colors.YELLOW))
    return valid
