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
    prev_open = candle_data["prev_open"]
    prev_close = candle_data["prev_close"]
    prev_high = candle_data["prev_high"]
    prev_low = candle_data["prev_low"]
    prev_is_bullish = candle_data["prev_is_bullish"]
    prev_body = candle_data["prev_body_size"]

    curr_open = candle_data["open_"]
    curr_close = candle_data["close_"]
    curr_high = candle_data["high_"]
    curr_low = candle_data["low_"]
    curr_is_bullish = candle_data["is_bullish"]
    curr_body = candle_data["body_size"]

    ema_fast = candle_data["ema_fast"]
    ema_slow = candle_data["ema_slow"]

    # --- Check patterns ---
    signal = None

    # Bullish Engulfing: C1 merah → C2 hijau, body C2 menelan C1
    if not prev_is_bullish and curr_is_bullish:
        # Sesuai request user: C1 Close < C2 Open diperbolehkan, yang penting C2 menelan ke atas
        if curr_close > prev_open:
            engulf_ratio = curr_body / prev_body if prev_body > 0 else 0
            if engulf_ratio >= cfg.min_body_ratio:
                signal = _build_signal(
                    candle_data, "bullish_engulfing", engulf_ratio,
                    ema_fast, ema_slow, curr_close, cfg
                )

    # Bearish Engulfing: C1 hijau → C2 merah, body C2 menelan C1
    elif prev_is_bullish and not curr_is_bullish:
        # Sesuai request user: C1 Close > C2 Open diperbolehkan, yang penting C2 menelan ke bawah
        if curr_close < prev_open:
            engulf_ratio = curr_body / prev_body if prev_body > 0 else 0
            if engulf_ratio >= cfg.min_body_ratio:
                signal = _build_signal(
                    candle_data, "bearish_engulfing", engulf_ratio,
                    ema_fast, ema_slow, curr_close, cfg
                )

    # --- Output ---
    if signal and verbose:
        emoji = "🟩" if signal["pattern_type"] == "bullish_engulfing" else "🟥"
        print(
            f"   {emoji} {signal['pattern_type'].upper()} terdeteksi! "
            f"Ratio: {signal['engulf_ratio']:.2f}x | "
            f"Confidence: {signal['confidence_score']:.1f}% | "
            f"EMA: {signal['ema_trend']}"
        )
    elif verbose:
        print("   ⏭️ Tidak ada pola engulfing.")

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
