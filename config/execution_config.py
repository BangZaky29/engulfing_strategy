# =====================================================
# config/execution_config.py
# Konfigurasi eksekusi MT5 (Lot, TP, Slippage, dll)
# =====================================================

import os
from dataclasses import dataclass, field


@dataclass
class ExecutionConfig:
    """Konfigurasi parameter trading/eksekusi."""
    lot_size: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_LOT_SIZE", "0.01"))
    )
    tp_points: int = field(
        default_factory=lambda: int(os.getenv("EXECUTION_TP_POINTS", "100"))
    )
    slippage: int = field(
        default_factory=lambda: int(os.getenv("EXECUTION_SLIPPAGE", "20"))
    )
    magic_number: int = field(
        default_factory=lambda: int(os.getenv("EXECUTION_MAGIC_NUMBER", "777777"))
    )
