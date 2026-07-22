# =====================================================
# strategies/engulfing/filters_C/f2_bias_logic.py
# H1 Bias, M15 Confirmation, Validity Status
# Transfer dari BiasLogic.mqh
# =====================================================

from __future__ import annotations
from config.filter_c_config import FilterCConfig
from .trigger_scanner import find_latest_trigger, get_trigger_state, DIR_NONE, DIR_BUY, DIR_SELL, DIR_MIXED
from .f3_ema_utils import get_ema_value, ema_relation_text
from .f4_state_manager import (
    TFMState, clear_state, direction_to_string, state_key,
    state_age_candles, state_text, TFMonitorStateManager,
)


def find_latest_h1_state(
    h1_candles: list[dict], point: float,
    ema_values: list[float], cfg: FilterCConfig,
) -> TFMState | None:
    """
    Scan H1 trigger terbaru. Hanya terima Buy atau Sell (skip Mixed).
    Transfer dari TFM_FindLatestH1State() di BiasLogic.mqh.
    """
    total_bars = len(h1_candles)
    if total_bars < 10:
        return None

    max_shift = cfg.trigger_lookback_bars
    extra = max(cfg.marubozu_compare_candles, cfg.db_max_candles)
    max_allowed = total_bars - extra - 2
    max_shift = min(max_shift, max_allowed)

    if max_shift < 1:
        return None

    found = None
    for shift in range(max_shift, 0, -1):
        state = get_trigger_state(h1_candles, shift, point, ema_values, cfg, tf="H1")
        if state and state["direction"] in (DIR_BUY, DIR_SELL):
            found = TFMState(
                direction=state["direction"],
                source=state["source"],
                time=state["time"],
                range_points=state["range_points"],
            )

    return found


def main_bias_column(h1_state: TFMState, m15_state: TFMState) -> str:
    """
    Return "Buy", "Sell", "Buy+", "Sell+".
    Buy+ = H1 Buy DAN M15 Buy (searah).
    Transfer dari TFM_MainBiasColumn() di BiasLogic.mqh.
    """
    if h1_state.direction == DIR_BUY and m15_state.direction == DIR_BUY:
        return "Buy+"
    if h1_state.direction == DIR_SELL and m15_state.direction == DIR_SELL:
        return "Sell+"
    return direction_to_string(h1_state.direction)


def h1_m15_aligned(h1_state: TFMState, m15_state: TFMState) -> bool:
    """Cek apakah H1 dan M15 searah."""
    if h1_state.direction not in (DIR_BUY, DIR_SELL):
        return False
    if m15_state.direction not in (DIR_BUY, DIR_SELL):
        return False
    return h1_state.direction == m15_state.direction


def validity_status(
    h1_state: TFMState, m15_state: TFMState, m5_state: TFMState,
    h1_candles: list[dict], m15_candles: list[dict], m5_candles: list[dict],
    h1_ema: list[float], m15_ema: list[float],
    cfg: FilterCConfig,
) -> tuple[str, str]:
    """
    Hitung status validitas: STRONG / VALID / EARLY / LATE / WAIT.
    Transfer dari TFM_ValidityStatus() di BiasLogic.mqh.
    
    Rules:
    - WAIT: H1 dan M15 belum searah
    - LATE: H1 age >= 5
    - STRONG: H1+M15 Trend, H1 age <= strong_h1_max_age, M15 age <= strong_m15_max_age, dan M5 age == 0 (fresh trigger)
    - EARLY: H1 atau M15 Rev, H1 age <= strong_h1_max_age, M15 age <= strong_m15_max_age, dan M5 age == 0 (fresh trigger)
    - VALID: sisanya
    """
    if not h1_m15_aligned(h1_state, m15_state):
        return "WAIT", "H1 dan M15 belum searah"

    h1_age = state_age_candles(h1_state, h1_candles)
    m15_age = state_age_candles(m15_state, m15_candles)
    m5_age = state_age_candles(m5_state, m5_candles)

    # EMA relation
    h1_close = 0.0
    h1_ema_val = 0.0
    if h1_state.time and h1_candles:
        for i, c in enumerate(h1_candles):
            if c.get("time") == h1_state.time:
                h1_close = float(c.get("close", 0.0))
                h1_ema_val = get_ema_value(h1_ema, len(h1_candles) - i)
                break

    m15_close = 0.0
    m15_ema_val = 0.0
    if m15_state.time and m15_candles:
        for i, c in enumerate(m15_candles):
            if c.get("time") == m15_state.time:
                m15_close = float(c.get("close", 0.0))
                m15_ema_val = get_ema_value(m15_ema, len(m15_candles) - i)
                break

    h1_ema_text = ema_relation_text(h1_state.direction, h1_close, h1_ema_val, cfg.use_ema_filter)
    m15_ema_text = ema_relation_text(m15_state.direction, m15_close, m15_ema_val, cfg.use_ema_filter)

    h1_trend = h1_ema_text == "Trend"
    m15_trend = m15_ema_text == "Trend"
    h1_rev = h1_ema_text == "Rev"
    m15_rev = m15_ema_text == "Rev"

    # LATE: H1 terlalu tua
    if h1_age >= cfg.h1_late_age:
        return "LATE", f"H1 terlalu tua (age={h1_age})"

    # Cek keselarasan dan kebaruan M5 trigger
    m5_has_trigger = m5_state.direction in (DIR_BUY, DIR_SELL) and m5_state.time is not None
    m5_aligned = m5_has_trigger and (m5_state.direction == h1_state.direction)
    m5_fresh = m5_aligned and (m5_age == 0)

    # STRONG: keduanya Trend, H1 dan M15 masih fresh, M5 searah dan fresh (age=0)
    if h1_trend and m15_trend and h1_age <= cfg.strong_h1_max_age and m15_age <= cfg.strong_m15_max_age and m5_fresh:
        return "STRONG", "Semua syarat STRONG terpenuhi"

    # EARLY: ada unsur Rev, tapi masih fresh, M5 searah dan fresh (age=0)
    if (h1_rev or m15_rev) and h1_age <= cfg.strong_h1_max_age and m15_age <= cfg.strong_m15_max_age and m5_fresh:
        return "EARLY", "Ada unsur Reversal, namun trigger masih fresh"

    # VALID: searah tapi tidak STRONG/EARLY
    reasons = []
    if not m5_has_trigger:
        reasons.append("M5 belum ada trigger valid")
    elif not m5_aligned:
        reasons.append("M5 berlawanan dengan Bias H1")
    elif not m5_fresh:
        reasons.append(f"M5 tidak fresh (age={m5_age})")
        
    if h1_age > cfg.strong_h1_max_age:
        reasons.append(f"H1 tidak fresh (age={h1_age})")
    if m15_age > cfg.strong_m15_max_age:
        reasons.append(f"M15 tidak fresh (age={m15_age})")
        
    if not h1_trend:
        reasons.append(f"H1 status = {h1_ema_text}")
    if not m15_trend:
        reasons.append(f"M15 status = {m15_ema_text}")
        
    reason_str = ", ".join(reasons) if reasons else "Kondisi belum memenuhi kriteria STRONG"
    return "VALID", reason_str


def build_event_key(
    h1_state: TFMState, m15_state: TFMState, m5_state: TFMState,
    bias_col: str, status: str,
) -> str:
    """
    Build dedup event key.
    Transfer dari TFM_BuildEventKey() di BiasLogic.mqh.
    """
    key = bias_col
    key += f"|STATUS={status}"
    key += f"|H1={state_key(h1_state)}"
    key += f"|M15={state_key(m15_state)}"
    key += f"|M5={state_key(m5_state)}"
    return key


def build_snapshot(
    manager: TFMonitorStateManager,
    h1_candles: list[dict], m15_candles: list[dict], m5_candles: list[dict],
    h1_ema: list[float], m15_ema: list[float], m5_ema: list[float],
    status: str, bias_col: str, symbol: str,
    use_ema_filter: bool,
) -> str:
    """
    Build full snapshot string.
    Format: TF Monitor | STATUS | Buy+/Sell+ | H1 ... | M15 ... | M5 ... | Symbol
    
    Transfer dari TFM_BuildSnapshot() di BiasLogic.mqh.
    """
    h1_text = state_text("H1", manager.h1_state, h1_candles, h1_ema, use_ema_filter, manager.h1_new)
    m15_text = state_text("M15", manager.m15_state, m15_candles, m15_ema, use_ema_filter, manager.m15_new)
    m5_text = state_text("M5", manager.m5_state, m5_candles, m5_ema, use_ema_filter, manager.m5_new)

    return f"TF Monitor | {status} | {bias_col} | {h1_text} | {m15_text} | {m5_text} | {symbol}"
