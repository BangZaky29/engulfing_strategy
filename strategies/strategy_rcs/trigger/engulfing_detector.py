# =====================================================
# strategies/strategy_rcs/trigger/engulfing_detector.py
# Logika deteksi Engulfing standard untuk RCS
# =====================================================

def detect_engulfing(candle_data: dict, point: float) -> str | None:
    """
    Cek apakah candle_data merupakan pola Engulfing valid.
    Menggunakan definisi: Curr (Engulfing) menelan Prev (Engulfed) secara full body dan ekor.
    
    Returns direction ("BUY" atau "SELL") jika valid, atau None jika tidak.
    """
    c_open = candle_data["open_"]
    c_close = candle_data["close_"]
    c_high = candle_data["high_"]
    c_low = candle_data["low_"]
    c_is_bullish = candle_data["is_bullish"]
    
    p_high = candle_data["prev_high"]
    p_low = candle_data["prev_low"]
    
    # 1. Pastikan curr menelan full range prev (high dan low prev ada di dalam high dan low curr)
    if not (c_high > p_high and c_low < p_low):
        return None
        
    # 2. Return arah dari Engulfing
    if c_is_bullish:
        return "BUY"
    else:
        return "SELL"
