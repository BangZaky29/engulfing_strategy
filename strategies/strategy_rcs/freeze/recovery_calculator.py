# =====================================================
# strategies/strategy_rcs/freeze/recovery_calculator.py
# Menghitung hasil profit/loss saat keluar dari freeze
# =====================================================

import datetime
import MetaTrader5 as mt5
from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState

def calculate_cycle_profit(state: RCSState) -> float:
    """Mengambil total profit/loss aktual dari histori transaksi broker untuk siklus ini berdasarkan tiket posisi."""
    tickets = [state.op1_ticket, state.op2_ticket, state.op3_ticket]
    total_profit = 0.0
    
    for ticket in tickets:
        if ticket is None:
            continue
        deals = mt5.history_deals_get(position=ticket)
        if deals:
            for deal in deals:
                total_profit += deal.profit
                total_profit += deal.swap
                total_profit += deal.commission
                
    return total_profit

def calculate_recovery(symbol: str, state: RCSState, config: RCSConfig) -> tuple[float, float]:
    """
    Hitung profit tertutup (Closed PnL) sejak masuk freeze.
    Hasil Recovery = profit_tertutup - freeze_start_floating_usd.
    
    Returns: (total_profit, hasil_recovery)
    """
    total_profit = calculate_cycle_profit(state)
    
    if state.freeze_start_time is None:
        return total_profit, 0.0
            
    hasil_recovery = total_profit - state.freeze_start_floating_usd
    return total_profit, hasil_recovery
