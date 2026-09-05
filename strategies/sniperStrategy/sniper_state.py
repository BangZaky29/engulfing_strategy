import os
import json
from dataclasses import dataclass, field
from typing import Optional

SNIPER_STATE_FILE = "data/sniper_strategy_state.json"

@dataclass
class SniperStrategyState:
    symbol: str
    active_ticket: Optional[int] = None
    trigger_direction: Optional[str] = None
    trigger_price: float = 0.0
    c1_low: float = 0.0
    c1_high: float = 0.0
    trigger_time: int = 0

    def save(self):
        try:
            os.makedirs("data", exist_ok=True)
            data = {}
            if os.path.exists(SNIPER_STATE_FILE):
                with open(SNIPER_STATE_FILE, "r") as f:
                    data = json.load(f)
            
            data[self.symbol] = {
                "active_ticket": self.active_ticket,
                "trigger_direction": self.trigger_direction,
                "trigger_price": self.trigger_price,
                "c1_low": self.c1_low,
                "c1_high": self.c1_high,
                "trigger_time": self.trigger_time
            }
            
            with open(SNIPER_STATE_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"⚠️ Gagal save state SniperStrategy: {e}")

    @classmethod
    def load(cls, symbol: str) -> "SniperStrategyState":
        try:
            if os.path.exists(SNIPER_STATE_FILE):
                with open(SNIPER_STATE_FILE, "r") as f:
                    data = json.load(f)
                    if symbol in data:
                        sym_data = data[symbol]
                        return cls(
                            symbol=symbol,
                            active_ticket=sym_data.get("active_ticket"),
                            trigger_direction=sym_data.get("trigger_direction"),
                            trigger_price=sym_data.get("trigger_price", 0.0),
                            c1_low=sym_data.get("c1_low", 0.0),
                            c1_high=sym_data.get("c1_high", 0.0),
                            trigger_time=sym_data.get("trigger_time", 0)
                        )
        except Exception:
            pass
        return cls(symbol=symbol)

    def reset(self):
        self.active_ticket = None
        self.trigger_direction = None
        self.trigger_price = 0.0
        self.c1_low = 0.0
        self.c1_high = 0.0
        self.trigger_time = 0
        self.save()
