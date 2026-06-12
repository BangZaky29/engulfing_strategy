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
    sl_buffer_percent: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_SL_BUFFER_PERCENT", "105"))
    )
    """
    Persentase posisi SL di luar High/Low candle engulfing (C2).

    Konsep Ring:
      Candle Hijau (Bullish) : 0% = Close  | 100% = Low
      Candle Merah (Bearish) : 0% = Close  | 100% = High

    Dengan sl_buffer_percent = 105:
      BUY  -> SL = Low  - (Close - Low)  * 0.05   (5% di bawah Low)
      SELL -> SL = High + (High - Close) * 0.05   (5% di atas High)
    """
