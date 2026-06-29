# =====================================================
# strategies/engulfing/filters_C/__init__.py
# Filter C — TF Monitor
# Public API: check_tf_monitor()
# =====================================================

from __future__ import annotations
import logging
from datetime import datetime, timezone

import MetaTrader5 as mt5

from config.filter_c_config import FilterCConfig
from .f1_triggers import find_latest_trigger, DIR_NONE, DIR_BUY, DIR_SELL
from .f2_bias_logic import (
    find_latest_h1_state, main_bias_column, validity_status,
    build_event_key, build_snapshot,
)
from .f3_ema_utils import calculate_ema_series
from .f4_state_manager import TFMState, TFMonitorStateManager, clear_state, state_age_candles

logger = logging.getLogger("filter_c")

# =====================================================
# MT5 TF Map
# =====================================================
_TF_MT5_MAP = {
    "M1": mt5.TIMEFRAME_M1,  # type: ignore[attr-defined]
    "M5": mt5.TIMEFRAME_M5,  # type: ignore[attr-defined]
    "M15": mt5.TIMEFRAME_M15,  # type: ignore[attr-defined]
    "M30": mt5.TIMEFRAME_M30,  # type: ignore[attr-defined]
    "H1": mt5.TIMEFRAME_H1,  # type: ignore[attr-defined]
    "H4": mt5.TIMEFRAME_H4,  # type: ignore[attr-defined]
    "D1": mt5.TIMEFRAME_D1,  # type: ignore[attr-defined]
}

# =====================================================
# Global State Manager (per-symbol)
# =====================================================
_managers: dict[str, TFMonitorStateManager] = {}


def _get_manager(symbol: str) -> TFMonitorStateManager:
    if symbol not in _managers:
        _managers[symbol] = TFMonitorStateManager()
    return _managers[symbol]


# =====================================================
# Data Fetcher
# =====================================================
def _fetch_candles(symbol: str, tf_label: str, count: int) -> list[dict]:
    """
    Fetch closed candles dari MT5 untuk timeframe tertentu.
    Return list of dicts: {open, high, low, close, time}
    Index 0 = oldest, -1 = newest.
    """
    tf_mt5 = _TF_MT5_MAP.get(tf_label)
    if tf_mt5 is None:
        logger.warning(f"[TFM] Unknown timeframe: {tf_label}")
        return []

    # Shift 1 → skip running candle (ambil mulai dari candle closed terakhir)
    rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 1, count)  # type: ignore[attr-defined]
    if rates is None or len(rates) == 0:
        return []

    candles = []
    for r in rates:
        candles.append({
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "time": datetime.fromtimestamp(r["time"], tz=timezone.utc),
        })

    return candles


def _get_point(symbol: str) -> float:
    """Get point size dari MT5 symbol info."""
    info = mt5.symbol_info(symbol)  # type: ignore[attr-defined]
    if info is None:
        return 0.01  # fallback XAU
    return info.point


# =====================================================
# Public API
# =====================================================
def check_tf_monitor(
    symbol: str,
    cfg: FilterCConfig | None = None,
) -> dict:
    """
    Jalankan TF Monitor check untuk symbol tertentu.
    
    Return dict:
    {
        "status": "STRONG" | "VALID" | "EARLY" | "LATE" | "WAIT",
        "bias_column": "Buy+" | "Sell+" | "Buy" | "Sell" | "Wait",
        "snapshot": "TF Monitor | STRONG | Buy+ | H1 ... | M15 ... | M5 ... | XAUUSD",
        "is_new_event": True/False,
        "h1_state": TFMState,
        "m15_state": TFMState,
        "m5_state": TFMState,
    }
    """
    if cfg is None:
        cfg = FilterCConfig()

    manager = _get_manager(symbol)
    point = _get_point(symbol)

    # Fetch lookback bars + buffer untuk DB/Marubozu extra
    fetch_count = cfg.trigger_lookback_bars + cfg.db_max_candles + 10

    # =========================================================
    # 1. Fetch candle data untuk H1, M15, M5
    # =========================================================
    h1_candles = _fetch_candles(symbol, "H1", fetch_count)
    m15_candles = _fetch_candles(symbol, "M15", fetch_count)
    m5_candles = _fetch_candles(symbol, "M5", fetch_count)

    if len(h1_candles) < 10 or len(m15_candles) < 10 or len(m5_candles) < 10:
        return {
            "status": "WAIT",
            "bias_column": "Wait",
            "snapshot": f"TF Monitor | WAIT DATA | loading history | {symbol}",
            "is_new_event": False,
            "h1_state": manager.h1_state,
            "m15_state": manager.m15_state,
            "m5_state": manager.m5_state,
        }

    # =========================================================
    # 2. Calculate EMA per-timeframe
    # =========================================================
    h1_closes = [c["close"] for c in h1_candles]
    m15_closes = [c["close"] for c in m15_candles]
    m5_closes = [c["close"] for c in m5_candles]

    h1_ema = calculate_ema_series(h1_closes, cfg.ema_period)
    m15_ema = calculate_ema_series(m15_closes, cfg.ema_period)
    m5_ema = calculate_ema_series(m5_closes, cfg.ema_period)

    # =========================================================
    # 3. Update states (hanya re-scan jika candle closed berubah)
    # =========================================================
    # H1
    h1_last_time = h1_candles[-1]["time"] if h1_candles else None
    if manager.should_rescan("H1", h1_last_time):
        h1_result = find_latest_h1_state(h1_candles, point, h1_ema, cfg)
        if h1_result:
            manager.h1_state = h1_result
        elif not manager.state_ready.get("H1", False):
            manager.h1_state = clear_state()
        manager.mark_scanned("H1", h1_last_time)

    # M15
    m15_last_time = m15_candles[-1]["time"] if m15_candles else None
    if manager.should_rescan("M15", m15_last_time):
        m15_result = find_latest_trigger(m15_candles, point, m15_ema, cfg)
        if m15_result:
            manager.m15_state = TFMState(
                direction=m15_result["direction"],
                source=m15_result["source"],
                time=m15_result["time"],
                range_points=m15_result["range_points"],
            )
        elif not manager.state_ready.get("M15", False):
            manager.m15_state = clear_state()
        manager.mark_scanned("M15", m15_last_time)

    # M5
    m5_last_time = m5_candles[-1]["time"] if m5_candles else None
    if manager.should_rescan("M5", m5_last_time):
        m5_result = find_latest_trigger(m5_candles, point, m5_ema, cfg)
        if m5_result:
            manager.m5_state = TFMState(
                direction=m5_result["direction"],
                source=m5_result["source"],
                time=m5_result["time"],
                range_points=m5_result["range_points"],
            )
        elif not manager.state_ready.get("M5", False):
            manager.m5_state = clear_state()
        manager.mark_scanned("M5", m5_last_time)

    # =========================================================
    # 4. Calculate status & bias
    # =========================================================
    status = validity_status(
        manager.h1_state, manager.m15_state,
        h1_candles, m15_candles,
        h1_ema, m15_ema,
        cfg,
    )
    bias_col = main_bias_column(manager.h1_state, manager.m15_state)

    # =========================================================
    # 5. Build event key & detect changes
    # =========================================================
    event_key = build_event_key(
        manager.h1_state, manager.m15_state, manager.m5_state,
        bias_col, status,
    )

    is_new_event = False

    if not manager.has_snapshot:
        # First load
        manager.h1_new = manager.h1_state.direction != DIR_NONE and manager.h1_state.time is not None
        manager.m15_new = manager.m15_state.direction != DIR_NONE and manager.m15_state.time is not None
        manager.m5_new = manager.m5_state.direction != DIR_NONE and manager.m5_state.time is not None

        snapshot = build_snapshot(
            manager, h1_candles, m15_candles, m5_candles,
            h1_ema, m15_ema, m5_ema,
            status, bias_col, symbol, cfg.use_ema_filter,
        )
        manager.save_notified_states(event_key, snapshot)
        is_new_event = True

    elif event_key != manager.last_event_key:
        # State changed
        manager.detect_new_markers()

        snapshot = build_snapshot(
            manager, h1_candles, m15_candles, m5_candles,
            h1_ema, m15_ema, m5_ema,
            status, bias_col, symbol, cfg.use_ema_filter,
        )
        manager.save_notified_states(event_key, snapshot)
        is_new_event = True
    else:
        snapshot = manager.last_snapshot

    # =========================================================
    # 6. Cari H1 Trigger Candle
    # =========================================================
    h1_trigger_candle = None
    if manager.h1_state and manager.h1_state.time:
        for c in h1_candles:
            if c["time"] == manager.h1_state.time:
                h1_trigger_candle = c
                break

    return {
        "status": status,
        "bias_column": bias_col,
        "snapshot": snapshot,
        "is_new_event": is_new_event,
        "h1_state": manager.h1_state,
        "m15_state": manager.m15_state,
        "m5_state": manager.m5_state,
        "h1_trigger_candle": h1_trigger_candle,
        "h1_trigger_source": manager.h1_state.source if manager.h1_state else None,
        "h1_trigger_time": manager.h1_state.time.strftime("%H:%M") if manager.h1_state and manager.h1_state.time else None,
        "m15_trigger_source": manager.m15_state.source if manager.m15_state else None,
        "m15_trigger_time": manager.m15_state.time.strftime("%H:%M") if manager.m15_state and manager.m15_state.time else None,
        "m15_trigger_age": state_age_candles(manager.m15_state, m15_candles),
        "m5_trigger_source": manager.m5_state.source if manager.m5_state else None,
        "m5_trigger_time": manager.m5_state.time.strftime("%H:%M") if manager.m5_state and manager.m5_state.time else None,
        "m5_trigger_direction": manager.m5_state.direction if manager.m5_state else 0,
    }


__all__ = ["check_tf_monitor", "FilterCConfig"]
