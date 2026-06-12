# =====================================================
# strategies/engulfing/detector.py
# Orchestrator: jalankan semua filter secara berurutan
#
# Urutan Filter:
#   [F1] Ring Length   -> f1_ring.py
#   [F2] Anti-Doji     -> f2_doji.py
#   [F3] Pola Engulf   -> f3_pattern.py  (warna + menelan + ratio)
#   [F4] EMA Position  -> f4_ema.py
# =====================================================

from config.engulfing_config import EngulfingConfig
from .filters import (
    check_ring_length,
    check_body_thickness,
    check_engulf_pattern,
    check_ema_position,
)
from .signal_builder import build_signal


def detect_engulfing(
    candle_data: dict,
    cfg: EngulfingConfig = None,
    verbose: bool = False,
) -> dict | None:
    """
    Jalankan semua filter secara berurutan.
    Return sinyal jika semua filter lolos, None jika gagal.
    """
    if cfg is None:
        cfg = EngulfingConfig()

    # --- Unpack data ---
    prev_open       = candle_data["prev_open"]
    prev_is_bullish = candle_data["prev_is_bullish"]
    prev_body       = candle_data["prev_body_size"]

    curr_open       = candle_data["open_"]
    curr_close      = candle_data["close_"]
    curr_high       = candle_data["high_"]
    curr_low        = candle_data["low_"]
    curr_is_bullish = candle_data["is_bullish"]
    curr_body       = candle_data["body_size"]

    ema_fast        = candle_data["ema_fast"]
    ema_slow        = candle_data["ema_slow"]

    point  = candle_data.get("point", 0.01)
    digits = candle_data.get("digits", 2)

    warna_c2 = "Hijau [BUY]"  if curr_is_bullish else "Merah [SELL]"
    warna_c1 = "Hijau [BUY]"  if prev_is_bullish else "Merah [SELL]"

    # --- Header verbose ---
    if verbose:
        print(f"   {'-'*52}")
        print(f"   [FILTER] C2={warna_c2}  C1={warna_c1}")
        print(f"   {'-'*52}")

    # -----------------------------------------------------------------
    # [F1] Ring Length: panjang ring C2 minimal X pts
    # -----------------------------------------------------------------
    if not cfg.filter_f1_ring_enabled:
        if verbose:
            print("   [--] [F1] Ring Filter: DISABLED (bypass)")
        # Tetap hitung ring_range untuk keperluan build_signal
        if curr_is_bullish:
            c2_ring_price = curr_close - curr_low
        else:
            c2_ring_price = curr_high - curr_close
        c2_ring_pts = round(c2_ring_price / point)
    else:
        ring_ok, c2_ring_pts, c2_ring_price, _ = check_ring_length(
            curr_close, curr_high, curr_low, curr_is_bullish,
            point, digits, cfg, verbose
        )
        if not ring_ok:
            return None

    # -----------------------------------------------------------------
    # [F2] Anti-Doji: body minimal X% dari full ring
    # -----------------------------------------------------------------
    if not cfg.filter_f2_doji_enabled:
        if verbose:
            print("   [--] [F2] Doji Filter: DISABLED (bypass)")
        body_ring_pct = 0.0
    else:
        body_ok, body_ring_pct = check_body_thickness(
            curr_body, curr_high, curr_low,
            point, digits, cfg, verbose
        )
        if not body_ok:
            return None

    # -----------------------------------------------------------------
    # [F3] Pola Engulfing: warna C1->C2, menelan, ratio
    # -----------------------------------------------------------------
    if not cfg.filter_f3_pattern_enabled:
        if verbose:
            print("   [--] [F3] Pattern Filter: DISABLED (bypass)")
        # Tetap tentukan pattern_type dari warna C1->C2
        if not prev_is_bullish and curr_is_bullish:
            pattern_type = "bullish_engulfing"
        elif prev_is_bullish and not curr_is_bullish:
            pattern_type = "bearish_engulfing"
        else:
            pattern_type = "bullish_engulfing" if curr_is_bullish else "bearish_engulfing"
        engulf_ratio = 0.0
    else:
        pattern_ok, pattern_type, engulf_ratio = check_engulf_pattern(
            prev_open, prev_body, prev_is_bullish,
            curr_open, curr_close, curr_body, curr_is_bullish,
            point, digits, cfg, verbose
        )
        if not pattern_ok or pattern_type is None:
            return None

    # -----------------------------------------------------------------
    # [F4] EMA Position: Close C2 di sisi benar EMA
    # (gunakan flag filter_f4_ema_enabled ATAU ema_filter_enabled lama)
    # -----------------------------------------------------------------
    if not cfg.filter_f4_ema_enabled:
        if verbose:
            print("   [--] [F4] EMA Filter: DISABLED (bypass)")
    else:
        ema_ok = check_ema_position(
            pattern_type, curr_close,
            ema_fast, ema_slow,
            digits, cfg, verbose
        )
        if not ema_ok:
            return None

    # -----------------------------------------------------------------
    # [OK] Semua filter lolos -> bangun sinyal
    # -----------------------------------------------------------------
    signal = build_signal(
        candle_data, pattern_type, engulf_ratio,
        ema_fast, ema_slow, curr_close, cfg
    )

    if verbose:
        label     = "[BUY]" if pattern_type == "bullish_engulfing" else "[SELL]"
        ema_ref   = ema_slow if cfg.ema_filter_source == "slow" else ema_fast
        ema_label = f"EMA_{cfg.ema_filter_source.upper()}"
        print(f"   {'-'*52}")
        print(f"   {label} {pattern_type.upper()} LOLOS SEMUA FILTER!")
        print(
            f"      Ring  : {c2_ring_pts} pts"
            f" | Body: {body_ring_pct:.1f}%"
            f" | Ratio: {signal['engulf_ratio']:.2f}x"
        )
        print(
            f"      EMA   : Close_C2={curr_close:.{digits}f}"
            f" vs {ema_label}={ema_ref:.{digits}f}"
            f" | Confidence: {signal['confidence_score']:.1f}%"
        )
        print(f"   {'-'*52}")

    return signal
