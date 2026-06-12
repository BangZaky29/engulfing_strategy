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

    # ─── Syarat Panjang Ring C2 ───────────────────────────────────────
    # Panjang minimal ring C2 dalam satuan point (harga mentah, bukan pip).
    # Candle Hijau : ring = Close - Low
    # Candle Merah : ring = High  - Close
    # Default = 10 point (misal XAUUSD: 10 × 0.01 = $0.10)
    min_ring_points: float = field(
        default_factory=lambda: float(os.getenv("ENGULFING_MIN_RING_POINTS", "10"))
    )

    # ─── Anti-Doji: Minimal Ketebalan Body C2 ────────────────────────
    # Full Ring C2 = High - Low  (100%)
    # Body C2      = |Close - Open|
    # Syarat       : Body / Full_Ring >= min_body_ring_pct (%)
    # Default = 20%  →  body minimal 20% dari full candle range
    min_body_ring_pct: float = field(
        default_factory=lambda: float(os.getenv("ENGULFING_MIN_BODY_RING_PCT", "20"))
    )

    # ─── EMA Position Filter (syarat OP) ─────────────────────────────
    # BUY  : Close C2 harus di ATAS  EMA referensi
    # SELL : Close C2 harus di BAWAH EMA referensi
    # ema_filter_source: "slow" = EMA_20 (default) | "fast" = EMA_10
    ema_filter_enabled: bool = field(
        default_factory=lambda: os.getenv("ENGULFING_EMA_FILTER_ENABLED", "true").lower() == "true"
    )
    ema_filter_source: str = field(
        default_factory=lambda: os.getenv("ENGULFING_EMA_FILTER_SOURCE", "slow").lower()
    )
