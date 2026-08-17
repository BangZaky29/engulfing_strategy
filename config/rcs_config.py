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
    symbols: list = field(
        default_factory=lambda: [x.strip() for x in os.getenv("RCS_SYMBOL", "XAUUSD").split(",") if x.strip()]
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
    min_ema_distance_pts: int = field(
        default_factory=lambda: int(os.getenv("RCS_MIN_EMA_DISTANCE_PTS", "0"))
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
        default_factory=lambda: os.getenv("RCS_GROUP_JID", os.getenv("GROUP_JID", "120363409493021715@g.us"))
    )
    private_jid: str = field(
        default_factory=lambda: os.getenv("PRIVATE_JID", os.getenv("GROUP_JID", "120363409493021715@g.us"))
    )
    profit_signal_jid: str = field(
        default_factory=lambda: os.getenv("PROFIT_SIGNAL", os.getenv("GROUP_JID", "120363409493021715@g.us"))
    )
    loss_signal_jid: str = field(
        default_factory=lambda: os.getenv("LOSS_SIGNAL", os.getenv("GROUP_JID", "120363409493021715@g.us"))
    )

    # Trading Schedule Execution Time
    rcs_trading_active_enabled: bool = field(
        default_factory=lambda: os.getenv("RCS_TRADING_ACTIVE_ENABLED", "false").lower() == "true"
    )
    rcs_trading_active_start: str = field(
        default_factory=lambda: os.getenv("RCS_TRADING_ACTIVE_START", "05:00")
    )
    rcs_trading_active_end: str = field(
        default_factory=lambda: os.getenv("RCS_TRADING_ACTIVE_END", "15:00")
    )

    # Daily Money Management Guard
    rcs_daily_target_enabled: bool = field(
        default_factory=lambda: os.getenv("RCS_DAILY_TARGET_ENABLED", "false").lower() == "true"
    )
    rcs_daily_profit_target_usd: float = field(
        default_factory=lambda: float(os.getenv("RCS_DAILY_PROFIT_TARGET_USD", "5.0"))
    )
    rcs_daily_loss_target_usd: float = field(
        default_factory=lambda: float(os.getenv("RCS_DAILY_LOSS_TARGET_USD", "5.0"))
    )

    # Logging CSV
    use_csv_log: bool = field(
        default_factory=lambda: os.getenv("RCS_USE_CSV_LOG", "false").lower() == "true"
    )
    csv_prefix: str = field(
        default_factory=lambda: os.getenv("RCS_CSV_PREFIX", "RCS")
    )

    def update_dynamic_lots(self, symbol: str = "") -> tuple[float, float, str]:
        """Perbarui lot_size_op1 dan lot_size_op2 secara dinamis berdasarkan modal MT5."""
        from mt5_client.money_management import get_dynamic_op1_lot
        dyn_op1, funds, src = get_dynamic_op1_lot(fallback_lot=self.lot_size_op1)
        self.lot_size_op1 = dyn_op1
        auto_lot = os.getenv(f"{symbol}_RCS_AUTO_LOT_OP2", os.getenv("RCS_AUTO_LOT_OP2", "true")).lower() == "true"
        if auto_lot:
            self.lot_size_op2 = round(self.lot_size_op1 * 2, 2)
        return dyn_op1, funds, src

    def __post_init__(self):
        # Lot OP2 otomatis 2x Lot OP1 (seperti sistem MRCV)
        self.update_dynamic_lots()

    @classmethod
    def from_env(cls, symbol: str | None = None) -> "RCSConfig":
        import dataclasses
        config = cls()
        if not symbol:
            return config
            
        for f in dataclasses.fields(cls):
            if f.name in ["enabled", "symbols"]:
                continue
                
            base_key = f.name.upper()
            if not base_key.startswith("RCS_"):
                base_key = f"RCS_{base_key}"
                
            if f.name == "private_jid": base_key = "PRIVATE_JID"
            elif f.name == "profit_signal_jid": base_key = "PROFIT_SIGNAL"
            elif f.name == "loss_signal_jid": base_key = "LOSS_SIGNAL"
            
            sym_key = f"{symbol}_{base_key}"
            val = os.getenv(sym_key)
            if val is not None:
                if f.type == bool:
                    setattr(config, f.name, val.lower() == "true")
                elif f.type == int:
                    setattr(config, f.name, int(float(val)))
                elif f.type == float:
                    setattr(config, f.name, float(val))
                else:
                    setattr(config, f.name, val)
                    
        # Rekalkulasi lot_size_op1 dinamis & lot_size_op2 = 2 * lot_size_op1
        config.update_dynamic_lots(symbol)

        return config
