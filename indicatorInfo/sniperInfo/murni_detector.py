# =====================================================
# indicatorInfo/sniperInfo/murni_detector.py
# Deteksi Engulfing Murni — Close C1 melewati Ekor C2
# =====================================================


def detect_engulfing_murni(candle_data: dict, source: str = "scanner") -> str | None:
    """
    Deteksi Engulfing Murni: Close C1 melewati EKOR (shadow/wick) C2.

    Syarat lebih ketat dari engulfing biasa:
    - Beda warna (C1 vs C2 berlawanan arah)
    - Bullish Murni: C1 bullish + C2 bearish + C1.close > C2.high
      (Body C1 menelan seluruh candle C2 termasuk upper wick)
    - Bearish Murni: C1 bearish + C2 bullish + C1.close < C2.low
      (Body C1 menelan seluruh candle C2 termasuk lower wick)

    Args:
        candle_data: Dict berisi data C1 (candle terakhir close) dan C2 (sebelumnya).
        source: "scanner" untuk format scanner_engine, "fetcher" untuk format candle_fetcher.

    Returns:
        "BUY" | "SELL" | None
    """
    if source == "scanner":
        # Format dari scanner/engine.py: c1 = close_, c2 = c2_*
        c1_open = candle_data["close_"]   # Perhatian: di scanner, close_ = c1 close
        c1_close = candle_data["close_"]
        c1_open = candle_data["open_"]
        c1_high = candle_data["high_"]
        c1_low = candle_data["low_"]
        c1_is_bullish = c1_close > c1_open

        c2_open = candle_data["c2_open"]
        c2_close = candle_data["c2_close"]
        c2_high = candle_data["c2_high"]
        c2_low = candle_data["c2_low"]
        c2_is_bullish = c2_close > c2_open
    else:
        # Format dari candle_fetcher.py: close_ = C1, prev_* = C2
        c1_open = candle_data["open_"]
        c1_close = candle_data["close_"]
        c1_high = candle_data["high_"]
        c1_low = candle_data["low_"]
        c1_is_bullish = candle_data["is_bullish"]

        c2_open = candle_data["prev_open"]
        c2_close = candle_data["prev_close"]
        c2_high = candle_data["prev_high"]
        c2_low = candle_data["prev_low"]
        c2_is_bullish = candle_data["prev_is_bullish"]

    # 0. Syarat beda warna (Reversal) — C1 dan C2 harus berlawanan arah
    if c1_is_bullish == c2_is_bullish:
        return None

    # 1. Bullish Engulfing Murni
    #    C2 = Bearish (merah), C1 = Bullish (hijau)
    #    Close C1 melewati HIGH C2 (menembus seluruh shadow/ekor atas C2)
    if c1_is_bullish and not c2_is_bullish:
        if c1_close > c2_high:
            return "BUY"

    # 2. Bearish Engulfing Murni
    #    C2 = Bullish (hijau), C1 = Bearish (merah)
    #    Close C1 melewati LOW C2 (menembus seluruh shadow/ekor bawah C2)
    if not c1_is_bullish and c2_is_bullish:
        if c1_close < c2_low:
            return "SELL"

    return None
