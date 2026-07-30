# =====================================================
# config/itr_config.py
# Konfigurasi khusus untuk Infinity Trailing Reversal
# =====================================================

import os
from dataclasses import dataclass, field

@dataclass
class ITRConfig:
    enabled: bool = field(
        default_factory=lambda: os.getenv("ITR_ENABLED", "false").lower() == "true"
    )
    symbol: str = field(
        default_factory=lambda: os.getenv("ITR_SYMBOL", "XAUUSD")
    )
    lot_size: float = field(
        default_factory=lambda: float(os.getenv("ITR_LOT_SIZE", "0.10"))
    )
    initial_direction: str = field(
        default_factory=lambda: os.getenv("ITR_INITIAL_DIRECTION", "BUY").upper()
    )
    pending_distance_usd: float = field(
        default_factory=lambda: float(os.getenv("ITR_PENDING_DISTANCE_USD", "10.0"))
    )
    trailing_step_usd: float = field(
        default_factory=lambda: float(os.getenv("ITR_TRAILING_STEP_USD", "5.0"))
    )
    magic_number: int = field(
        default_factory=lambda: int(os.getenv("ITR_MAGIC_NUMBER", "888888"))
    )

    # WA Config
    group_sar: str = field(
        default_factory=lambda: os.getenv("ITR_GROUP_SAR", "")
    )
    executor: str = field(
        default_factory=lambda: os.getenv("ITR_EXECUTOR", "")
    )

    # Opsi 1
    opsi1_enabled: bool = field(
        default_factory=lambda: os.getenv("ITR_OPSI1_ENABLED", "false").lower() == "true"
    )
    opsi1_target_usd: float = field(
        default_factory=lambda: float(os.getenv("ITR_OPSI1_TARGET_USD", "50.0"))
    )

    # Opsi 2
    opsi2_enabled: bool = field(
        default_factory=lambda: os.getenv("ITR_OPSI2_ENABLED", "false").lower() == "true"
    )
    opsi2_profit_target_usd: float = field(
        default_factory=lambda: float(os.getenv("ITR_OPSI2_PROFIT_TARGET_USD", "20.0"))
    )
    opsi2_loss_target_usd: float = field(
        default_factory=lambda: float(os.getenv("ITR_OPSI2_LOSS_TARGET_USD", "-20.0"))
    )
    opsi2_cooldown_minutes: int = field(
        default_factory=lambda: int(os.getenv("ITR_OPSI2_COOLDOWN_MINUTES", "5"))
    )
