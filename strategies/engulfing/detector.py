# =====================================================
# strategies/engulfing/detector.py
# Core logic: Deteksi pola Bullish & Bearish Engulfing
# =====================================================

from config.engulfing_config import EngulfingConfig


def detect_engulfing(candle_data: dict, cfg: EngulfingConfig = None,
                     verbose: bool = False) -> dict | None:
    """
    Deteksi apakah C2 membentuk pola engulfing terhadap C1.

    Bullish Engulfing:
      - C1 bearish (merah), C2 bullish (hijau)
      - Body C2 sepenuhnya menelan body C1
      - Open C2 <= Close C1  AND  Close C2 >= Open C1

    Bearish Engulfing:
      - C1 bullish (hijau), C2 bearish (merah)
      - Body C2 sepenuhnya menelan body C1
      - Open C2 >= Close C1  AND  Close C2 <= Open C1

    Returns:
        dict sinyal engulfing  |  None jika tidak ada pola
    """
    if cfg is None:
        cfg = EngulfingConfig()

    # --- Unpack data ---
    prev_open       = candle_data["prev_open"]
    prev_close      = candle_data["prev_close"]
    prev_high       = candle_data["prev_high"]
    prev_low        = candle_data["prev_low"]
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

    # point = ukuran 1 MT5 point (XAUUSD = 0.01, sehingga 7.42 harga = 742 MT5 points)
    point  = candle_data.get("point", 0.01)
    digits = candle_data.get("digits", 2)

    warna_c2 = "Hijau ▲" if curr_is_bullish else "Merah ▼"
    warna_c1 = "Hijau ▲" if prev_is_bullish else "Merah ▼"

    # =====================================================
    # Pre-filter C2: Panjang Ring & Anti-Doji
    # =====================================================
    if verbose:
        print(f"   {'─'*52}")
        print(f"   🔍 Filter C2 ({warna_c2})  C1 ({warna_c1})")
        print(f"   {'─'*52}")

    # ─── [1] Hitung ring C2 sesuai konsep ──────────────────────────
    #   Candle Hijau : ring = Close - Low   (0%=Close → 100%=Low)
    #   Candle Merah : ring = High  - Close (0%=Close → 100%=High)
    if curr_is_bullish:
        c2_ring_price = curr_close - curr_low
        ring_formula  = "Close - Low"
    else:
        c2_ring_price = curr_high - curr_close
        ring_formula  = "High - Close"

    # Konversi ke MT5 points (satuan yang sama dgn tampilan di MT5)
    c2_ring_pts   = round(c2_ring_price / point)
    c2_full_ring  = curr_high - curr_low
    c2_full_pts   = round(c2_full_ring / point)
    curr_body_pts = round(curr_body / point)
    prev_body_pts = round(prev_body / point)

    # ─── [2] Filter: minimal panjang ring C2 ────────────────────────
    ring_ok = c2_ring_pts >= cfg.min_ring_points
    if verbose:
        status = "✅" if ring_ok else "❌"
        print(
            f"   {status} Ring ({ring_formula}): {c2_ring_pts} pts"
            f"  (harga: {c2_ring_price:.{digits}f})"
            f"  | min: {cfg.min_ring_points:.0f} pts"
        )
    if not ring_ok:
        if verbose:
            print(
                f"   ⏩ SKIP: ring terlalu pendek"
                f"  ({c2_ring_pts} pts < min {cfg.min_ring_points:.0f} pts)"
            )
        return None

    # ─── [3] Anti-Doji: body minimal X% dari full ring ──────────────
    #   Full Ring = High - Low (100%)
    #   Body      = |Close - Open|
    body_ring_pct = (curr_body / c2_full_ring * 100) if c2_full_ring > 0 else 0.0
    body_ok = body_ring_pct >= cfg.min_body_ring_pct

    if verbose:
        status = "✅" if body_ok else "❌"
        print(
            f"   {status} Body%: {body_ring_pct:.1f}%"
            f"  (body={curr_body_pts} pts / full_ring={c2_full_pts} pts)"
            f"  | min: {cfg.min_body_ring_pct:.0f}%"
        )
    if not body_ok:
        if verbose:
            print(
                f"   ⏩ SKIP: body terlalu tipis / Doji"
                f"  ({body_ring_pct:.1f}% < min {cfg.min_body_ring_pct:.0f}%)"
            )
        return None

    # ─── [4] Cek pasangan warna C1 → C2 ────────────────────────────
    pola_ok = (
        (not prev_is_bullish and curr_is_bullish) or  # Merah→Hijau (bullish engulfing)
        (prev_is_bullish and not curr_is_bullish)      # Hijau→Merah (bearish engulfing)
    )
    if verbose:
        status = "✅" if pola_ok else "❌"
        print(f"   {status} Pasangan: C1={warna_c1} → C2={warna_c2}")
    if not pola_ok:
        if verbose:
            print("   ⏩ SKIP: C1 dan C2 warna sama, bukan pola engulfing")
        return None

    # ─── [5] Cek engulf (apakah C2 menelan body C1) ─────────────────
    signal = None

    # Bullish Engulfing: C1 merah → C2 hijau
    if not prev_is_bullish and curr_is_bullish:
        menelan = curr_close > prev_open
        if verbose:
            status = "✅" if menelan else "❌"
            print(
                f"   {status} Menelan: Close_C2 ({curr_close:.{digits}f})"
                f" > Open_C1 ({prev_open:.{digits}f})"
            )
        if menelan:
            engulf_ratio = curr_body / prev_body if prev_body > 0 else 0
            engulf_ok    = engulf_ratio >= cfg.min_body_ratio
            if verbose:
                status = "✅" if engulf_ok else "❌"
                print(
                    f"   {status} Engulf ratio: {engulf_ratio:.2f}x"
                    f"  (body_C2={curr_body_pts} pts / body_C1={prev_body_pts} pts)"
                    f"  | min: {cfg.min_body_ratio}x"
                )
            if engulf_ok:
                signal = _build_signal(
                    candle_data, "bullish_engulfing", engulf_ratio,
                    ema_fast, ema_slow, curr_close, cfg
                )
            elif verbose:
                print(
                    f"   ⏩ SKIP: engulf ratio kurang"
                    f"  ({engulf_ratio:.2f}x < min {cfg.min_body_ratio}x)"
                )
        else:
            if verbose:
                print("   ⏩ SKIP: C2 tidak menelan body C1")

    # Bearish Engulfing: C1 hijau → C2 merah
    elif prev_is_bullish and not curr_is_bullish:
        menelan = curr_close < prev_open
        if verbose:
            status = "✅" if menelan else "❌"
            print(
                f"   {status} Menelan: Close_C2 ({curr_close:.{digits}f})"
                f" < Open_C1 ({prev_open:.{digits}f})"
            )
        if menelan:
            engulf_ratio = curr_body / prev_body if prev_body > 0 else 0
            engulf_ok    = engulf_ratio >= cfg.min_body_ratio
            if verbose:
                status = "✅" if engulf_ok else "❌"
                print(
                    f"   {status} Engulf ratio: {engulf_ratio:.2f}x"
                    f"  (body_C2={curr_body_pts} pts / body_C1={prev_body_pts} pts)"
                    f"  | min: {cfg.min_body_ratio}x"
                )
            if engulf_ok:
                signal = _build_signal(
                    candle_data, "bearish_engulfing", engulf_ratio,
                    ema_fast, ema_slow, curr_close, cfg
                )
            elif verbose:
                print(
                    f"   ⏩ SKIP: engulf ratio kurang"
                    f"  ({engulf_ratio:.2f}x < min {cfg.min_body_ratio}x)"
                )
        else:
            if verbose:
                print("   ⏩ SKIP: C2 tidak menelan body C1")

    # --- Output final ---
    if verbose:
        print(f"   {'─'*52}")
    if signal and verbose:
        emoji = "🟩" if signal["pattern_type"] == "bullish_engulfing" else "🟥"
        print(
            f"   {emoji} {signal['pattern_type'].upper()} LOLOS SEMUA FILTER!"
        )
        print(
            f"      Ring : {c2_ring_pts} pts | Body: {body_ring_pct:.1f}% | "
            f"Ratio: {signal['engulf_ratio']:.2f}x | "
            f"Confidence: {signal['confidence_score']:.1f}% | EMA: {signal['ema_trend']}"
        )
        print(f"   {'─'*52}")
    elif not signal and verbose:
        print(f"   ⏭️  Tidak ada sinyal engulfing.")

    return signal


# =====================================================
# Private helpers
# =====================================================

def _build_signal(candle_data: dict, pattern_type: str, engulf_ratio: float,
                  ema_fast: float, ema_slow: float, curr_close: float,
                  cfg: EngulfingConfig) -> dict:
    """Build dict sinyal lengkap."""
    confidence = _calc_confidence(engulf_ratio, pattern_type, ema_fast, ema_slow, curr_close, cfg)
    ema_trend = _get_ema_trend(ema_fast, ema_slow)

    return {
        "symbol": candle_data["symbol"],
        "timeframe": candle_data["timeframe"],
        "signal_time": candle_data["timestamp"],
        "pattern_type": pattern_type,
        "prev_open": candle_data["prev_open"],
        "prev_close": candle_data["prev_close"],
        "prev_high": candle_data["prev_high"],
        "prev_low": candle_data["prev_low"],
        "curr_open": candle_data["open_"],
        "curr_close": candle_data["close_"],
        "curr_high": candle_data["high_"],
        "curr_low": candle_data["low_"],
        "engulf_ratio": round(engulf_ratio, 3),
        "ema_fast_value": ema_fast,
        "ema_slow_value": ema_slow,
        "ema_trend": ema_trend,
        "confidence_score": round(confidence, 1),
        "is_confirmed": (
            (pattern_type == "bullish_engulfing" and ema_trend == "bullish")
            or (pattern_type == "bearish_engulfing" and ema_trend == "bearish")
        ),
        "notes": _generate_notes(pattern_type, engulf_ratio, ema_trend, confidence),
    }


def _calc_confidence(engulf_ratio: float, pattern_type: str,
                     ema_fast: float, ema_slow: float,
                     curr_close: float, cfg: EngulfingConfig) -> float:
    """
    Confidence score 0–100 berdasarkan:
      1. Base score dari engulf ratio
      2. Bonus EMA trend alignment
      3. Bonus close di sisi benar EMA
      4. Bonus ratio besar
    """
    # Base: 40–60
    base = min(60, 40 + (engulf_ratio - 1.0) * 20)

    # EMA alignment
    ema_bonus = 0
    if pattern_type == "bullish_engulfing" and ema_fast > ema_slow:
        ema_bonus = cfg.confidence_ema_bonus
    elif pattern_type == "bearish_engulfing" and ema_fast < ema_slow:
        ema_bonus = cfg.confidence_ema_bonus

    # Close position vs EMA
    close_bonus = 0
    if pattern_type == "bullish_engulfing" and curr_close > ema_fast:
        close_bonus = 10
    elif pattern_type == "bearish_engulfing" and curr_close < ema_fast:
        close_bonus = 10

    # Ratio bonus
    ratio_bonus = 0
    if engulf_ratio >= 2.0:
        ratio_bonus = cfg.confidence_ratio_bonus
    elif engulf_ratio >= 1.5:
        ratio_bonus = cfg.confidence_ratio_bonus * 0.5

    return min(100, max(0, base + ema_bonus + close_bonus + ratio_bonus))


def _get_ema_trend(ema_fast: float, ema_slow: float) -> str:
    if ema_fast > ema_slow:
        return "bullish"
    elif ema_fast < ema_slow:
        return "bearish"
    return "neutral"


def _generate_notes(pattern_type: str, engulf_ratio: float,
                    ema_trend: str, confidence: float) -> str:
    parts = []
    label = "Bullish" if pattern_type == "bullish_engulfing" else "Bearish"
    parts.append(f"Pola {label} Engulfing terdeteksi")
    parts.append(f"Engulf ratio: {engulf_ratio:.2f}x")
    parts.append(f"EMA trend: {ema_trend}")

    if confidence >= 80:
        parts.append("⚠️ HIGH CONFIDENCE")
    elif confidence >= 50:
        parts.append("Sinyal moderate")
    else:
        parts.append("Sinyal lemah")

    aligned = (
        (pattern_type == "bullish_engulfing" and ema_trend == "bullish")
        or (pattern_type == "bearish_engulfing" and ema_trend == "bearish")
    )
    if aligned:
        parts.append("✅ EMA sejalan")
    elif ema_trend != "neutral":
        parts.append("⚠️ EMA berlawanan")

    return " | ".join(parts)
