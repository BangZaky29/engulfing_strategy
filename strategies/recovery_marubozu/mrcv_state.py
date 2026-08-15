import os
import json
from dataclasses import dataclass, field
from typing import Optional

class MRCVPhase:
    IDLE = "PHASE_IDLE"
    ACTIVE = "PHASE_ACTIVE"

@dataclass
class MRCVState:
    phase: str = MRCVPhase.IDLE
    
    # Cumulative Profit
    cumulative_profit: float = 0.0

    # Trade Info
    trigger_direction: Optional[str] = None # "BUY" or "SELL"
    trigger_ring_c1_pts: float = 0.0
    
    op1_level: float = 0.0
    op2_level: float = 0.0
    op3_level: float = 0.0
    
    tp1_price: float = 0.0
    tp2_price: float = 0.0
    
    op1_ticket: Optional[int] = None
    op2_ticket: Optional[int] = None
    op3_ticket: Optional[int] = None
    
    op1_open_price: float = 0.0

    def reset_cycle(self):
        """Reset only the active cycle (after hitting TP or SL), keeping cumulative profit."""
        self.phase = MRCVPhase.IDLE
        self.trigger_direction = None
        self.trigger_ring_c1_pts = 0.0
        
        self.op1_level = 0.0
        self.op2_level = 0.0
        self.op3_level = 0.0
        self.tp1_price = 0.0
        self.tp2_price = 0.0
        
        self.op1_ticket = None
        self.op2_ticket = None
        self.op3_ticket = None
        self.op1_open_price = 0.0

    def reset_all(self, symbol: str):
        """Reset everything including cumulative profit (when Close All happens)."""
        self.reset_cycle()
        self.cumulative_profit = 0.0
        self.save_to_file(symbol)

    def _get_state_file_path(self, symbol: str) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, f"mrcv_state_{symbol.replace('-', '_')}.json")

    def save_to_file(self, symbol: str):
        data = {
            "cumulative_profit": self.cumulative_profit,
        }
        try:
            with open(self._get_state_file_path(symbol), "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ Gagal menyimpan state MRCV {symbol}: {e}")

    def load_from_file(self, symbol: str):
        filepath = self._get_state_file_path(symbol)
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            self.cumulative_profit = data.get("cumulative_profit", 0.0)
        except Exception as e:
            print(f"⚠️ Gagal memuat state MRCV {symbol}: {e}")

