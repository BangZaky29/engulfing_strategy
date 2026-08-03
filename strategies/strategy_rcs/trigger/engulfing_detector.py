# =====================================================
# strategies/strategy_rcs/trigger/engulfing_detector.py
# Logika deteksi Engulfing standard untuk RCS
# =====================================================

def detect_engulfing(candle_data: dict, point: float) -> str | None:
    """
    Cek apakah candle_data merupakan pola Engulfing valid.
    Definisi: C1 (Engulfing) menelan C2 (Engulfed) pada body dan penembusan High/Low sesuai arah.
    
    Returns direction ("BUY" atau "SELL") jika valid, atau None jika tidak.
    """
    c_open = candle_data["open_"]
    c_close = candle_data["close_"]
    c_high = candle_data["high_"]
    c_low = candle_data["low_"]
    c_is_bullish = candle_data["is_bullish"]
    
    p_open = candle_data["prev_open"]
    p_close = candle_data["prev_close"]
    p_high = candle_data["prev_high"]
    p_low = candle_data["prev_low"]
    p_is_bullish = candle_data["prev_is_bullish"]
    
    # 0. Syarat beda warna (Reversal)
    if c_is_bullish == p_is_bullish:
        return None
    
    # 1. Bullish Engulfing (C2 Merah, C1 Hijau)
    if c_is_bullish:
        # C1 Close menembus Open C2 ke atas & C1 High menembus High C2
        if c_close >= p_open and c_high >= p_high:
            return "BUY"
            
    # 2. Bearish Engulfing (C2 Hijau, C1 Merah)
    else:
        # C1 Close menembus Open C2 ke bawah & C1 Low menembus Low C2
        if c_close <= p_open and c_low <= p_low:
            return "SELL"
            
    return None
