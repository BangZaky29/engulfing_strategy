# =====================================================
# strategies/strategy_rcs/rcs_state.py
# Runtime state holding the current conditions of RCS
# =====================================================

import datetime
import json
import os
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

    # Trigger Candle Metrics (disimpan saat trigger valid, dipakai saat notify_result)
    trigger_dist_ema_pts: int = 0         # Jarak Open C1 ke EMA 20 (pts)
    trigger_risk_range_pts: int = 0       # Risk Range C1 dalam pts
    trigger_body_pct: float = 0.0         # Body candle C1 dalam %
    trigger_spread_pts: int = 0           # Spread market saat trigger (pts)
    
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

    # Manual Position Tracking (dari PositionTracker)
    manual_positions_count: int = 0                         # Jumlah OP manual saat ini
    manual_positions_profit: float = 0.0                    # Total floating OP manual
    manual_detected_time: Optional[datetime.datetime] = None  # Kapan pertama kali OP manual terdeteksi
    is_paused_by_manual: bool = False                       # Flag: siklus baru di-block karena OP manual
    
    def reset(self, symbol: str = None):
        """Kembalikan ke state IDLE dan bersihkan file state jika symbol diberikan."""
        if symbol:
            self.clear_state_file(symbol)
        self.phase = RCSPhase.IDLE
        self.trigger_direction = None
        self.trigger_risk_range = 0.0
        self.trigger_timestamp = None
        self.trigger_age = 0
        self.op2_notified = False

        # Reset trigger metrics
        self.trigger_dist_ema_pts = 0
        self.trigger_risk_range_pts = 0
        self.trigger_body_pct = 0.0
        self.trigger_spread_pts = 0
        
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

        # Reset manual tracking
        self.manual_positions_count = 0
        self.manual_positions_profit = 0.0
        self.manual_detected_time = None
        self.is_paused_by_manual = False
        
        # Note: cooldown_until_candle tidak di-reset di sini 
        # karena itu dipakai justru saat IDLE untuk menahan open posisi baru.

    def _get_state_file_path(self, symbol: str) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, f"rcs_state_{symbol.replace('-', '_')}.json")

    def save_to_file(self, symbol: str):
        """Menyimpan trigger metrics krusial ke file JSON agar tahan restart."""
        data = {
            "trigger_dist_ema_pts": self.trigger_dist_ema_pts,
            "trigger_risk_range_pts": self.trigger_risk_range_pts,
            "trigger_body_pct": self.trigger_body_pct,
            "trigger_spread_pts": self.trigger_spread_pts,
        }
        filepath = self._get_state_file_path(symbol)
        temp_filepath = f"{filepath}.tmp"
        try:
            with open(temp_filepath, "w") as f:
                json.dump(data, f)
            os.replace(temp_filepath, filepath)
        except Exception as e:
            print(f"⚠️ Gagal menyimpan state {symbol}: {e}")

    def load_from_file(self, symbol: str):
        """Memuat trigger metrics dari file JSON setelah bot restart."""
        filepath = self._get_state_file_path(symbol)
        if not os.path.exists(filepath):
            return
            
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            self.trigger_dist_ema_pts = data.get("trigger_dist_ema_pts", 0)
            self.trigger_risk_range_pts = data.get("trigger_risk_range_pts", 0)
            self.trigger_body_pct = data.get("trigger_body_pct", 0.0)
            self.trigger_spread_pts = data.get("trigger_spread_pts", 0)
        except Exception as e:
            print(f"⚠️ Gagal memuat state {symbol}: {e}")

    def clear_state_file(self, symbol: str):
        """Menghapus file JSON state jika ada."""
        filepath = self._get_state_file_path(symbol)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
