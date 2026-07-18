# =====================================================
# app/tfm_logger.py
# Log snapshot TF Monitor secara periodik.
# =====================================================

import json
from datetime import datetime
from database import SignalRepo
from utils.colors import Colors, cprint

def log_tfm_snapshot(symbol: str, fc_cfg, last_tfm_snapshot: dict) -> None:
    """
    Ambil snapshot terbaru dan jika ada perubahan (new event), log dan upsert ke SignalRepo.
    """
    try:
        from strategies.engulfing.filters_C import check_tf_monitor
        tfm_result = check_tf_monitor(symbol, cfg=fc_cfg)
        snapshot = tfm_result.get("snapshot", "")
        is_new = tfm_result.get("is_new_event", False)

        if is_new and snapshot and snapshot != last_tfm_snapshot.get(symbol):
            print(cprint(f"📡 {snapshot}", Colors.CYAN))
            last_tfm_snapshot[symbol] = snapshot

            # Insert TFM status change ke Supabase untuk WA notification
            tfm_signal = {
                "symbol": symbol,
                "timeframe": f"TFM_{tfm_result['status']}",
                "signal_time": datetime.now(),
                "pattern_type": "bullish_engulfing" if "Buy" in tfm_result.get("bias_column", "") else "bearish_engulfing",
                "prev_open": 0, "prev_close": 0, "prev_high": 0, "prev_low": 0,
                "curr_open": 0, "curr_close": 0, "curr_high": 0, "curr_low": 0,
                "engulf_ratio": 0, "volume": 0,
                "ema_fast_value": 0, "ema_slow_value": 0,
                "ema_trend": tfm_result["status"],
                "confidence_score": 0,
                "is_confirmed": True,
                "ticket_id": None,
                "notes": json.dumps({
                    "ticket_id": "TFM_STATUS_CHANGE",
                    "tfm_status": tfm_result["status"],
                    "tfm_bias": tfm_result["bias_column"],
                    "tfm_snapshot": snapshot,
                    "grade": "N/A", "action_str": "NONE",
                    "body_pct": 0, "cp_pct": 0, "sl_pct_used": 0,
                    "rr_ratio": 0, "sl_pts": 0, "ring_pts": 0,
                    "op_price": 0, "sl_price": 0, "tp_price": None,
                    "total_score": 0, "market_state": "TFM",
                    "trading_session": "",
                }),
            }
            SignalRepo.upsert(tfm_signal)

    except Exception as e:
        pass  # TFM error non-blocking
