# =====================================================
# strategies/strategy_rcs/trigger/trigger_filter.py
# Filter-filter utama RCS (Range, Body, Spread, EMA)
# =====================================================

from config.rcs_config import RCSConfig
from . import skip_reasons as sr

def apply_all_filters(candle_data: dict, config: RCSConfig, direction: str) -> tuple[bool, str]:
    """
    Evaluasi semua filter RCS.
    Returns: (is_passed, skip_reason)
    """
    point = candle_data["point"]
    if point == 0:
        return False, "Point size 0 (invalid data)"
        
    c_open = candle_data["open_"]
    c_close = candle_data["close_"]
    c_high = candle_data["high_"]
    c_low = candle_data["low_"]
    spread = int(candle_data["spread"])
    
    # Hitung risk range & body
    if direction == "BUY":
        risk_range_pts = int(round((c_close - c_low) / point))
    else:
        risk_range_pts = int(round((c_high - c_close) / point))
        
    body_pct = candle_data["body_pct"]
    
    # 1. Filter Range
    if risk_range_pts < config.min_trigger_range:
        return False, sr.skip_range_too_small(risk_range_pts, config.min_trigger_range)
    if risk_range_pts > config.max_trigger_range:
        return False, sr.skip_range_too_large(risk_range_pts, config.max_trigger_range)
        
    # 2. Filter Body
    if body_pct < config.min_body_percent:
        return False, sr.skip_body_too_small(body_pct, config.min_body_percent)
    if body_pct > config.max_body_percent:
        return False, sr.skip_body_too_large(body_pct, config.max_body_percent)
        
    # 3. Filter Spread
    if config.use_spread_filter and spread > config.max_spread_points:
        return False, sr.skip_spread_too_high(spread, config.max_spread_points)
        
    # 4. Filter EMA Pullback
    if config.use_ema_pullback:
        ema = candle_data["ema_now"]
        dist_open_ema = int(round(abs(c_open - ema) / point))
        
        # 4a. Cek Sisi Open C1 (Sisi Benar): 
        # Untuk BUY: Open C1 HARUS di atas/sama dengan EMA 20 (c_open >= ema)
        # Untuk SELL: Open C1 HARUS di bawah/sama dengan EMA 20 (c_open <= ema)
        if direction == "BUY":
            if c_open < ema:
                return False, sr.skip_ema_wrong_side(direction)
            if c_close <= ema:
                return False, sr.skip_ema_not_crossed(direction)
        else:
            # SELL
            if c_open > ema:
                return False, sr.skip_ema_wrong_side(direction)
            if c_close >= ema:
                return False, sr.skip_ema_not_crossed(direction)
                
        # 4b. Cek Rentang Jarak Open ke EMA (0 - 200 pts)
        if dist_open_ema < config.min_ema_distance_pts:
            return False, sr.skip_ema_distance_too_close(dist_open_ema, config.min_ema_distance_pts)
            
        if dist_open_ema > config.max_ema_distance_pts:
            return False, sr.skip_ema_distance_too_far(dist_open_ema, config.max_ema_distance_pts)
            
    return True, ""
