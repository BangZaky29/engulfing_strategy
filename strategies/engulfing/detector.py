# =====================================================
# strategies/engulfing/detector.py
# Orchestrator: jalankan semua filter secara berurutan
# =====================================================

import os
from config.engulfing_config import EngulfingConfig
from config.filter_c_config import FilterCConfig
from .filters_A.f1_trigger import check_engulfing_trigger
from .filters_A.f2_scoring import calculate_scoring
from .filters_A.f3_pattern import check_pattern_size
from .filters_A.f4_market_state import evaluate_market_state
from .filters_B import check_engulfing_trigger_b, check_pattern_size_b, check_ema_ring_b
from .filters_C import check_tf_monitor
from .filters_C.f4_state_manager import DIR_BUY, DIR_SELL
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
                        return None
                else:
                    return None
                
            # [F3_B] EMA Ring Filter
            if not fallback_m5_trigger and cfg.filter_f3_ema_ring_b_enabled:
                valid_ema_ring = check_ema_ring_b(
                    c1_high, c1_low, c2_high, c2_low,
                    ema_now, pattern_type, verbose, color
                )
                if not valid_ema_ring:
                    return None

            # [F2_B] Pattern Size
            if not fallback_m5_trigger:
                if cfg.filter_f2_pattern_b_enabled:
                    valid_f2_b = check_pattern_size_b(c1_high, c1_low, point, symbol, cfg, verbose, color)
                    if not valid_f2_b:
                        pattern_size_pts = round(abs(c1_high - c1_low) / point) if point > 0 else 0
                        skip_reason = f"Pattern size invalid ({pattern_size_pts} pts) untuk Filter B"
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

    signal["skip_reasons"] = [skip_reason] if skip_reason else []
    if skip_reason:
        signal["is_confirmed"] = False
        signal["skip_reason"] = skip_reason
        if verbose:
            print(cprint(f"   {skip_msg(skip_reason)}", Colors.YELLOW))
        try:
            import json as _json
            notes_obj = _json.loads(signal.get("notes", "{}"))
            notes_obj["skip_reason"] = signal["skip_reason"]
            notes_obj["skip_reasons"] = signal["skip_reasons"]
            signal["notes"] = _json.dumps(notes_obj)
        except Exception:
            pass
    else:
        signal["is_confirmed"] = True
        signal["skip_reason"] = None

        # =============================================================
        # [FC] Filter C — TF Monitor Check
        # Hanya dijalankan jika sinyal sudah lolos Filter A/B.
        # Blocking: WAIT/LATE → skip. TP selalu 1:1 (jarak OP–SL).
        # =============================================================
        if cfg.filter_c_tfm_enabled:
            try:
                from config.filter_c_config import FilterCConfig

                fc_cfg = FilterCConfig()
                tfm_result = check_tf_monitor(symbol, cfg=fc_cfg)

                # Inject TFM data ke signal
                signal["tfm_status"] = tfm_result["status"]
                signal["tfm_bias"]   = tfm_result["bias_column"]
                signal["tfm_snapshot"] = tfm_result["snapshot"]
                signal["m5_trigger_source"] = tfm_result.get("m5_trigger_source")
                signal["m5_trigger_direction"] = tfm_result.get("m5_trigger_direction")
                signal["m15_trigger_source"] = tfm_result.get("m15_trigger_source")
                signal["h1_trigger_time"] = tfm_result.get("h1_trigger_time")
                signal["m15_trigger_time"] = tfm_result.get("m15_trigger_time")
                signal["m15_trigger_age"] = tfm_result.get("m15_trigger_age")
                signal["m5_trigger_time"] = tfm_result.get("m5_trigger_time")

                try:
                    import json as _json
                    notes_obj = _json.loads(signal.get("notes", "{}"))
                    notes_obj["h1_trigger_source"] = tfm_result.get("h1_trigger_source", "")
                    notes_obj["h1_trigger_time"] = tfm_result.get("h1_trigger_time")
                    notes_obj["m15_trigger_source"] = tfm_result.get("m15_trigger_source", "")
                    notes_obj["m15_trigger_time"] = tfm_result.get("m15_trigger_time")
                    notes_obj["m15_trigger_age"] = tfm_result.get("m15_trigger_age")
                    notes_obj["m5_trigger_source"] = tfm_result.get("m5_trigger_source", "")
                    notes_obj["m5_trigger_time"] = tfm_result.get("m5_trigger_time")
                    notes_obj["skip_reason"] = signal.get("skip_reason")
                    notes_obj["skip_reasons"] = signal.get("skip_reasons", [])
                    signal["notes"] = _json.dumps(notes_obj)
                except Exception:
                    pass

                # ─────────────────────────────────────────────────────────
                # Dynamic SL dari H1 Trigger Candle
                # Rule:
                #   0%   = Close H1 trigger
                #   100% = High H1 trigger (SELL) | Low H1 trigger (BUY)
                #   SL   = Close + (range × sl_h1_pct)   → SELL
                #   SL   = Close - (range × sl_h1_pct)   → BUY
                #   TP   = OP ± |OP - SL| × rr_ratio     (1:1 default)
                # ─────────────────────────────────────────────────────────
                if tfm_result.get("h1_trigger_candle"):
                    import json as _json
                    hc = tfm_result["h1_trigger_candle"]
                    signal["h1_trigger_open"]   = hc["open"]
                    signal["h1_trigger_high"]   = hc["high"]
                    signal["h1_trigger_low"]    = hc["low"]
                    signal["h1_trigger_close"]  = hc["close"]
                    signal["h1_trigger_source"] = tfm_result.get("h1_trigger_source", "")

                    op    = signal.get("op_price", 0.0)
                    point = candle_data.get("point", 0.01)

                    if op > 0 and point > 0:
                        h1_close   = hc["close"]
                        h1_high    = hc["high"]
                        h1_low     = hc["low"]
                        sl_h1_pct  = fc_cfg.sl_h1_pct  # default 0.30

                        if pattern_type == "bearish_engulfing":
                            # SELL: range dari H1_close ke H1_high (ujung ekor atas)
                            # SL ditaruh 30% DI ATAS High
                            range_ref = h1_high - h1_close
                            new_sl    = h1_high + (range_ref * sl_h1_pct)
                        else:
                            # BUY: range dari H1_close ke H1_low (ujung ekor bawah)
                            # SL ditaruh 30% DI BAWAH Low
                            range_ref = h1_close - h1_low
                            new_sl    = h1_low - (range_ref * sl_h1_pct)

                        sl_dist    = abs(op - new_sl)
                        new_rr     = 1.0
                        new_sl_pts = round(sl_dist / point)

                        if pattern_type == "bearish_engulfing":
                            new_tp = op - (sl_dist * new_rr)
                        else:
                            new_tp = op + (sl_dist * new_rr)

                        # Update signal
                        signal["rr_ratio"] = new_rr
                        signal["sl_price"] = new_sl
                        signal["sl_pts"]   = new_sl_pts
                        signal["tp_price"] = new_tp

                        # Update notes JSON
                        try:
                            notes_obj = _json.loads(signal.get("notes", "{}"))
                            notes_obj["sl_price"]          = new_sl
                            notes_obj["sl_pts"]            = new_sl_pts
                            notes_obj["tp_price"]          = new_tp
                            notes_obj["sl_source"]         = "H1"
                            notes_obj["sl_pct"]            = sl_h1_pct
                            notes_obj["rr_ratio"]          = new_rr
                            # ✅ Simpan h1_trigger_source dan trigger time ke notes agar WA bot bisa baca
                            notes_obj["h1_trigger_source"] = tfm_result.get("h1_trigger_source", "")
                            notes_obj["h1_trigger_time"] = tfm_result.get("h1_trigger_time")
                            notes_obj["m15_trigger_source"] = tfm_result.get("m15_trigger_source", "")
                            notes_obj["m15_trigger_time"] = tfm_result.get("m15_trigger_time")
                            notes_obj["m15_trigger_age"] = tfm_result.get("m15_trigger_age")
                            notes_obj["m5_trigger_time"] = tfm_result.get("m5_trigger_time")
                            notes_obj["skip_reason"] = signal.get("skip_reason")
                            notes_obj["skip_reasons"] = signal.get("skip_reasons", [])
                            if signal.get("m15_trigger_source"):
                                notes_obj["m15_trigger_source"] = signal["m15_trigger_source"]
                            if signal.get("m5_trigger_source"):
                                notes_obj["m5_trigger_source"] = signal["m5_trigger_source"]
                            signal["notes"] = _json.dumps(notes_obj)
                        except Exception:
                            pass

                        if verbose:
                            h1_src = tfm_result.get("h1_trigger_source", "?")
                            print(cprint(
                                f"   🎯 [FC] Dynamic SL (H1) | Trigger: {h1_src} | "
                                f"H1 Close={h1_close:.2f} High={h1_high:.2f} Low={h1_low:.2f} | "
                                f"Range={range_ref:.2f} | SL={new_sl:.2f} ({new_sl_pts}pts) | "
                                f"TP={new_tp:.2f} | RR={new_rr}",
                                Colors.CYAN
                            ))

                # Cek apakah arah M5 (pattern_type) searah dengan Bias TF Monitor
                is_aligned = True
                if "Buy" in tfm_result["bias_column"] and pattern_type == "bearish_engulfing":
                    is_aligned = False
                elif "Sell" in tfm_result["bias_column"] and pattern_type == "bullish_engulfing":
                    is_aligned = False

                skip_reasons = []
                if tfm_result["status"] != "STRONG":
                    skip_reasons.append(f"TF Monitor: status {tfm_result['status']} bukan STRONG")
                if not is_aligned:
                    skip_reasons.append(f"TF Monitor: Arah M5 berlawanan dengan Bias ({tfm_result['bias_column']})")

                if skip_reasons:
                    signal["is_confirmed"] = False
                    signal["skip_reasons"] = skip_reasons
                    signal["skip_reason"] = " | ".join(skip_reasons)
                    if verbose:
                        print(cprint(
                            f"   ❌ [FC] TF Monitor BLOCKED: {signal['skip_reason']}",
                            Colors.YELLOW
                        ))
                        print(cprint(f"   📡 {tfm_result['snapshot']}", Colors.CYAN))
                else:
                    signal["rr_ratio"] = 1.0
                    try:
                        import json as _json2
                        op = signal.get("op_price", 0.0)
                        sl = signal.get("sl_price", 0.0)
                        if op > 0 and sl > 0:
                            sl_dist = abs(op - sl)
                            if pattern_type == "bearish_engulfing":
                                new_tp = op - sl_dist
                            else:
                                new_tp = op + sl_dist
                            signal["tp_price"] = new_tp
                            notes_obj = _json2.loads(signal.get("notes", "{}"))
                            notes_obj["tp_price"] = new_tp
                            notes_obj["rr_ratio"] = 1.0
                            if signal.get("m5_trigger_source"):
                                notes_obj["m5_trigger_source"] = signal["m5_trigger_source"]
                            signal["notes"] = _json2.dumps(notes_obj)
                    except Exception:
                        pass

                    if verbose:
                        status_emoji = {"STRONG": "🟢🔥", "VALID": "🟢", "EARLY": "🟡"}.get(tfm_result["status"], "❓")
                        print(cprint(f"   ✅ [FC] TF Monitor: {status_emoji} {tfm_result['status']} | {tfm_result['bias_column']}", Colors.GREEN))
                        print(cprint(f"   📡 {tfm_result['snapshot']}", Colors.CYAN))

            except Exception as e:
                # Filter C failure tidak boleh block sinyal
                if verbose:
                    print(cprint(f"   ⚠️ [FC] TF Monitor error (non-blocking): {e}", Colors.YELLOW))

        if verbose and signal.get("is_confirmed"):
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
