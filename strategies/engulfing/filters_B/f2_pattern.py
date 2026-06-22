# =====================================================
# strategies/engulfing/filters_B/f2_pattern.py
# F2: Ring Size Validation (Filter B)
# =====================================================

from config.engulfing_config import EngulfingConfig
from utils.colors import cprint, ok, no

def check_pattern_size_b(
    c1_high: float, c1_low: float,
    point: float,
    symbol: str,
    cfg: EngulfingConfig,
    verbose: bool = False,
    color: str = "",
) -> bool:
    """
    Cek syarat ukuran Engulfing Pattern (C1 Range)
    Range harus berada di antara MIN_RING_C1_POINTS_B dan MAX_RING_C1_POINTS_B.
    """
    if point == 0:
        return False
        
    c1_points = abs(c1_high - c1_low) / point
    min_ring, max_ring = cfg.get_ring_size_b(symbol)

    if c1_points < min_ring:
        if verbose:
            print(cprint(
                f"   [F2_B] {symbol} Pattern Size: {c1_points:.1f} pts < Min ({min_ring}) -> ",
                color
            ) + no())
        return False
        
    if c1_points > max_ring:
        if verbose:
            print(cprint(
                f"   [F2_B] {symbol} Pattern Size: {c1_points:.1f} pts > Max ({max_ring}) -> ",
                color
            ) + no())
        return False

    if verbose:
        print(cprint(
            f"   [F2_B] {symbol} Pattern Size: {c1_points:.1f} pts (Valid Range {min_ring}-{max_ring}) -> ",
            color
        ) + ok())

    return True
