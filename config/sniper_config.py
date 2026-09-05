# =====================================================
# config/sniper_config.py
# Konfigurasi khusus untuk Sniper Info (Dual TF Engulfing Murni)
# =====================================================

import os
from dataclasses import dataclass, field


@dataclass
class SniperConfig:
    """Konfigurasi Sniper Info — Dual Timeframe Engulfing Murni Recovery System."""

    enabled: bool = field(
        default_factory=lambda: os.getenv("SNIPER_ENABLED", "false").lower() == "true"
    )
    strategy_enabled: bool = field(
        default_factory=lambda: os.getenv("SNIPER_STRATEGY_ENABLED", "false").lower() == "true"
    )
    help_rcs_recovery: bool = field(
        default_factory=lambda: os.getenv("SNIPER_HELP_RCS_RECOVERY", "false").lower() == "true"
    )
    max_pending_candles: int = field(
        default_factory=lambda: int(os.getenv("SNIPER_MAX_PENDING_CANDLES", "2"))
    )
    symbols: list = field(
        default_factory=lambda: [
            x.strip()
            for x in os.getenv("SNIPER_SYMBOL", "XAUUSD").split(",")
            if x.strip()
        ]
    )

    # --- Timeframe ---
    tf_primary: str = field(
        default_factory=lambda: os.getenv("SNIPER_TF_PRIMARY", "M30")
    )
    tf_confirm: str = field(
        default_factory=lambda: os.getenv("SNIPER_TF_CONFIRM", "M5")
    )
    candle_count: int = field(
        default_factory=lambda: int(os.getenv("SNIPER_CANDLE_COUNT", "50"))
    )

    # --- Lot & Execution ---
    lot_size: float = field(
        default_factory=lambda: float(os.getenv("SNIPER_LOT_SIZE", "0.02"))
    )
    entry_percent: float = field(
        default_factory=lambda: float(os.getenv("SNIPER_ENTRY_PERCENT", "20"))
    )
    tp_percent: float = field(
        default_factory=lambda: float(os.getenv("SNIPER_TP_PERCENT", "50"))
    )
    magic_number: int = field(
        default_factory=lambda: int(os.getenv("SNIPER_MAGIC_NUMBER", "902001"))
    )

    # --- Notifikasi ---
    group_jid: str = field(
        default_factory=lambda: os.getenv(
            "SNIPER_GROUP_JID", "120363431394730386@g.us"
        )
    )

    @classmethod
    def from_env(cls) -> "SniperConfig":
        """Buat SniperConfig dari environment variables."""
        return cls()
