# =====================================================
# strategies/engulfing/filters/f2_scoring.py
# F2: All scoring metrics & grade calculation
# =====================================================

from config.engulfing_config import EngulfingConfig

def calculate_scoring(
    c1_open: float, c1_close: float, c1_high: float, c1_low: float,
    c2_open: float, c2_close: float, c2_high: float, c2_low: float,
    avg_range_20: float, ema_now: float, ema_20_ago: float,
    cross_count: int, side_strength: float, pattern_type: str, point: float,
    cfg: EngulfingConfig, verbose: bool = False
) -> dict:
    
    # === 1. Range C1 ===
    range_c1_price = c1_high - c1_low
    range_c1_pts = range_c1_price / point if point > 0 else 0
    
    # === 2. Persentase Body C1 ===
    body_c1_price = abs(c1_close - c1_open)
    body_c1_pts = body_c1_price / point if point > 0 else 0
    body_pct = (body_c1_pts / range_c1_pts * 100) if range_c1_pts > 0 else 0
    
    # === 3. Persentase Wick C1 ===
    wick_pct = 100 - body_pct
    
    # === 4. CP (Close Power) ===
    # Seberapa jauh Close C1 menelan range C2 (High-Low)
    range_c2_price = c2_high - c2_low
    if range_c2_price <= 0:
        cp_pct = 100.0
    else:
        if pattern_type == "bullish_engulfing":
            cp_pct = ((c1_close - c2_open) / range_c2_price) * 100
        else:
            cp_pct = ((c2_open - c1_close) / range_c2_price) * 100

    # === 5. EMA Position ===
    # EMA = ema_now
    is_cross = (c1_open < ema_now and c1_close > ema_now) or (c1_open > ema_now and c1_close < ema_now)
    is_above = c1_close > ema_now
    is_below = c1_close < ema_now
    
    ema_score_pts = 0
    ema_label = "None"
    if is_cross:
        ema_score_pts = 20
        ema_label = "Cross"
    elif is_above:
        ema_score_pts = 15
        ema_label = "Above"
    elif is_below:
        ema_score_pts = 15
        ema_label = "Below"

    # === 6. Market State ===
    # Default = Normal
    market_state = "Normal"
    if cfg.filter_market_state_enabled and point > 0:
        slope_point = abs(ema_now - ema_20_ago) / point
        # Perhitungan slope ratio, cross ratio, dll bisa dilanjutkan di sini
        # Sesuai instruksi, kita bypass logika detail ini jika dinonaktifkan
        # Jika dihidupkan, asumsi sementara: slope besar = trend, banyak cross = sideways
        slope_ratio = slope_point / (avg_range_20 / point) if avg_range_20 > 0 else 0
        
        if slope_ratio > 0.5 and side_strength > 0.6:
            market_state = "Trending"
        elif cross_count > 5 or slope_ratio < 0.1:
            market_state = "Sideways"

    market_state_score = 0
    if market_state == "Trending":
        market_state_score = cfg.score_bonus_trend
    elif market_state == "Sideways":
        market_state_score = cfg.score_penalty_sideways

    # === 7. Scoring Grade ===
    body_score = (body_pct / 100) * cfg.score_weight_body
    
    range_ratio = (range_c1_price / avg_range_20) if avg_range_20 > 0 else 1.0
    capped_range_ratio = min(range_ratio, 1.5)
    range_score = (capped_range_ratio / 1.5) * cfg.score_weight_range
    
    capped_cp = min(cp_pct, 100.0)
    cp_score = (capped_cp / 100) * cfg.score_weight_cp
    
    if cfg.filter_ema_scoring_enabled:
        raw_score = body_score + range_score + ema_score_pts + cp_score + market_state_score
        total_score = raw_score
    else:
        # EMA is Info Only, hitung skor tanpa EMA tapi normalkan kembali ke skala 100
        active_max_weight = cfg.score_weight_body + cfg.score_weight_range + cfg.score_weight_cp
        raw_score = body_score + range_score + cp_score + market_state_score
        total_score = (raw_score / active_max_weight) * 100 if active_max_weight > 0 else 0

    # Konversi Grade
    if total_score >= 95: grade = "A+"
    elif total_score >= 90: grade = "A"
    elif total_score >= 85: grade = "B+"
    elif total_score >= 80: grade = "B"
    elif total_score >= 75: grade = "C+"
    elif total_score >= 70: grade = "C"
    else: grade = "D"

    # Penentuan Action
    action_type = "TREND" if market_state == "Trending" else "REVERSAL"
    direction = "BUY" if pattern_type == "bullish_engulfing" else "SELL"
    action_str = f"{direction} {action_type}"

    if verbose:
        print(f"   [F2] Scoring Summary:")
        print(f"        - Range C1 : {range_c1_pts:.0f} pts | RangeRatio: {range_ratio:.2f}x -> Score: {range_score:.1f}")
        print(f"        - Body C1  : {body_pct:.1f}% -> Score: {body_score:.1f}")
        print(f"        - Close Pwr: {cp_pct:.1f}% -> Score: {cp_score:.1f}")
        print(f"        - EMA Pos  : {ema_label} -> Score: {ema_score_pts:.1f}")
        print(f"        - Market   : {market_state} -> Score: {market_state_score:.1f}")
        print(f"        = TOTAL    : {total_score:.1f} -> Grade: {grade}")
        
    return {
        "range_pts": round(range_c1_pts),
        "body_pct": round(body_pct),
        "wick_pct": round(wick_pct),
        "cp_pct": round(cp_pct),
        "ema_label": ema_label,
        "market_state": market_state,
        "total_score": round(total_score, 1),
        "grade": grade,
        "action_str": action_str
    }
