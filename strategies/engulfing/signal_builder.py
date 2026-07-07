# =====================================================
# strategies/engulfing/signal_builder.py
# Build sinyal dan notes payload
# =====================================================

import json
from datetime import datetime, timezone, timedelta
from config.engulfing_config import EngulfingConfig
from config.execution_config import ExecutionConfig

def is_us_dst(dt: datetime) -> bool:
    # Convert dt to UTC first to be standard
    dt_utc = dt.astimezone(timezone.utc)
    year = dt_utc.year
    
    # Second Sunday in March
    w_march1 = datetime(year, 3, 1, tzinfo=timezone.utc).weekday()
    first_sun_march = 1 + (6 - w_march1) % 7
    dst_start = datetime(year, 3, first_sun_march + 7, 2, 0, tzinfo=timezone.utc)
    
    # First Sunday in November
    w_nov1 = datetime(year, 11, 1, tzinfo=timezone.utc).weekday()
    first_sun_nov = 1 + (6 - w_nov1) % 7
    dst_end = datetime(year, 11, first_sun_nov, 2, 0, tzinfo=timezone.utc)
    
    return dst_start <= dt_utc < dst_end


def get_trading_session_wib(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
    else:
        # If it is naive (no tzinfo), assume it is UTC.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        
    wib_tz = timezone(timedelta(hours=7))
    dt_wib = dt.astimezone(wib_tz)
    hour = dt_wib.hour
    
    is_dst = is_us_dst(dt)
    
    if is_dst:
        # Summer/DST
        if 7 <= hour < 14:
            return "Asia Only"
        elif 14 <= hour < 16:
            return "Asia x Europe Overlap"
        elif 16 <= hour < 19:
            return "Europe Only"
        elif 19 <= hour < 23:
            return "Europe x New York Overlap"
        elif hour >= 23 or hour < 4:
            return "New York Only"
        else:
            return "Off / Low Liquidity"
    else:
        # Winter/Non-DST
        if 7 <= hour < 15:
            return "Asia Only"
        elif 15 <= hour < 16:
            return "Asia x Europe Overlap"
        elif 16 <= hour < 20:
            return "Europe Only"
        elif 20 <= hour < 24:
            return "Europe x New York Overlap"
        elif 0 <= hour < 5:
            return "New York Only"
        else:
            return "Off / Low Liquidity"


def build_signal(
    candle_data: dict,
    pattern_type: str,
    scoring_res: dict,
    rr_ratio: float,
    cfg: EngulfingConfig,
) -> dict:
    """Build dict sinyal lengkap untuk disimpan ke DB / dikirim ke execution."""
    
    c1_open       = candle_data["open_"]
    c1_close      = candle_data["close_"]
    c1_high       = candle_data["high_"]
    c1_low        = candle_data["low_"]
    point         = candle_data.get("point", 0.01)

    exec_cfg = ExecutionConfig()
    trading_session = get_trading_session_wib()
    op_price = c1_close  # Default for A
    tp_price = 0.0

    if cfg.active_filter_strategy == 'B':
        # --- Filter B ---
        op_pct = exec_cfg.op_pct_b
        
        if pattern_type.startswith("bullish"):
            range_ref = c1_close - c1_low
            op_price = c1_close - (range_ref * (op_pct / 100.0))
        else:
            range_ref = c1_high - c1_close
            op_price = c1_close + (range_ref * (op_pct / 100.0))
            
        sl_pct_used = 0.0


    else:
        # --- Filter A ---
        # No longer computing SL and TP here
        sl_pct_used = 0.0

    # 2. (RR Ratio is now provided by F3 filter via arguments)

    # Save details into notes as JSON string
    notes_payload = {
        "grade": scoring_res["grade"],
        "action_str": scoring_res["action_str"],
        "body_pct": scoring_res["body_pct"],
        "cp_pct": scoring_res["cp_pct"],
        "sl_pct_used": sl_pct_used,
        "rr_ratio": rr_ratio,
        "sl_pts": 0,
        "ring_pts": round(abs(c1_high - c1_low) / point) if point > 0 else 0,
        "op_price": float(op_price),
        "sl_price": 0.0,
        "tp_price": None,
        "total_score": scoring_res["total_score"],
        "market_state": scoring_res["market_state"],
        "trading_session": trading_session,
        "score_breakdown": scoring_res.get("score_breakdown", ""),
        "sl_source": "M5",   # akan di-override "H1" oleh detector jika H1 trigger tersedia
        "sl_pct": None,      # akan diisi oleh detector (sl_h1_pct dari FilterCConfig)
        "tfm_status": None,
        "tfm_bias": None,
        "tfm_snapshot": None,
        "skip_reason": None,
        "skip_reasons": [],
        "h1_trigger_source": None,
        "h1_trigger_time": None,
        "m15_trigger_source": None,
        "m15_trigger_time": None,
        "m15_trigger_age": None,
        "m5_trigger_source": None,
        "m5_trigger_time": None,
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
        "volume":         float(candle_data.get("volume", 0.0)),
        "ema_fast_value": candle_data.get("ema_now", 0.0),
        "ema_slow_value": candle_data.get("ema_20_ago", 0.0),
        "ema_trend":      scoring_res["market_state"],
        "confidence_score": scoring_res["total_score"],
        "action_str": scoring_res["action_str"],
        "is_confirmed": True,
        "notes": notes_str,
        
        # Ekstra return fields agar bisa dipakai oleh print di detector.py
        "rr_ratio": rr_ratio,
        "sl_pts": 0,
        "op_price": float(op_price),
        "sl_price": 0.0,
        "tp_price": None,
        "trading_session": trading_session
    }

