# =====================================================
# config/rcs_config.py
# Konfigurasi khusus untuk Reversal Candle System (RCS)
# =====================================================

import os
from dataclasses import dataclass, field

@dataclass
class RCSConfig:
    enabled: bool = field(
        default_factory=lambda: os.getenv("RCS_ENABLED", "false").lower() == "true"
    )
    symbol: str = field(
        default_factory=lambda: os.getenv("RCS_SYMBOL", "XAUUSD")
    )
    signal_timeframe: str = field(
        default_factory=lambda: os.getenv("RCS_SIGNAL_TIMEFRAME", "M5")
    )
    candle_count: int = field(
        default_factory=lambda: int(os.getenv("RCS_CANDLE_COUNT", "50"))
    )

    # Trigger Pattern
    use_engulfing: bool = field(
        default_factory=lambda: os.getenv("RCS_USE_ENGULFING", "true").lower() == "true"
    )
    use_ict: bool = field(
        default_factory=lambda: os.getenv("RCS_USE_ICT", "true").lower() == "true"
    )
    ict_sweep_lookback: int = field(
        default_factory=lambda: int(os.getenv("RCS_ICT_SWEEP_LOOKBACK", "5"))
    )

    # Filter Wajib
    min_trigger_range: int = field(
        default_factory=lambda: int(os.getenv("RCS_MIN_TRIGGER_RANGE", "50"))
    )
    max_trigger_range: int = field(
        default_factory=lambda: int(os.getenv("RCS_MAX_TRIGGER_RANGE", "500"))
    )
    min_body_percent: float = field(
        default_factory=lambda: float(os.getenv("RCS_MIN_BODY_PERCENT", "30"))
    )
    max_body_percent: float = field(
        default_factory=lambda: float(os.getenv("RCS_MAX_BODY_PERCENT", "90"))
    )
    use_spread_filter: bool = field(
        default_factory=lambda: os.getenv("RCS_USE_SPREAD_FILTER", "true").lower() == "true"
    )
    max_spread_points: int = field(
        default_factory=lambda: int(os.getenv("RCS_MAX_SPREAD_POINTS", "50"))
    )
    
    # Filter EMA Pullback
    use_ema_pullback: bool = field(
        default_factory=lambda: os.getenv("RCS_USE_EMA_PULLBACK", "true").lower() == "true"
    )
    ema_period: int = field(
        default_factory=lambda: int(os.getenv("RCS_EMA_PERIOD", "20"))
    )
    max_ema_distance_pts: int = field(
        default_factory=lambda: int(os.getenv("RCS_MAX_EMA_DISTANCE_PTS", "200"))
    )
    use_ema_slope: bool = field(
        default_factory=lambda: os.getenv("RCS_USE_EMA_SLOPE", "false").lower() == "true"
    )

    # OP1 Entry
    op1_entry_mode: str = field(
        default_factory=lambda: os.getenv("RCS_OP1_ENTRY_MODE", "PERCENT").upper()
    )
    entry_percent: float = field(
        default_factory=lambda: float(os.getenv("RCS_ENTRY_PERCENT", "20.0"))
    )
    max_instant_slip_pts: int = field(
        default_factory=lambda: int(os.getenv("RCS_MAX_INSTANT_SLIP_PTS", "30"))
    )
    max_target_slip_pts: int = field(
        default_factory=lambda: int(os.getenv("RCS_MAX_TARGET_SLIP_PTS", "20"))
    )
    entry_tolerance_pts: int = field(
        default_factory=lambda: int(os.getenv("RCS_ENTRY_TOLERANCE_PTS", "5"))
    )
    lot_size_op1: float = field(
        default_factory=lambda: float(os.getenv("RCS_LOT_SIZE_OP1", "0.01"))
    )
    magic_op1: int = field(
        default_factory=lambda: int(os.getenv("RCS_MAGIC_OP1", "901001"))
    )

    # TP1
    tp_mode: str = field(
        default_factory=lambda: os.getenv("RCS_TP_MODE", "PERCENT").upper()
    )
    tp_percent: float = field(
        default_factory=lambda: float(os.getenv("RCS_TP_PERCENT", "100.0"))
    )
    tp_usd: float = field(
        default_factory=lambda: float(os.getenv("RCS_TP_USD", "500.0"))
    )

    # OP2
    op2_mode: str = field(
        default_factory=lambda: os.getenv("RCS_OP2_MODE", "HEDGE").upper()
    )
    op2_percent: float = field(
        default_factory=lambda: float(os.getenv("RCS_OP2_PERCENT", "100.0"))
    )
    lot_size_op2: float = field(
        default_factory=lambda: float(os.getenv("RCS_LOT_SIZE_OP2", "0.01"))
    )
    magic_op2: int = field(
        default_factory=lambda: int(os.getenv("RCS_MAGIC_OP2", "901002"))
    )
    sl_cooldown_candles: int = field(
        default_factory=lambda: int(os.getenv("RCS_SL_COOLDOWN_CANDLES", "3"))
    )

    # TP2 (untuk HEDGE_REENTRY)
    tp2_mode: str = field(
        default_factory=lambda: os.getenv("RCS_TP2_MODE", "PERCENT").upper()
    )
    tp2_percent: float = field(
        default_factory=lambda: float(os.getenv("RCS_TP2_PERCENT", "100.0"))
    )
    tp2_usd: float = field(
        default_factory=lambda: float(os.getenv("RCS_TP2_USD", "500.0"))
    )

    # OP3 (untuk HEDGE_REENTRY)
    op3_mode: str = field(
        default_factory=lambda: os.getenv("RCS_OP3_MODE", "HEDGE").upper()
    )
    op3_percent: float = field(
        default_factory=lambda: float(os.getenv("RCS_OP3_PERCENT", "150.0"))
    )
    magic_op3: int = field(
        default_factory=lambda: int(os.getenv("RCS_MAGIC_OP3", "901003"))
    )
    op3_cooldown_candles: int = field(
        default_factory=lambda: int(os.getenv("RCS_OP3_COOLDOWN_CANDLES", "5"))
    )

    # General / Slippage
    trigger_mode: str = field(
        default_factory=lambda: os.getenv("RCS_TRIGGER_MODE", "NORMAL").upper()
    )
    max_trigger_age: int = field(
        default_factory=lambda: int(os.getenv("RCS_MAX_TRIGGER_AGE", "3"))
    )
    slippage: int = field(
        default_factory=lambda: int(os.getenv("RCS_SLIPPAGE", "20"))
    )

    # Notifikasi
    notif_trigger: bool = field(
        default_factory=lambda: os.getenv("RCS_NOTIF_TRIGGER", "true").lower() == "true"
    )
    notif_skip: bool = field(
        default_factory=lambda: os.getenv("RCS_NOTIF_SKIP", "true").lower() == "true"
    )
    notif_open: bool = field(
        default_factory=lambda: os.getenv("RCS_NOTIF_OPEN", "true").lower() == "true"
    )
    notif_result: bool = field(
        default_factory=lambda: os.getenv("RCS_NOTIF_RESULT", "true").lower() == "true"
    )
    notif_freeze: bool = field(
        default_factory=lambda: os.getenv("RCS_NOTIF_FREEZE", "true").lower() == "true"
    )
    group_jid: str = field(
        default_factory=lambda: os.getenv("RCS_GROUP_JID", "")
    )

    # Logging CSV
    use_csv_log: bool = field(
        default_factory=lambda: os.getenv("RCS_USE_CSV_LOG", "false").lower() == "true"
    )
    csv_prefix: str = field(
        default_factory=lambda: os.getenv("RCS_CSV_PREFIX", "RCS")
    )
