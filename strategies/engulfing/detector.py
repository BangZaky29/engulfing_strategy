# =====================================================
# strategies/engulfing/detector.py
# Orchestrator: jalankan semua filter secara berurutan
# =====================================================

import os
from config.engulfing_config import EngulfingConfig
from .filters_A.f1_trigger import check_engulfing_trigger
from .filters_A.f2_scoring import calculate_scoring
from .filters_A.f3_pattern import check_pattern_size
from .filters_A.f4_market_state import evaluate_market_state
from .filters_B import check_engulfing_trigger_b, check_pattern_size_b, check_ema_ring_b
from .signal_builder import build_signal
from utils.colors import Colors, cprint, skip_msg, grade_color


def detect_engulfing(
    candle_data: dict,
    cfg: EngulfingConfig | None = None,
    verbose: bool = False,
    color: str = "",
) -> dict | None:
    if cfg is None:
        cfg = EngulfingConfig()

    symbol = candle_data.get("symbol", "XAUUSD")

    # --- Unpack data ---
    # C1 adalah candle engulfing yg baru close
    c1_open       = candle_data["open_"]
    c1_close      = candle_data["close_"]
    c1_high       = candle_data["high_"]
    c1_low        = candle_data["low_"]
    c1_is_bullish = candle_data["is_bullish"]
    
    c1_is_doji    = candle_data.get("is_doji", False)
    
    # C2 adalah candle yg ditelan
    c2_open       = candle_data["prev_open"]
    c2_close      = candle_data["prev_close"]
    c2_high       = candle_data["prev_high"]
    c2_low        = candle_data["prev_low"]
    c2_is_bullish = candle_data["prev_is_bullish"]
    c2_is_doji    = candle_data.get("prev_is_doji", False)

    point  = candle_data.get("point", 0.01)
    digits = candle_data.get("digits", 2)

    # Market State Data
    avg_range_20 = candle_data.get("avg_range_20", 0.0)
    ema_now = candle_data.get("ema_now", 0.0)
    ema_slow = candle_data.get("ema_slow", 0.0)
    ema_20_ago = candle_data.get("ema_20_ago", 0.0)
    cross_count = candle_data.get("cross_count_20", 0)
    side_strength = candle_data.get("side_strength_20", 0.0)

    if c1_is_doji:
        warna_c1 = f"Putih [DOJI {'BUY' if c1_is_bullish else 'SELL'}]"
        clr_c1 = Colors.GRAY
    else:
        warna_c1 = "Hijau [BUY]" if c1_is_bullish else "Merah [SELL]"
        clr_c1 = Colors.GREEN if c1_is_bullish else Colors.RED

    if c2_is_doji:
        warna_c2 = f"Putih [DOJI {'BUY' if c2_is_bullish else 'SELL'}]"
        clr_c2 = Colors.GRAY
    else:
        warna_c2 = "Hijau [BUY]" if c2_is_bullish else "Merah [SELL]"
        clr_c2 = Colors.GREEN if c2_is_bullish else Colors.RED

    # --- Header verbose ---
    if verbose:
        print(cprint(f"   {'-'*52}", color))
        c1_label = cprint(warna_c1, clr_c1, bold=True)
        c2_label = cprint(warna_c2, clr_c2, bold=True)
        print(cprint("   [FILTER] ", color) + f"C1(Engulf)={c1_label}  C2(Ditela)={c2_label}")
        print(cprint(f"   {'-'*52}", color))

    skip_reason = None
    scoring_res = {}
    rr_ratio = 1.0
    pattern_type = "none"

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

    # ONLY RUN STRATEGY IF NO DOJI SKIP REASON
    if not skip_reason:
        if cfg.active_filter_strategy == 'B':
            if verbose:
                print(cprint(f"   [STRATEGY] Menggunakan Filter B (Pullback Limit, No Grade)", color))
                
            # [F1_B] Engulfing Trigger & EMA Slow
            is_valid, pattern_type = check_engulfing_trigger_b(
                c1_open, c1_close, c2_open, c2_close,
                c2_high, c2_low, c2_is_doji,
                ema_slow, verbose, color
            )
            if not is_valid or pattern_type is None:
                return None
                
            # [F3_B] EMA Ring Filter
            if cfg.filter_f3_ema_ring_b_enabled:
                valid_ema_ring = check_ema_ring_b(
                    c1_high, c1_low, c2_high, c2_low,
                    ema_now, pattern_type, verbose, color
                )
                if not valid_ema_ring:
                    return None

            # [F2_B] Pattern Size
            valid_f2_b = check_pattern_size_b(c1_high, c1_low, point, symbol, cfg, verbose, color)
            if not valid_f2_b:
                pattern_size_pts = round(abs(c1_high - c1_low) / point) if point > 0 else 0
                skip_reason = f"Pattern size invalid ({pattern_size_pts} pts) untuk Filter B"
                
            # Mock scoring_res for Filter B
            scoring_res = {
                "range_pts": round(abs(c1_high - c1_low) / point), 
                "body_pct": 100, "wick_pct": 0, "cp_pct": 100,
                "ema_label": "None", "market_state": "Filter B", "total_score": 100,
                "grade": "N/A", "action_str": "BUY" if c1_is_bullish else "SELL"
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
                return None

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

        if cfg.active_filter_strategy != 'B':
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
        else:
            # Filter B: valid_f3 was calculated differently, let's keep it consistent
            pass

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
            print(cprint(f"   {skip_msg(skip_reason)}", Colors.YELLOW))
    else:
        signal["is_confirmed"] = True
        signal["skip_reason"] = None
        if verbose:
            sl_pts = signal.get("sl_pts", 0)
            sl_price = signal.get("sl_price", 0.0)
            print(cprint(f"   {'-'*52}", color))
            session_str = signal.get("trading_session", "Unknown")
            print(cprint(f"   {pattern_type.upper()} LOLOS SEMUA FILTER! ✅", Colors.GREEN, bold=True))
            print(cprint(
                f"   Engulfing | {signal['symbol']} | {signal['timeframe']} | "
                f"{scoring_res['action_str']} | Grade : {grade_color(str(scoring_res['grade']))} | "
                f"B : {scoring_res['body_pct']}% | CP : {scoring_res['cp_pct']}% | "
                f"RR : {signal['rr_ratio']} | SL : {sl_price} ({sl_pts}pts) | Sesi : {session_str}",
                Colors.GREEN
            ))
            print(cprint(f"   {'-'*52}", color))

    return signal
