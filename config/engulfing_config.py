# =====================================================
# config/engulfing_config.py
# Konfigurasi parameter deteksi pola Engulfing
# =====================================================

import os
from dataclasses import dataclass, field


@dataclass
class EngulfingConfig:
    """Threshold dan parameter untuk engulfing detection."""
    active_filter_strategy: str = field(
        default_factory=lambda: os.getenv("ACTIVE_FILTER_STRATEGY", "A").upper()
    )
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
    filter_f3_pattern_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_F3_PATTERN_ENABLED", "true").lower() == "true"
    )
    filter_f3_ema_ring_b_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_F3_EMA_RING_B_ENABLED", "true").lower() == "true"
    )
    filter_f2_pattern_b_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_F2_PATTERN_B_ENABLED", "true").lower() == "true"
    )
    filter_c_tfm_enabled: bool = field(
        default_factory=lambda: os.getenv("FILTER_C_TFM_ENABLED", "false").lower() == "true"
    )
    
    score_weight_body: float = field(default_factory=lambda: float(os.getenv("SCORE_WEIGHT_BODY", "40")))
    score_weight_range: float = field(default_factory=lambda: float(os.getenv("SCORE_WEIGHT_RANGE", "30")))
    score_weight_ema: float = field(default_factory=lambda: float(os.getenv("SCORE_WEIGHT_EMA", "20")))
    score_weight_cp: float = field(default_factory=lambda: float(os.getenv("SCORE_WEIGHT_CP", "10")))
    score_bonus_trend: float = field(default_factory=lambda: float(os.getenv("SCORE_BONUS_TREND", "5")))
    score_penalty_sideways: float = field(default_factory=lambda: float(os.getenv("SCORE_PENALTY_SIDEWAYS", "-15")))
    score_penalty_counter_trend: float = field(default_factory=lambda: float(os.getenv("SCORE_PENALTY_COUNTER_TREND", "-10")))
    market_lookback: int = field(default_factory=lambda: int(os.getenv("MARKET_LOOKBACK", "20")))
    
    min_grade_allowed: str = field(default_factory=lambda: os.getenv("MIN_GRADE_ALLOWED", "C+"))
    ema_source: int = field(default_factory=lambda: int(os.getenv("ENGULFING_EMA_SOURCE", "20")))

    # F3 Pattern & Ring Size Config
    min_ring_c1_points: int = field(default_factory=lambda: int(os.getenv("MIN_RING_C1_POINTS", "100")))
    normal_ring_c1_points: int = field(default_factory=lambda: int(os.getenv("NORMAL_RING_C1_POINTS", "250")))
    large_ring_c1_points: int = field(default_factory=lambda: int(os.getenv("LARGE_RING_C1_POINTS", "450")))
    max_ring_c1_points: int = field(default_factory=lambda: int(os.getenv("MAX_RING_C1_POINTS", "1500")))

    # F3 Pattern & Ring Size Config (Filter B)
    min_ring_c1_points_b: int = field(default_factory=lambda: int(os.getenv("MIN_RING_C1_POINTS_B", "250")))
    max_ring_c1_points_b: int = field(default_factory=lambda: int(os.getenv("MAX_RING_C1_POINTS_B", "700")))

    def get_ring_size_b(self, symbol: str) -> tuple[int, int]:
        """Fetch symbol-specific min/max ring size for Filter B."""
        min_val = int(os.getenv(f"RING_B_{symbol.upper()}_MIN", self.min_ring_c1_points_b))
        max_val = int(os.getenv(f"RING_B_{symbol.upper()}_MAX", self.max_ring_c1_points_b))
        return min_val, max_val

