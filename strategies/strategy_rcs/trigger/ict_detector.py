# =====================================================
# strategies/strategy_rcs/trigger/ict_detector.py
# Logika deteksi ICT Sweep Pattern
# =====================================================

import MetaTrader5 as mt5
from config.mt5_config import MT5Config

def detect_ict(symbol: str, tf_label: str, mt5_cfg: MT5Config, lookback_bars: int, point: float) -> str | None:
    """
    Cek apakah candle terakhir melakukan liquidity sweep dan rejection (ICT Style).
    Sweep didefinisikan sebagai: ekor candle menyentuh/melewati high/low dari N candle sebelumnya,
    tapi body tutup (rejection) meninggalkannya.
    
    Returns direction ("BUY" atau "SELL") jika valid, atau None jika tidak.
    """
    tf_const = mt5_cfg.get_mt5_timeframe(tf_label)
    
    # Ambil N + 2 candle (1 untuk curr, N untuk lookback, 1 tambahan untuk safety shift)
    rates = mt5.copy_rates_from_pos(symbol, tf_const, 1, lookback_bars + 2)
    if rates is None or len(rates) < lookback_bars + 1:
        return None
        
    curr = rates[-1]  # C1 (Candle yang baru saja close)
    prev = rates[-2]  # C2 (Candle sebelum C1)
    
    c_open = curr['open']
    c_close = curr['close']
    c_high = curr['high']
    c_low = curr['low']
    c_is_bullish = c_close > c_open

    p_open = prev['open']
    p_close = prev['close']
    p_is_bullish = p_close > p_open
    
    # 0. Syarat beda warna (Reversal): C1 dan C2 HARUS berlawanan warna!
    # Untuk SELL: C1 = MERAH (Bearish), C2 = HIJAU (Bullish)
    # Untuk BUY:  C1 = HIJAU (Bullish), C2 = MERAH (Bearish)
    if c_is_bullish == p_is_bullish:
        return None
        
    # Lookback candles (tidak termasuk C1 / curr)
    lookback_candles = rates[-(lookback_bars + 1):-1]
    
    highest_in_lookback = max(c['high'] for c in lookback_candles)
    lowest_in_lookback = min(c['low'] for c in lookback_candles)
    
    # 1. Sweep Liquidity Bawah (Bullish Setup)
    # Ekor tembus low lookback, tapi body close BULLISH
    if c_low < lowest_in_lookback and c_is_bullish:
        # Cek kekuatan rejection (ekor bawah harus cukup panjang, close di atas)
        # Syarat minimal: body dan upper wick tidak lebih besar dari lower wick (rejection kuat)
        body = c_close - c_open
        lower_wick = c_open - c_low
        if lower_wick > body:
            return "BUY"
            
    # 2. Sweep Liquidity Atas (Bearish Setup)
    # Ekor tembus high lookback, tapi body close BEARISH
    if c_high > highest_in_lookback and not c_is_bullish:
        body = c_open - c_close
        upper_wick = c_high - c_open
        if upper_wick > body:
            return "SELL"
            
    return None
