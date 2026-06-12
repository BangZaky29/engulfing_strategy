# =====================================================
# strategies/engulfing/filters/f4_ema.py
# Filter [F4]: EMA Position Filter
#
# Syarat OP berdasarkan posisi Close C2 vs EMA:
#   BUY  : Close C2 > EMA  (Close sudah di atas EMA)
#   SELL : Close C2 < EMA  (Close sudah di bawah EMA)
#
# Visualisasi SELL VALID:
#   | Open  | <- Open boleh di atas EMA
#   - EMA  -   <- EMA motong body = MASIH VALID
#   | Close | <- Close di bawah EMA = syarat terpenuhi
#
# Visualisasi SELL TIDAK VALID:
#   | Open  |
#   | Close | <- Close masih di atas EMA
#   - EMA  -   <- EMA di bawah seluruh body = TIDAK VALID
# =====================================================

from config.engulfing_config import EngulfingConfig


def check_ema_position(
    pattern_type: str,
    curr_close: float,
    ema_fast: float,
    ema_slow: float,
    digits: int,
    cfg: EngulfingConfig,
    verbose: bool = False,
) -> bool:
    """
    Cek apakah Close C2 berada di sisi yang benar terhadap EMA.

    BUY  -> Close C2 > EMA referensi
    SELL -> Close C2 < EMA referensi

    Returns:
        True jika lolos filter (atau filter di-disable)
    """
    if not cfg.ema_filter_enabled:
        if verbose:
            print("   [--] [F4] EMA Filter: DISABLED")
        return True

    ema_ref   = ema_slow if cfg.ema_filter_source == "slow" else ema_fast
    ema_label = f"EMA_{cfg.ema_filter_source.upper()}"

    if pattern_type == "bullish_engulfing":
        # BUY: Close harus > EMA
        ema_pos_ok = curr_close > ema_ref
        if verbose:
            status  = "[OK]" if ema_pos_ok else "[NO]"
            cmp_sym = ">"    if ema_pos_ok else "<="
            verdict = "VALID" if ema_pos_ok else "DITOLAK"
            print(
                f"   {status} [F4] EMA Filter ({ema_label}={ema_ref:.{digits}f}): "
                f"Close_C2 ({curr_close:.{digits}f}) {cmp_sym} {ema_label} "
                f"-> BUY {verdict}"
            )
            if not ema_pos_ok:
                print(f"   >> SKIP: Close C2 <= {ema_label} -> BUY tidak diizinkan")
        return ema_pos_ok

    elif pattern_type == "bearish_engulfing":
        # SELL: Close harus < EMA
        ema_pos_ok = curr_close < ema_ref
        if verbose:
            status  = "[OK]" if ema_pos_ok else "[NO]"
            cmp_sym = "<"    if ema_pos_ok else ">="
            verdict = "VALID" if ema_pos_ok else "DITOLAK"
            print(
                f"   {status} [F4] EMA Filter ({ema_label}={ema_ref:.{digits}f}): "
                f"Close_C2 ({curr_close:.{digits}f}) {cmp_sym} {ema_label} "
                f"-> SELL {verdict}"
            )
            if not ema_pos_ok:
                print(f"   >> SKIP: Close C2 >= {ema_label} -> SELL tidak diizinkan")
        return ema_pos_ok

    return True
