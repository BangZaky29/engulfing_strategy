"""
Base class & registry untuk semua pattern detector.

Setiap pattern cukup inherit BasePattern dan implement detect().
Pattern otomatis terdaftar di PATTERN_REGISTRY saat import.
"""

import os
from abc import ABC, abstractmethod


class BasePattern(ABC):
    """Abstract base class untuk semua pattern detector."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nama pattern (e.g., 'Engulfing', 'SameCandle')."""
        ...

    @abstractmethod
    def detect(self, candle_data: dict, rates: list, point: float) -> list:
        """Deteksi pattern dari data candle.

        Args:
            candle_data: dict berisi c1 & c2 data (close_, open_, high_, low_, c2_*, body_pct)
            rates: list of raw rate dicts (latest first, reversed dari MT5)
            point: symbol point value

        Returns:
            List of (direction, details_dict) tuples.
            Contoh: [("BUY", {"body_pct": 79.2})]
            Return [] jika tidak ada pattern terdeteksi.
        """
        ...


# =========================================================
# Pattern Registry - auto-collects all patterns
# =========================================================

# Global registry: list of BasePattern instances
PATTERN_REGISTRY: list[BasePattern] = []


def register_pattern(pattern_cls):
    """Decorator untuk auto-register pattern class ke registry."""
    instance = pattern_cls()
    PATTERN_REGISTRY.append(instance)
    return pattern_cls


def get_all_patterns() -> list[BasePattern]:
    """Return semua pattern yang sudah di-register."""
    return PATTERN_REGISTRY


# =========================================================
# Auto-import semua pattern files agar decorator jalan
# =========================================================
def _auto_import_patterns():
    """Import semua module di folder patterns/ agar @register_pattern aktif."""
    from . import engulfing, marubozu, same_candle  # noqa: F401


_auto_import_patterns()
