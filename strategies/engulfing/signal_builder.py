# =====================================================
# strategies/engulfing/signal_builder.py
# Build sinyal dan notes payload
# =====================================================

import json
from config.engulfing_config import EngulfingConfig


def build_signal(
    candle_data: dict,
    pattern_type: str,
    scoring_res: dict,
    cfg: EngulfingConfig,
) -> dict:
    """Build dict sinyal lengkap untuk disimpan ke DB / dikirim ke execution."""
    
    c1_open       = candle_data["open_"]
    c1_close      = candle_data["close_"]
    c1_high       = candle_data["high_"]
    c1_low        = candle_data["low_"]
    point         = candle_data.get("point", 0.01)

    # 1. Calculate SL pts and SL price
    import os
    sl_pct = float(os.getenv("EXECUTION_SL_PCT", "75"))
    range_c1_price = c1_high - c1_low
    sl_distance_price = range_c1_price * (sl_pct / 100.0)
    
    if pattern_type == "bullish_engulfing":
        sl_price = c1_low - sl_distance_price
    else:
        sl_price = c1_high + sl_distance_price
        
    sl_pts = round(sl_distance_price / point) if point > 0 else 0

    # 2. Calculate RR Ratio
    rr_ratio = float(os.getenv("EXECUTION_TP_RR_RATIO", "1.5"))

    # Save details into notes as JSON string
    notes_payload = {
        "grade": scoring_res["grade"],
        "action_str": scoring_res["action_str"],
        "body_pct": scoring_res["body_pct"],
        "cp_pct": scoring_res["cp_pct"],
        "rr_ratio": rr_ratio,
        "sl_pts": sl_pts,
        "sl_price": round(sl_price, 2),
        "total_score": scoring_res["total_score"],
        "market_state": scoring_res["market_state"]
    }
    notes_str = json.dumps(notes_payload)

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
        "engulf_ratio":   0.0, # deprecated
        "ema_fast_value": candle_data.get("ema_now", 0.0),
        "ema_slow_value": candle_data.get("ema_20_ago", 0.0),
        "ema_trend":      scoring_res["market_state"],
        "confidence_score": scoring_res["total_score"],
        "is_confirmed": True,
        "notes": notes_str,
        
        # Ekstra return fields agar bisa dipakai oleh print di detector.py
        "rr_ratio": rr_ratio,
        "sl_pts": sl_pts,
        "sl_price": round(sl_price, 2)
    }

