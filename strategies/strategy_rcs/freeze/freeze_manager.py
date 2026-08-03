# =====================================================
# strategies/strategy_rcs/freeze/freeze_manager.py
# Logika masuk dan keluar dari State Freeze
# =====================================================

import datetime
import MetaTrader5 as mt5
from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState

def get_total_floating_rcs(state: RCSState) -> float:
    """Hitung total floating profit/loss dari semua posisi aktif RCS"""
    pos1 = mt5.positions_get(ticket=state.op1_ticket) if state.op1_ticket else None
    pos2 = mt5.positions_get(ticket=state.op2_ticket) if state.op2_ticket else None
    pos3 = mt5.positions_get(ticket=state.op3_ticket) if state.op3_ticket else None
    
    total = 0.0
    if pos1 and len(pos1) > 0:
        total += pos1[0].profit
    if pos2 and len(pos2) > 0:
        total += pos2[0].profit
    if pos3 and len(pos3) > 0:
        total += pos3[0].profit
        
    return total

def enter_freeze(state: RCSState, config: RCSConfig):
    """Jalankan snapshot sebelum masuk freeze"""
    state.freeze_start_floating_usd = get_total_floating_rcs(state)
    state.freeze_start_time = datetime.datetime.now()

def check_unfreeze(symbol: str, state: RCSState, config: RCSConfig) -> bool:
    """
    Cek apakah semua tiket (OP1, OP2, OP3) sudah tidak ada di posisi aktif.
    Jika kosong, berarti telah ditutup manual (atau oleh SL).
    """
    pos1 = mt5.positions_get(ticket=state.op1_ticket) if state.op1_ticket else None
    pos2 = mt5.positions_get(ticket=state.op2_ticket) if state.op2_ticket else None
    pos3 = mt5.positions_get(ticket=state.op3_ticket) if state.op3_ticket else None
    
    # Jika tidak ada posisi sama sekali
    if not pos1 and not pos2 and not pos3:
        return True
    return False

def calculate_cycle_profit(state: RCSState) -> float:
    """Mengambil total profit/loss aktual dari histori transaksi broker untuk siklus ini."""
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

def calculate_recovery(symbol: str, state: RCSState, config: RCSConfig) -> tuple:
    """Hitung (profit_aktual, recovery_usd) setelah unfreeze"""
    profit = calculate_cycle_profit(state)
    # Recovery adalah seberapa banyak balance kembali dibanding saat awal freeze
    recovery = profit - state.freeze_start_floating_usd
    return profit, recovery
