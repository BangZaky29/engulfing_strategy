# =====================================================
# strategies/engulfing/detector/filter_c_eval.py
# Modul untuk evaluasi Filter C (TF Monitor Check).
# =====================================================

from utils.colors import Colors, cprint
from config.engulfing_config import EngulfingConfig
from ..filters_C import check_tf_monitor

def apply_filter_c(signal: dict, symbol: str, candle_data: dict, pattern_type: str, cfg: EngulfingConfig, verbose: bool):
    """
    Apply Filter C (TF Monitor Check) and update the signal dictionary in-place.
    """
    if not cfg.filter_c_tfm_enabled:
        return

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

                # Update notes JSON
                try:
                    notes_obj = _json.loads(signal.get("notes", "{}"))
                    notes_obj["sl_source"]         = "H1"
                    # ✅ Simpan h1_trigger_source dan trigger time ke notes agar WA bot bisa baca
                    notes_obj["h1_trigger_source"] = tfm_result.get("h1_trigger_source", "")
                    notes_obj["h1_trigger_time"] = tfm_result.get("h1_trigger_time")
                    notes_obj["m15_trigger_source"] = tfm_result.get("m15_trigger_source", "")
                    notes_obj["m15_trigger_time"] = tfm_result.get("m15_trigger_time")
                    notes_obj["m15_trigger_age"] = tfm_result.get("m15_trigger_age")
                    notes_obj["m5_trigger_time"] = tfm_result.get("m5_trigger_time")
                    
                    # ✅ Calculate H1 EMA Distance
                    h1_ema_val = tfm_result.get("h1_trigger_ema")
                    if h1_ema_val and hc.get("open") and cfg.filter_ema_distance_enabled:
                        dist_raw = abs(hc["open"] - h1_ema_val)
                        dist_pts = round(dist_raw / point) if point > 0 else 0
                        min_pts, max_pts = cfg.get_ema_distance_limits(symbol)
                        
                        notes_obj["h1_ema_distance_pts"] = dist_pts
                        notes_obj["h1_ema_distance_min"] = min_pts
                        notes_obj["h1_ema_distance_max"] = max_pts
                        
                        if dist_pts < min_pts:
                            notes_obj["h1_ema_distance_status"] = "INVALID"
                            signal.setdefault("skip_reasons", []).append(f"EMA Distance terlalu dekat, H1 C1 ({dist_pts} pts < {min_pts} min) [INVALID]")
                            if tfm_result.get("status") == "STRONG":
                                tfm_result["status"] = "VALID"
                                tfm_result["status_reason"] = "H1 EMA Distance terlalu dekat"
                        elif dist_pts > max_pts:
                            notes_obj["h1_ema_distance_status"] = "VALID"
                            signal.setdefault("skip_reasons", []).append(f"EMA Distance terlalu jauh, H1 C1 ({dist_pts} pts > {max_pts} max) [VALID-OVEREXTENDED]")
                            if tfm_result.get("status") == "STRONG":
                                tfm_result["status"] = "VALID"
                                tfm_result["status_reason"] = "H1 EMA Distance overextended (kejauhan)"
                        else:
                            notes_obj["h1_ema_distance_status"] = "STRONG"
                            
                    notes_obj["skip_reason"] = signal.get("skip_reason")
                    notes_obj["skip_reasons"] = signal.get("skip_reasons", [])
                    if signal.get("m15_trigger_source"):
                        notes_obj["m15_trigger_source"] = signal["m15_trigger_source"]
                    if signal.get("m5_trigger_source"):
                        notes_obj["m5_trigger_source"] = signal["m5_trigger_source"]
                    
                    # Clean up old legacy fields from notes if they exist
                    notes_obj.pop("sl_price", None)
                    notes_obj.pop("sl_pts", None)
                    notes_obj.pop("tp_price", None)
                    notes_obj.pop("sl_pct", None)
                    notes_obj.pop("rr_ratio", None)
                    notes_obj.pop("target_usd", None)

                    signal["notes"] = _json.dumps(notes_obj)
                except Exception:
                    pass

                if verbose:
                    h1_src = tfm_result.get("h1_trigger_source", "?")
                    print(cprint(
                        f"   🎯 [FC] H1 Trigger Attached | Source: {h1_src} | "
                        f"H1 Close={h1_close:.2f} High={h1_high:.2f} Low={h1_low:.2f}",
                        Colors.CYAN
                    ))

        # Cek apakah arah M5 (pattern_type) searah dengan Bias TF Monitor
        is_aligned = True
        if "Buy" in tfm_result["bias_column"] and pattern_type == "bearish_engulfing":
            is_aligned = False
        elif "Sell" in tfm_result["bias_column"] and pattern_type == "bullish_engulfing":
            is_aligned = False

        skip_reasons = signal.get("skip_reasons", [])
        if tfm_result["status"] != "STRONG":
            reason_detail = tfm_result.get("status_reason", "")
            skip_reasons.append(f"TF Monitor: status {tfm_result['status']} bukan STRONG ({reason_detail})" if reason_detail else f"TF Monitor: status {tfm_result['status']} bukan STRONG")
        if not is_aligned:
            skip_reasons.append(f"TF Monitor: Arah M5 berlawanan dengan Bias ({tfm_result['bias_column']})")

        if skip_reasons:
            signal["is_confirmed"] = False
            signal["skip_reasons"] = skip_reasons
            signal["skip_reason"] = " | ".join(skip_reasons)
            try:
                import json as _json
                notes_obj = _json.loads(signal.get("notes", "{}"))
                notes_obj["skip_reason"] = signal["skip_reason"]
                notes_obj["skip_reasons"] = signal["skip_reasons"]
                signal["notes"] = _json.dumps(notes_obj)
            except Exception:
                pass
            if verbose:
                print(cprint(
                    f"   ❌ [FC] TF Monitor BLOCKED: {signal['skip_reason']}",
                    Colors.YELLOW
                ))
                print(cprint(f"   📡 {tfm_result['snapshot']}", Colors.CYAN))
        else:
            try:
                import json as _json2
                notes_obj = _json2.loads(signal.get("notes", "{}"))
                # Clean up legacy fields
                notes_obj.pop("tp_price", None)
                notes_obj.pop("rr_ratio", None)
                notes_obj.pop("target_usd", None)

                if signal.get("m5_trigger_source"):
                    notes_obj["m5_trigger_source"] = signal["m5_trigger_source"]
                signal["notes"] = _json2.dumps(notes_obj)
                
                # Remove legacy calculated fields from signal payload
                signal.pop("sl_price", None)
                signal.pop("tp_price", None)
                signal.pop("sl_pts", None)
                signal.pop("rr_ratio", None)
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
