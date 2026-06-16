# =====================================================
# strategies/engulfing/filters/f3_pattern.py
# F3: Pattern (Ring Size) Filter & Dynamic RR
# =====================================================

from config.engulfing_config import EngulfingConfig

def check_pattern_size(
    c1_high: float,
    c1_low: float,
    point: float,
    cfg: EngulfingConfig,
    verbose: bool = False
) -> tuple[bool, float]:
    """
    Validasi ukuran (Ring) C1 dalam poin.
    Jika di luar batas MIN dan MAX -> Reject.
    Jika lolos -> Tentukan RR Ratio.
    """
    if point <= 0:
        if verbose: print("   [F3] Point = 0, bypass filter.")
        return True, 1.5

    c1_points = (c1_high - c1_low) / point

    if c1_points < cfg.min_ring_c1_points:
        if verbose:
            print(f"   [F3] Pattern Size: C1 terlalu kecil ({c1_points:.1f} pts < {cfg.min_ring_c1_points} pts) -> [REJECT]")
        return False, 0.0

    if c1_points > cfg.max_ring_c1_points:
        if verbose:
            print(f"   [F3] Pattern Size: C1 raksasa ({c1_points:.1f} pts > {cfg.max_ring_c1_points} pts) -> [REJECT]")
        return False, 0.0

    # Tentukan RR secara adaptif berdasarkan Range Poin C1
    rr_ratio = 1.0 # Default fallback
    if c1_points <= cfg.normal_ring_c1_points:
        # Ring Kecil: 100 - 250
        rr_ratio = 2.0
        ring_cat = "Kecil"
    elif c1_points <= cfg.large_ring_c1_points:
        # Ring Normal: 251 - 450
        rr_ratio = 1.5
        ring_cat = "Normal"
    else:
        # Ring Besar: 451 - 1500
        rr_ratio = 1.0
        ring_cat = "Besar"

    if verbose:
        print(f"   [F3] Pattern Size: {c1_points:.1f} pts (Ring {ring_cat}) -> RR: {rr_ratio:.1f}")

    return True, rr_ratio
