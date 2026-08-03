# =====================================================
# strategies/strategy_rcs/rcs_state.py
# Runtime state holding the current conditions of RCS
# =====================================================

import datetime
from dataclasses import dataclass, field
from typing import Optional

class RCSPhase:
    IDLE = "PHASE_IDLE"
    OP1 = "PHASE_OP1"
    FREEZE = "PHASE_FREEZE"

@dataclass
class RCSState:
    phase: str = RCSPhase.IDLE
    
    # Trigger Info
    trigger_direction: Optional[str] = None # "BUY" or "SELL"
    trigger_risk_range: float = 0.0
    trigger_timestamp: Optional[int] = None
    trigger_age: int = 0
    cooldown_until_candle: int = 0
    
    # Target Levels
    op1_level: float = 0.0
    op2_level: float = 0.0
    op3_level: float = 0.0
    
    tp1_price: float = 0.0
    tp2_price: float = 0.0
    
    # Open Tickets
    op1_ticket: Optional[int] = None
    op2_ticket: Optional[int] = None
    op3_ticket: Optional[int] = None
    
    op1_open_price: float = 0.0
    
    # Freeze Info
    freeze_start_floating_usd: float = 0.0
    freeze_start_time: Optional[datetime.datetime] = None
    freeze_is_hedge: bool = False
    op2_notified: bool = False
    
    def reset(self):
        """Kembalikan ke state IDLE."""
        self.phase = RCSPhase.IDLE
        self.trigger_direction = None
        self.trigger_risk_range = 0.0
        self.trigger_timestamp = None
        self.trigger_age = 0
        self.op2_notified = False
        
        self.op1_level = 0.0
        self.op2_level = 0.0
        self.op3_level = 0.0
        self.tp1_price = 0.0
        self.tp2_price = 0.0
        
        self.op1_ticket = None
        self.op2_ticket = None
        self.op3_ticket = None
        self.op1_open_price = 0.0
        
        self.freeze_start_floating_usd = 0.0
        self.freeze_start_time = None
        self.freeze_is_hedge = False
        
        # Note: cooldown_until_candle tidak di-reset di sini 
        # karena itu dipakai justru saat IDLE untuk menahan open posisi baru.
