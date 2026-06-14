# =====================================================
# config/engulfing_config.py
# Konfigurasi parameter deteksi pola Engulfing
# =====================================================

import os
from dataclasses import dataclass, field


@dataclass
class EngulfingConfig:
    """Threshold dan parameter untuk engulfing detection."""
    filter_f1_trigger_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_F1_TRIGGER_ENABLED", "true").lower() == "true"
    )
    filter_f2_scoring_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_F2_SCORING_ENABLED", "true").lower() == "true"
    )
    filter_market_state_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_MARKET_STATE_ENABLED", "false").lower() == "true"
    )
    filter_ema_scoring_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_EMA_SCORING_ENABLED", "false").lower() == "true"
    )
    
    score_weight_body: float = field(default_factory=lambda: float(os.getenv("SCORE_WEIGHT_BODY", "40")))
    score_weight_range: float = field(default_factory=lambda: float(os.getenv("SCORE_WEIGHT_RANGE", "30")))
    score_weight_ema: float = field(default_factory=lambda: float(os.getenv("SCORE_WEIGHT_EMA", "20")))
    score_weight_cp: float = field(default_factory=lambda: float(os.getenv("SCORE_WEIGHT_CP", "10")))
    score_bonus_trend: float = field(default_factory=lambda: float(os.getenv("SCORE_BONUS_TREND", "5")))
    score_penalty_sideways: float = field(default_factory=lambda: float(os.getenv("SCORE_PENALTY_SIDEWAYS", "-15")))
    
    min_grade_allowed: str = field(default_factory=lambda: os.getenv("MIN_GRADE_ALLOWED", "C+"))
    ema_source: int = field(default_factory=lambda: int(os.getenv("ENGULFING_EMA_SOURCE", "20")))
