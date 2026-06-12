# =====================================================
# strategies/engulfing/signal_builder.py
# Build sinyal, hitung confidence, generate notes
# =====================================================

from config.engulfing_config import EngulfingConfig


def build_signal(
    candle_data: dict,
    pattern_type: str,
    engulf_ratio: float,
    ema_fast: float,
    ema_slow: float,
    curr_close: float,
    cfg: EngulfingConfig,
) -> dict:
    """Build dict sinyal lengkap untuk disimpan ke DB / dikirim ke execution."""
    confidence = calc_confidence(engulf_ratio, pattern_type, ema_fast, ema_slow, curr_close, cfg)
    ema_trend  = get_ema_trend(ema_fast, ema_slow)

    return {
        "symbol":         candle_data["symbol"],
        "timeframe":      candle_data["timeframe"],
        "signal_time":    candle_data["timestamp"],
        "pattern_type":   pattern_type,
        "prev_open":      candle_data["prev_open"],
        "prev_close":     candle_data["prev_close"],
        "prev_high":      candle_data["prev_high"],
        "prev_low":       candle_data["prev_low"],
        "curr_open":      candle_data["open_"],
        "curr_close":     candle_data["close_"],
        "curr_high":      candle_data["high_"],
        "curr_low":       candle_data["low_"],
        "engulf_ratio":   round(engulf_ratio, 3),
        "ema_fast_value": ema_fast,
        "ema_slow_value": ema_slow,
        "ema_trend":      ema_trend,
        "confidence_score": round(confidence, 1),
        "is_confirmed": (
            (pattern_type == "bullish_engulfing" and ema_trend == "bullish")
            or (pattern_type == "bearish_engulfing" and ema_trend == "bearish")
        ),
        "notes": generate_notes(pattern_type, engulf_ratio, ema_trend, confidence),
    }


def calc_confidence(
    engulf_ratio: float,
    pattern_type: str,
    ema_fast: float,
    ema_slow: float,
    curr_close: float,
    cfg: EngulfingConfig,
) -> float:
    """
    Confidence score 0–100 berdasarkan:
      1. Base score dari engulf ratio       (40–60)
      2. Bonus EMA trend alignment          (+cfg.confidence_ema_bonus)
      3. Bonus close di sisi benar EMA      (+10)
      4. Bonus ratio besar (>=1.5x / >=2x) (+cfg.confidence_ratio_bonus)
    """
    # Base: 40–60 tergantung seberapa besar ratio
    base = min(60, 40 + (engulf_ratio - 1.0) * 20)

    # Bonus: EMA fast vs slow alignment
    ema_bonus = 0
    if pattern_type == "bullish_engulfing" and ema_fast > ema_slow:
        ema_bonus = cfg.confidence_ema_bonus
    elif pattern_type == "bearish_engulfing" and ema_fast < ema_slow:
        ema_bonus = cfg.confidence_ema_bonus

    # Bonus: posisi Close vs EMA fast
    close_bonus = 0
    if pattern_type == "bullish_engulfing" and curr_close > ema_fast:
        close_bonus = 10
    elif pattern_type == "bearish_engulfing" and curr_close < ema_fast:
        close_bonus = 10

    # Bonus: ratio besar
    ratio_bonus = 0
    if engulf_ratio >= 2.0:
        ratio_bonus = cfg.confidence_ratio_bonus
    elif engulf_ratio >= 1.5:
        ratio_bonus = cfg.confidence_ratio_bonus * 0.5

    return min(100, max(0, base + ema_bonus + close_bonus + ratio_bonus))


def get_ema_trend(ema_fast: float, ema_slow: float) -> str:
    """Return 'bullish' | 'bearish' | 'neutral' berdasarkan EMA cross."""
    if ema_fast > ema_slow:
        return "bullish"
    elif ema_fast < ema_slow:
        return "bearish"
    return "neutral"


def generate_notes(
    pattern_type: str,
    engulf_ratio: float,
    ema_trend: str,
    confidence: float,
) -> str:
    """Generate string catatan singkat tentang kualitas sinyal."""
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
