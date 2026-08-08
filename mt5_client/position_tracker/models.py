# =====================================================
# mt5_client/position_tracker/models.py
# Data models untuk Position Tracker
# =====================================================

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PositionOrigin(Enum):
    """Asal usul posisi: dibuka oleh sistem atau manual oleh trader."""
    SYSTEM = "SYSTEM"
    MANUAL = "MANUAL"


@dataclass
class TrackedPosition:
    """Representasi satu posisi yang dilacak oleh PositionTracker."""
    ticket: int
    symbol: str
    direction: str              # "BUY" / "SELL"
    volume: float
    open_price: float
    open_time: datetime
    magic_number: int
    comment: str
    origin: PositionOrigin
    strategy: str               # "RCS" / "ENGULFING" / "ITR" / "UNKNOWN"
    current_price: float = 0.0
    sl_price: float = 0.0
    tp_price: float = 0.0
    margin: float = 0.0
    current_profit: float = 0.0
    current_swap: float = 0.0
    current_commission: float = 0.0
    is_closed: bool = False
    close_time: Optional[datetime] = None
    close_profit: float = 0.0
    close_swap: float = 0.0
    close_commission: float = 0.0

    @property
    def net_profit(self) -> float:
        """Total profit termasuk swap dan commission."""
        if self.is_closed:
            return self.close_profit + self.close_swap + self.close_commission
        return self.current_profit + self.current_swap + self.current_commission


@dataclass
class ClosedManualSummary:
    """Ringkasan OP manual yang sudah ditutup dalam rentang waktu tertentu."""
    total_count: int = 0
    total_profit: float = 0.0
    total_swap: float = 0.0
    total_commission: float = 0.0
    positions: list = field(default_factory=list)  # list[TrackedPosition]

    @property
    def net_total(self) -> float:
        """Total bersih termasuk swap dan commission."""
        return self.total_profit + self.total_swap + self.total_commission


@dataclass
class PositionSnapshot:
    """Snapshot posisi aktif pada satu waktu untuk satu symbol."""
    symbol: str
    timestamp: datetime
    system_positions: list = field(default_factory=list)   # list[TrackedPosition]
    manual_positions: list = field(default_factory=list)    # list[TrackedPosition]
    total_system_floating: float = 0.0
    total_manual_floating: float = 0.0

    @property
    def total_floating(self) -> float:
        return self.total_system_floating + self.total_manual_floating

    @property
    def total_count(self) -> int:
        return len(self.system_positions) + len(self.manual_positions)

    @property
    def manual_count(self) -> int:
        return len(self.manual_positions)

    @property
    def system_count(self) -> int:
        return len(self.system_positions)
