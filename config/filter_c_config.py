# =====================================================
# config/filter_c_config.py
# Konfigurasi Filter C — TF Monitor
# Mirror dari Config.mqh (MQ5 TF_Monitor)
# =====================================================

import os
from dataclasses import dataclass, field


@dataclass
class FilterCConfig:
    """Konfigurasi parameter TF Monitor (Filter C)."""

    # === Trigger Toggles (Global Fallbacks) ===
    use_engulfing: bool = field(
        default_factory=lambda: os.getenv("TFM_USE_ENGULFING", "true").lower() == "true"
    )
    use_marubozu: bool = field(
        default_factory=lambda: os.getenv("TFM_USE_MARUBOZU", "true").lower() == "true"
    )
    use_ict: bool = field(
        default_factory=lambda: os.getenv("TFM_USE_ICT", "true").lower() == "true"
    )
    use_pinbar: bool = field(
        default_factory=lambda: os.getenv("TFM_USE_PINBAR", "true").lower() == "true"
    )
    use_dominan_break: bool = field(
        default_factory=lambda: os.getenv("TFM_USE_DOMINAN_BREAK", "true").lower() == "true"
    )
    use_multi_trigger: bool = field(
        default_factory=lambda: os.getenv("TFM_USE_MULTI_TRIGGER", "true").lower() == "true"
    )

    def get_use_engulfing(self, tf: str) -> bool:
        val = os.getenv(f"TFM_{tf}_USE_ENGULFING")
        if val is not None:
            return val.lower() == "true"
        return self.use_engulfing

    def get_use_marubozu(self, tf: str) -> bool:
        val = os.getenv(f"TFM_{tf}_USE_MARUBOZU")
        if val is not None:
            return val.lower() == "true"
        return self.use_marubozu

    def get_use_ict(self, tf: str) -> bool:
        val = os.getenv(f"TFM_{tf}_USE_ICT")
        if val is not None:
            return val.lower() == "true"
        return self.use_ict

    def get_use_pinbar(self, tf: str) -> bool:
        val = os.getenv(f"TFM_{tf}_USE_PINBAR")
        if val is not None:
            return val.lower() == "true"
        return self.use_pinbar

    def get_use_dominan_break(self, tf: str) -> bool:
        val = os.getenv(f"TFM_{tf}_USE_DOMINAN_BREAK")
        if val is not None:
            return val.lower() == "true"
        return self.use_dominan_break

    def get_use_multi_trigger(self, tf: str) -> bool:
        val = os.getenv(f"TFM_{tf}_USE_MULTI_TRIGGER")
        if val is not None:
            return val.lower() == "true"
        return self.use_multi_trigger

    # === EMA ===
    use_ema_filter: bool = field(
        default_factory=lambda: os.getenv("TFM_USE_EMA_FILTER", "true").lower() == "true"
    )
    ema_period: int = field(
        default_factory=lambda: int(os.getenv("TFM_EMA_PERIOD", "20"))
    )

    # === Marubozu Params ===
    marubozu_wick_buffer_points: int = field(
        default_factory=lambda: int(os.getenv("TFM_MARUBOZU_WICK_BUFFER_POINTS", "150"))
    )
    marubozu_compare_candles: int = field(
        default_factory=lambda: int(os.getenv("TFM_MARUBOZU_COMPARE_CANDLES", "3"))
    )
    marubozu_range_multiplier: float = field(
        default_factory=lambda: float(os.getenv("TFM_MARUBOZU_RANGE_MULTIPLIER", "2.0"))
    )

    # === Pinbar Params ===
    pinbar_wick_body_multiplier: float = field(
        default_factory=lambda: float(os.getenv("TFM_PINBAR_WICK_BODY_MULTIPLIER", "4.0"))
    )
    pinbar_min_range_points: int = field(
        default_factory=lambda: int(os.getenv("TFM_PINBAR_MIN_RANGE_POINTS", "600"))
    )

    # === Dominan Break Params ===
    db_min_candles: int = field(
        default_factory=lambda: int(os.getenv("TFM_DB_MIN_CANDLES", "3"))
    )
    db_max_candles: int = field(
        default_factory=lambda: int(os.getenv("TFM_DB_MAX_CANDLES", "20"))
    )
    db_buffer_points: int = field(
        default_factory=lambda: int(os.getenv("TFM_DB_BUFFER_POINTS", "0"))
    )

    # === Monitor ===
    trigger_lookback_bars: int = field(
        default_factory=lambda: int(os.getenv("TFM_TRIGGER_LOOKBACK_BARS", "200"))
    )

    # === Validity Thresholds ===
    h1_late_age: int = field(
        default_factory=lambda: int(os.getenv("TFM_H1_LATE_AGE", "5"))
    )
    strong_h1_max_age: int = field(
        default_factory=lambda: int(os.getenv("TFM_STRONG_H1_MAX_AGE", "3"))
    )
    strong_m15_max_age: int = field(
        default_factory=lambda: int(os.getenv("TFM_STRONG_M15_MAX_AGE", "3"))
    )

    # === Filter C Behavior ===
    filter_c_blocking: bool = field(
        default_factory=lambda: os.getenv("TFM_BLOCKING", "true").lower() == "true"
    )

    # === Dynamic SL dari H1 Trigger ===
    # 0% = Close H1 trigger, 100% = High (SELL) / Low (BUY) H1 trigger
    # SL ditempatkan pada sl_h1_pct % dari range tersebut
    sl_h1_pct: float = field(
        default_factory=lambda: float(os.getenv("SL_H1_PCT", "0.30"))
    )
