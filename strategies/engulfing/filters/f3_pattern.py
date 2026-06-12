# =====================================================
# strategies/engulfing/filters/f3_pattern.py
# Filter [F3]: Pola Engulfing C1 -> C2
#
# F3a: Pasangan warna C1 -> C2 harus berlawanan
# F3b: C2 menelan body C1 (harga menelan)
# F3c: Engulf ratio >= min_body_ratio
# =====================================================

from config.engulfing_config import EngulfingConfig


def check_engulf_pattern(
    prev_open: float,
    prev_body: float,
    prev_is_bullish: bool,
    curr_open: float,
    curr_close: float,
    curr_body: float,
    curr_is_bullish: bool,
    point: float,
    digits: int,
    cfg: EngulfingConfig,
    verbose: bool = False,
) -> tuple[bool, str | None, float]:
    """
    Cek pola engulfing C1 -> C2 (warna, menelan, ratio).

    Returns:
        (ok, pattern_type, engulf_ratio)
        pattern_type = "bullish_engulfing" | "bearish_engulfing" | None
        ok = True jika semua kondisi terpenuhi
    """
    warna_c2 = "Hijau" if curr_is_bullish else "Merah"
    warna_c1 = "Hijau" if prev_is_bullish else "Merah"

    curr_body_pts = round(curr_body / point)
    prev_body_pts = round(prev_body / point)

    # --- [F3a] Pasangan warna C1 -> C2 ---
    pola_ok = (
        (not prev_is_bullish and curr_is_bullish) or  # Merah->Hijau
        (prev_is_bullish and not curr_is_bullish)      # Hijau->Merah
    )
    if verbose:
        status = "[OK]" if pola_ok else "[NO]"
        print(f"   {status} [F3a] Pasangan: C1={warna_c1} -> C2={warna_c2}")
    if not pola_ok:
        if verbose:
            print("   >> SKIP: C1 dan C2 warna sama, bukan pola engulfing")
        return False, None, 0.0

    # --- [F3b] Bullish: C2 menelan C1 ke atas ---
    if not prev_is_bullish and curr_is_bullish:
        menelan = curr_close > prev_open
        if verbose:
            status = "[OK]" if menelan else "[NO]"
            print(
                f"   {status} [F3b] Menelan BUY: Close_C2 ({curr_close:.{digits}f})"
                f" > Open_C1 ({prev_open:.{digits}f})"
            )
        if not menelan:
            if verbose:
                print("   >> SKIP: C2 tidak menelan body C1")
            return False, None, 0.0

        engulf_ratio = curr_body / prev_body if prev_body > 0 else 0
        engulf_ok    = engulf_ratio >= cfg.min_body_ratio
        if verbose:
            status = "[OK]" if engulf_ok else "[NO]"
            print(
                f"   {status} [F3c] Engulf ratio: {engulf_ratio:.2f}x"
                f"  (body_C2={curr_body_pts} pts / body_C1={prev_body_pts} pts)"
                f"  | min: {cfg.min_body_ratio}x"
            )
        if not engulf_ok:
            if verbose:
                print(
                    f"   >> SKIP: engulf ratio kurang"
                    f"  ({engulf_ratio:.2f}x < min {cfg.min_body_ratio}x)"
                )
            return False, None, engulf_ratio

        return True, "bullish_engulfing", engulf_ratio

    # --- [F3b] Bearish: C2 menelan C1 ke bawah ---
    elif prev_is_bullish and not curr_is_bullish:
        menelan = curr_close < prev_open
        if verbose:
            status = "[OK]" if menelan else "[NO]"
            print(
                f"   {status} [F3b] Menelan SELL: Close_C2 ({curr_close:.{digits}f})"
                f" < Open_C1 ({prev_open:.{digits}f})"
            )
        if not menelan:
            if verbose:
                print("   >> SKIP: C2 tidak menelan body C1")
            return False, None, 0.0

        engulf_ratio = curr_body / prev_body if prev_body > 0 else 0
        engulf_ok    = engulf_ratio >= cfg.min_body_ratio
        if verbose:
            status = "[OK]" if engulf_ok else "[NO]"
            print(
                f"   {status} [F3c] Engulf ratio: {engulf_ratio:.2f}x"
                f"  (body_C2={curr_body_pts} pts / body_C1={prev_body_pts} pts)"
                f"  | min: {cfg.min_body_ratio}x"
            )
        if not engulf_ok:
            if verbose:
                print(
                    f"   >> SKIP: engulf ratio kurang"
                    f"  ({engulf_ratio:.2f}x < min {cfg.min_body_ratio}x)"
                )
            return False, None, engulf_ratio

        return True, "bearish_engulfing", engulf_ratio

    return False, None, 0.0
