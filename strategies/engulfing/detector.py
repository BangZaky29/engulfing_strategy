# =====================================================
# strategies/engulfing/detector.py
# Orchestrator: jalankan semua filter secara berurutan
# =====================================================

import os
from config.engulfing_config import EngulfingConfig
from .filters import check_engulfing_trigger, calculate_scoring, check_pattern_size, evaluate_market_state
from .signal_builder import build_signal


def detect_engulfing(
    candle_data: dict,
    cfg: EngulfingConfig | None = None,
    verbose: bool = False,
) -> dict | None:
    if cfg is None:
        cfg = EngulfingConfig()

    # --- Unpack data ---
    # C1 adalah candle engulfing yg baru close
    c1_open       = candle_data["open_"]
    c1_close      = candle_data["close_"]
    c1_high       = candle_data["high_"]
    c1_low        = candle_data["low_"]
    c1_is_bullish = candle_data["is_bullish"]
    
    # C2 adalah candle yg ditelan
    c2_open       = candle_data["prev_open"]
    c2_close      = candle_data["prev_close"]
    c2_high       = candle_data["prev_high"]
    c2_low        = candle_data["prev_low"]
    c2_is_bullish = candle_data["prev_is_bullish"]

    point  = candle_data.get("point", 0.01)
    digits = candle_data.get("digits", 2)

    # Market State Data
    avg_range_20 = candle_data.get("avg_range_20", 0.0)
    ema_now = candle_data.get("ema_now", 0.0)
    ema_20_ago = candle_data.get("ema_20_ago", 0.0)
    cross_count = candle_data.get("cross_count_20", 0)
    side_strength = candle_data.get("side_strength_20", 0.0)

    warna_c1 = "Hijau [BUY]" if c1_is_bullish else "Merah [SELL]"
    warna_c2 = "Hijau [BUY]" if c2_is_bullish else "Merah [SELL]"

    # --- Header verbose ---
    if verbose:
        print(f"   {'-'*52}")
        print(f"   [FILTER] C1(Engulf)={warna_c1}  C2(Ditela)={warna_c2}")
        print(f"   {'-'*52}")

    # -----------------------------------------------------------------
    # [F1] Engulfing Trigger
    # -----------------------------------------------------------------
    if not cfg.filter_f1_trigger_enabled:
        if verbose: print("   [--] [F1] Trigger: DISABLED (bypass)")
        pattern_type = "bullish_engulfing" if c1_is_bullish else "bearish_engulfing"
    else:
        is_valid, pattern_type = check_engulfing_trigger(
            c1_open, c1_close, c2_open, c2_close, verbose
        )
        if not is_valid or pattern_type is None:
            return None

    # -----------------------------------------------------------------
    # [F3] Pattern Size & RR Dinamis
    # -----------------------------------------------------------------
    rr_ratio = 1.5
    valid_f3 = True
    if not cfg.filter_f3_pattern_enabled:
        if verbose: print("   [--] [F3] Pattern Size: DISABLED (bypass)")
    else:
        valid_f3, rr_ratio = check_pattern_size(c1_high, c1_low, point, cfg, verbose)

    # -----------------------------------------------------------------
    # [F2] Scoring & Metrics (Includes F4 Market State implicitly)
    # -----------------------------------------------------------------
    if not cfg.filter_f2_scoring_enabled:
        if verbose: print("   [--] [F2] Scoring: DISABLED (bypass)")
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
            cfg, verbose
        )

    # Filtering Grade Minimal
    grade_mapping = {"A+": 7, "A": 6, "B+": 5, "B": 4, "C+": 3, "C": 2, "D": 1}
    min_allowed = grade_mapping.get(cfg.min_grade_allowed, 3) # default C+
    grade_str = str(scoring_res.get("grade", "D"))
    curr_grade = grade_mapping.get(grade_str, 1)

    # Tentukan alasan skip jika ada
    skip_reason = None
    if not valid_f3:
        pattern_size_pts = round(abs(c1_high - c1_low) / point) if point > 0 else 0
        skip_reason = f"Pattern size invalid ({pattern_size_pts} pts)"
    elif curr_grade < min_allowed:
        skip_reason = f"Grade {grade_str} di bawah batas {cfg.min_grade_allowed}"

    # -----------------------------------------------------------------
    # Build sinyal (baik dikonfirmasi maupun dilewati)
    # -----------------------------------------------------------------
    signal = build_signal(
        candle_data, pattern_type, scoring_res, rr_ratio, cfg
    )

    if skip_reason:
        signal["is_confirmed"] = False
        signal["skip_reason"] = skip_reason
        if verbose:
            print(f"   >> SKIP: {skip_reason}")
    else:
        signal["is_confirmed"] = True
        signal["skip_reason"] = None
        if verbose:
            sl_pts = signal.get("sl_pts", 0)
            sl_price = signal.get("sl_price", 0.0)
            print(f"   {'-'*52}")
            print(f"   {pattern_type.upper()} LOLOS SEMUA FILTER!")
            print(f"   Engulfing | {signal['symbol']} | {signal['timeframe']} | {scoring_res['action_str']} | Grade : {scoring_res['grade']} | B : {scoring_res['body_pct']}% | CP : {scoring_res['cp_pct']}% | RR : {signal['rr_ratio']} | SL : {sl_price} ({sl_pts}pts)")
            print(f"   {'-'*52}")

    return signal
