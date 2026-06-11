# =====================================================
# config/engulfing_config.py
# Konfigurasi parameter deteksi pola Engulfing
# =====================================================

import os
from dataclasses import dataclass, field


@dataclass
class EngulfingConfig:
    """Threshold dan parameter untuk engulfing detection."""
    min_body_ratio: float = field(
        default_factory=lambda: float(os.getenv("ENGULFING_MIN_BODY_RATIO", "1.2"))
    )
    min_body_pips: float = field(
        default_factory=lambda: float(os.getenv("ENGULFING_MIN_BODY_PIPS", "0.5"))
    )
    confidence_ema_bonus: float = field(
        default_factory=lambda: float(os.getenv("ENGULFING_EMA_BONUS", "20"))
    )
    confidence_ratio_bonus: float = field(
        default_factory=lambda: float(os.getenv("ENGULFING_RATIO_BONUS", "15"))
    )
