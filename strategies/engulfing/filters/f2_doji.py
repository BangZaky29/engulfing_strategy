# =====================================================
# strategies/engulfing/filters/f2_doji.py
# Filter [F2]: Anti-Doji -- Ketebalan Body C2
#
# Logika:
#   Full Ring = High - Low   (100%)
#   Body      = |Close - Open|
#   Syarat    : Body / Full_Ring >= min_body_ring_pct (%)
# =====================================================

from config.engulfing_config import EngulfingConfig


def check_body_thickness(
    curr_body: float,
    curr_high: float,
    curr_low: float,
    point: float,
    digits: int,
    cfg: EngulfingConfig,
    verbose: bool = False,
) -> tuple[bool, float]:
    """
    Cek apakah body C2 cukup tebal (tidak Doji).

    Returns:
        (ok, body_ring_pct)
        ok = True jika lolos filter
    """
    c2_full_ring  = curr_high - curr_low
    c2_full_pts   = round(c2_full_ring / point)
    curr_body_pts = round(curr_body / point)

    body_ring_pct = (curr_body / c2_full_ring * 100) if c2_full_ring > 0 else 0.0
    body_ok       = body_ring_pct >= cfg.min_body_ring_pct

    if verbose:
        status = "[OK]" if body_ok else "[NO]"
        print(
            f"   {status} [F2] Body%: {body_ring_pct:.1f}%"
            f"  (body={curr_body_pts} pts / full_ring={c2_full_pts} pts)"
            f"  | min: {cfg.min_body_ring_pct:.0f}%"
        )
        if not body_ok:
            print(
                f"   >> SKIP: body terlalu tipis / Doji"
                f"  ({body_ring_pct:.1f}% < min {cfg.min_body_ring_pct:.0f}%)"
            )

    return body_ok, body_ring_pct
