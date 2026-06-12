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

    # --- Toggle Filter ---
    # true  = filter aktif (default)
    # false = filter di-bypass (sinyal tetap lolos meski tidak memenuhi syarat)
    filter_f1_ring_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_F1_RING_ENABLED", "true").lower() == "true"
    )

    # ─── Syarat Panjang Ring C2 ───────────────────────────────────────
    min_ring_points: float = field(
        default_factory=lambda: float(os.getenv("ENGULFING_MIN_RING_POINTS", "10"))
    )
    max_ring_points: float = field(
        default_factory=lambda: float(os.getenv("ENGULFING_MAX_RING_POINTS", "700"))
    )

    filter_f2_doji_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_F2_DOJI_ENABLED", "true").lower() == "true"
    )

    # ─── Anti-Doji: Minimal Ketebalan Body C2 ────────────────────────
    min_body_ring_pct: float = field(
        default_factory=lambda: float(os.getenv("ENGULFING_MIN_BODY_RING_PCT", "20"))
    )

    filter_f3_pattern_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_F3_PATTERN_ENABLED", "true").lower() == "true"
    )

    # ─── EMA Position Filter ─────────────────────────────────────────
    filter_f4_ema_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_F4_EMA_ENABLED", "true").lower() == "true"
    )
    ema_filter_enabled: bool = field(
        default_factory=lambda: os.getenv("ENGULFING_EMA_FILTER_ENABLED", "true").lower() == "true"
    )
    ema_filter_source: str = field(
        default_factory=lambda: os.getenv("ENGULFING_EMA_FILTER_SOURCE", "slow").lower()
    )
