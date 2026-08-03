# =====================================================
# strategies/strategy_rcs/freeze/recovery_calculator.py
# Menghitung hasil profit/loss saat keluar dari freeze
# =====================================================

import datetime
import MetaTrader5 as mt5
from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState

def calculate_recovery(symbol: str, state: RCSState, config: RCSConfig) -> tuple[float, float]:
    """
    Hitung profit tertutup (Closed PnL) sejak masuk freeze.
    Hasil Recovery = profit_tertutup - freeze_start_floating_usd.
    
    Returns: (total_profit, hasil_recovery)
    """
    if state.freeze_start_time is None:
        return 0.0, 0.0
        
    start_time = state.freeze_start_time
    end_time = datetime.datetime.now()
    
    deals = mt5.history_deals_get(start_time, end_time)
    if not deals:
        return 0.0, 0.0
        
    total_profit = 0.0
    for d in deals:
        if d.symbol == symbol and d.magic in (config.magic_op1, config.magic_op2, config.magic_op3):
            total_profit += d.profit
            
    hasil_recovery = total_profit - state.freeze_start_floating_usd
    return total_profit, hasil_recovery
