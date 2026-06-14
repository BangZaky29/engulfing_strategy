# =====================================================
# strategies/engulfing/filters/f4_market_state.py
# F4: Market State Evaluation (Trend vs Sideways)
# =====================================================

def evaluate_market_state(
    ema_now: float, 
    ema_20_ago: float, 
    avg_range_20: float, 
    cross_count: int, 
    side_strength: float, 
    point: float, 
    market_lookback: int = 20
) -> str:
    """
    Evaluasi Market State berdasarkan n-candle lookback.
    Returns: 'SIDEWAYS', 'TRENDING_UP', 'TRENDING_DOWN', atau 'NORMAL'
    """
    if point <= 0:
        return "NORMAL"

    # 1. Slope Ratio
    slope_points = abs(ema_now - ema_20_ago) / point
    avg_range_pts = avg_range_20 / point if avg_range_20 > 0 else 0
    slope_ratio = slope_points / avg_range_pts if avg_range_pts > 0 else 0

    # 2. Cross Ratio
    cross_ratio = cross_count / market_lookback if market_lookback > 0 else 0

    # 3. Klasifikasi Market State
    if slope_ratio < 0.15 or cross_ratio >= 0.35:
        return "SIDEWAYS"

    if slope_ratio >= 0.35 and side_strength >= 0.70:
        if ema_now > ema_20_ago:
            return "TRENDING_UP"
        elif ema_now < ema_20_ago:
            return "TRENDING_DOWN"
        
    return "NORMAL"
