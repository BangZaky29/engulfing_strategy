# =====================================================
# strategies/engulfing/filters/f1_ring.py
# Filter [F1]: Panjang Ring C2 (dalam MT5 points)
#
# Konsep Ring:
#   Candle Hijau : ring = Close - Low   (0%=Close -> 100%=Low)
#   Candle Merah : ring = High  - Close (0%=Close -> 100%=High)
# =====================================================

from config.engulfing_config import EngulfingConfig


def check_ring_length(
    curr_close: float,
    curr_high: float,
    curr_low: float,
    curr_is_bullish: bool,
    point: float,
    digits: int,
    cfg: EngulfingConfig,
    verbose: bool = False,
) -> tuple[bool, int, float, str]:
    """
    Cek apakah panjang ring C2 memenuhi syarat minimal.

    Returns:
        (ok, c2_ring_pts, c2_ring_price, ring_formula)
        ok = True jika lolos filter
    """
    # Hitung ring sesuai warna candle
    if curr_is_bullish:
        c2_ring_price = curr_close - curr_low
        ring_formula  = "Close - Low"
    else:
        c2_ring_price = curr_high - curr_close
        ring_formula  = "High - Close"

    c2_ring_pts = round(c2_ring_price / point)
    ring_ok     = c2_ring_pts >= cfg.min_ring_points

    if verbose:
        status = "[OK]" if ring_ok else "[NO]"
        print(
            f"   {status} [F1] Ring ({ring_formula}): {c2_ring_pts} pts"
            f"  (harga: {c2_ring_price:.{digits}f})"
            f"  | min: {cfg.min_ring_points:.0f} pts"
        )
        if not ring_ok:
            print(
                f"   >> SKIP: ring terlalu pendek"
                f"  ({c2_ring_pts} pts < min {cfg.min_ring_points:.0f} pts)"
            )

    return ring_ok, c2_ring_pts, c2_ring_price, ring_formula
