# =====================================================
# strategies/engulfing/detector/filter_ab_eval.py
# Modul untuk evaluasi Filter A dan Filter B.
# =====================================================

from config.engulfing_config import EngulfingConfig
from utils.colors import Colors, cprint

from ..filters_A.f1_trigger import check_engulfing_trigger
from ..filters_A.f2_scoring import calculate_scoring
from ..filters_A.f3_pattern import check_pattern_size
from ..filters_B import check_engulfing_trigger_b, check_pattern_size_b, check_ema_ring_b
from ..filters_C import check_tf_monitor
from ..filters_C.f4_state_manager import DIR_BUY, DIR_SELL

def evaluate_filters_ab(
    candle_data: dict,
    cfg: EngulfingConfig,
    verbose: bool,
    color: str,
) -> tuple[str | None, dict, float, str, bool]:
    """
    Menjalankan Filter A atau Filter B sesuai konfigurasi.
    Returns: (skip_reason, scoring_res, rr_ratio, pattern_type, valid_f3)
    """
    symbol = candle_data.get("symbol", "XAUUSD")

    c1_open       = candle_data["open_"]
    c1_close      = candle_data["close_"]
    c1_high       = candle_data["high_"]
    c1_low        = candle_data["low_"]
    c1_is_bullish = candle_data["is_bullish"]
    c1_is_doji    = candle_data.get("is_doji", False)
    
    c2_open       = candle_data["prev_open"]
    c2_close      = candle_data["prev_close"]
    c2_high       = candle_data["prev_high"]
    c2_low        = candle_data["prev_low"]
    c2_is_bullish = candle_data["prev_is_bullish"]
    c2_is_doji    = candle_data.get("prev_is_doji", False)

    point  = candle_data.get("point", 0.01)

    avg_range_20 = candle_data.get("avg_range_20", 0.0)
    ema_now = candle_data.get("ema_now", 0.0)
    ema_slow = candle_data.get("ema_slow", 0.0)
    ema_20_ago = candle_data.get("ema_20_ago", 0.0)
    cross_count = candle_data.get("cross_count_20", 0)
    side_strength = candle_data.get("side_strength_20", 0.0)

    skip_reason = None
    scoring_res = {}
    rr_ratio = 1.0
    pattern_type = "none"
    valid_f3 = True

    # DOJI CHECKS
    if c1_is_doji:
        skip_reason = "C1 is Doji, trigger candle too weak"
    elif c2_is_doji:
        if cfg.active_filter_strategy != 'B':
            skip_reason = "C2 is Doji, invalid engulfing (Hanya diizinkan di Filter B)"

    if skip_reason:
        scoring_res = {
            "range_pts": 0, "body_pct": candle_data.get("body_pct", 0), "wick_pct": 0, "cp_pct": 0,
            "ema_label": "None", "market_state": "Doji", "total_score": 0,
            "grade": "N/A", "action_str": "NONE"
        }
        return skip_reason, scoring_res, rr_ratio, pattern_type, valid_f3

    # ONLY RUN STRATEGY IF NO DOJI SKIP REASON
    if cfg.active_filter_strategy == 'B':
        if verbose:
            print(cprint(f"   [STRATEGY] Menggunakan Filter B (Pullback Limit, No Grade)", color))
            
        # [F1_B] Engulfing Trigger & EMA Slow
        fallback_m5_trigger = False
        m5_fallback_source = None
        is_valid, pattern_type = check_engulfing_trigger_b(
            c1_open, c1_close, c2_open, c2_close,
            c2_high, c2_low, c2_is_doji,
            ema_slow, verbose, color
        )
        if not is_valid or pattern_type is None:
            if candle_data.get("timeframe") == "M5" and cfg.filter_c_tfm_enabled:
                from config.filter_c_config import FilterCConfig
                fc_cfg = FilterCConfig()
                tfm_result = check_tf_monitor(symbol, cfg=fc_cfg)
                m5_source = tfm_result.get("m5_trigger_source")
                m5_direction = tfm_result.get("m5_trigger_direction")

                if (
                    tfm_result.get("status") == "STRONG"
                    and m5_source
                    and m5_direction in (DIR_BUY, DIR_SELL)
                ):
                    fallback_m5_trigger = True
                    m5_fallback_source = m5_source
                    pattern_type = "bullish_engulfing" if m5_direction == DIR_BUY else "bearish_engulfing"
                    if verbose:
                        print(cprint(f"   [F1_B] Fallback M5 trigger accepted: {m5_source}", color) + " " + Colors.GREEN)
                else:
                    return "ABORT", scoring_res, rr_ratio, pattern_type, valid_f3
            else:
                return "ABORT", scoring_res, rr_ratio, pattern_type, valid_f3
            
        # [F3_B] EMA Ring Filter
        if not fallback_m5_trigger and cfg.filter_f3_ema_ring_b_enabled:
            valid_ema_ring = check_ema_ring_b(
                c1_high, c1_low, c2_high, c2_low,
                ema_now, pattern_type, verbose, color
            )
            if not valid_ema_ring:
                return "ABORT", scoring_res, rr_ratio, pattern_type, valid_f3

        # [F2_B] Pattern Size
        if not fallback_m5_trigger:
            if cfg.filter_f2_pattern_b_enabled:
                valid_f2_b = check_pattern_size_b(c1_high, c1_low, point, symbol, cfg, verbose, color)
                if not valid_f2_b:
                    pattern_size_pts = round(abs(c1_high - c1_low) / point) if point > 0 else 0
                    skip_reason = f"Pattern size invalid ({pattern_size_pts} pts) untuk Filter B"
                    valid_f3 = False
            else:
                if verbose:
                    print(cprint("   [F2_B] Pattern Size: DISABLED (bypass)", Colors.GRAY))

        # Mock scoring_res for Filter B
        scoring_res = {
            "range_pts": round(abs(c1_high - c1_low) / point), 
            "body_pct": 100, "wick_pct": 0, "cp_pct": 100,
            "ema_label": "None", "market_state": "Filter B", "total_score": 100,
            "grade": "N/A", "action_str": "BUY" if pattern_type.startswith("bullish") else "SELL"
        }

    else:
        if verbose:
            print(cprint(f"   [STRATEGY] Menggunakan Filter A (Scoring/Grade)", color))
            
        # -----------------------------------------------------------------
        # [F1] Engulfing Trigger
        # -----------------------------------------------------------------
        if not cfg.filter_f1_trigger_enabled:
            if verbose: print(cprint("   [--] [F1] Trigger: DISABLED (bypass)", Colors.GRAY))
            pattern_type = "bullish_engulfing" if c1_is_bullish else "bearish_engulfing"
        else:
            is_valid, pattern_type = check_engulfing_trigger(
                c1_open, c1_close, c2_open, c2_close, ema_slow, verbose, color
            )
            if not is_valid or pattern_type is None:
                return "ABORT", scoring_res, rr_ratio, "none", valid_f3

        # -----------------------------------------------------------------
        # [F3] Pattern Size & RR Dinamis
        # -----------------------------------------------------------------
        rr_ratio = 1.5
        valid_f3 = True
        if not cfg.filter_f3_pattern_enabled:
            if verbose: print(cprint("   [--] [F3] Pattern Size: DISABLED (bypass)", Colors.GRAY))
        else:
            valid_f3, rr_ratio = check_pattern_size(c1_high, c1_low, point, cfg, verbose, color)

        # -----------------------------------------------------------------
        # [F2] Scoring & Metrics (Includes F4 Market State implicitly)
        # -----------------------------------------------------------------
        if not cfg.filter_f2_scoring_enabled:
            if verbose: print(cprint("   [--] [F2] Scoring: DISABLED (bypass)", Colors.GRAY))
            scoring_res = {
                "range_pts": 0, "body_pct": 100, "wick_pct": 0, "cp_pct": 100,
                "ema_label": "None", "market_state": "Normal", "total_score": 100,
                "grade": "A+", "action_str": "BUY" if c1_is_bullish else "SELL"
            }
        else:
            scoring_res = calculate_scoring(
                c1_open, c1_close, c1_high, c1_low,
                c2_open, c2_close, c2_high, c2_low,
                avg_range_20, ema_now, ema_20_ago,
                cross_count, side_strength, pattern_type, point,
                cfg, verbose, color
            )

        # Filtering Grade Minimal
        grade_mapping = {"A+": 7, "A": 6, "B+": 5, "B": 4, "C+": 3, "C": 2, "D": 1}
        min_allowed = grade_mapping.get(cfg.min_grade_allowed, 3) # default C+
        grade_str = str(scoring_res.get("grade", "D"))
        curr_grade = grade_mapping.get(grade_str, 1)

        # Tentukan alasan skip jika ada
        if not valid_f3:
            pattern_size_pts = round(abs(c1_high - c1_low) / point) if point > 0 else 0
            skip_reason = f"Pattern size invalid ({pattern_size_pts} pts)"
        elif curr_grade < min_allowed:
            skip_reason = f"Grade {grade_str} di bawah batas {cfg.min_grade_allowed}"

    return skip_reason, scoring_res, rr_ratio, pattern_type, valid_f3
