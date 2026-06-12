# =====================================================
# strategies/engulfing/filters/f1_ring.py
# Filter [F1]: Panjang Ring C2 (dalam MT5 points)
#
# Konsep Ring:
#   Candle Merah : ring = High  - Close (ekor atas)
#   Candle Hijau : ring = Close - Low   (ekor bawah)
#
# Syarat:
#   min_ring_points <= ring <= max_ring_points
#   Jika terlalu pendek → SKIP (bukan engulfing valid)
#   Jika terlalu panjang → SKIP (candle terlalu volatile)
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
    Cek apakah panjang ring C2 memenuhi syarat minimal & maksimal.

    Returns:
        (ok, c2_ring_pts, c2_ring_price, ring_formula)
        ok = True jika lolos filter (min <= ring <= max)
    """
    # Hitung ring sesuai warna candle
    if curr_is_bullish:
        c2_ring_price = curr_close - curr_low
        ring_formula  = "Close - Low"
    else:
        c2_ring_price = curr_high - curr_close
        ring_formula  = "High - Close"

    c2_ring_pts = round(c2_ring_price / point)

    too_short = c2_ring_pts < cfg.min_ring_points
    too_long  = c2_ring_pts > cfg.max_ring_points
    ring_ok   = not too_short and not too_long

    if verbose:
        status = "[OK]" if ring_ok else "[NO]"
        print(
            f"   {status} [F1] Ring ({ring_formula}): {c2_ring_pts} pts"
            f"  (harga: {c2_ring_price:.{digits}f})"
            f"  | min: {cfg.min_ring_points:.0f} pts"
            f"  | max: {cfg.max_ring_points:.0f} pts"
        )
        if too_short:
            print(
                f"   >> SKIP: ring terlalu pendek"
                f"  ({c2_ring_pts} pts < min {cfg.min_ring_points:.0f} pts)"
            )
        elif too_long:
            print(
                f"   >> SKIP: ring terlalu panjang / volatile"
                f"  ({c2_ring_pts} pts > max {cfg.max_ring_points:.0f} pts)"
            )

    return ring_ok, c2_ring_pts, c2_ring_price, ring_formula
