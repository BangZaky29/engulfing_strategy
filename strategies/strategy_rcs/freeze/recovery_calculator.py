# =====================================================
# strategies/strategy_rcs/freeze/recovery_calculator.py
# Menghitung hasil profit/loss saat keluar dari freeze
# Terintegrasi dengan PositionTracker untuk deteksi OP manual
# =====================================================

import datetime
import MetaTrader5 as mt5
from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState

def calculate_cycle_profit(state: RCSState, tracker=None, symbol: str = "") -> float:
    """
    Mengambil total profit/loss aktual dari histori transaksi broker untuk siklus ini berdasarkan tiket posisi.
    Juga menghitung profit dari OP manual yang dibuka/ditutup selama siklus jika tracker tersedia.
    """
    tickets = [state.op1_ticket, state.op2_ticket, state.op3_ticket]
    total_profit = 0.0
    
    for ticket in tickets:
        if ticket is None:
            continue
        
        # Retry mechanism untuk settlement delay broker (maks 15x / 3.75s)
        ticket_profit = 0.0
        for attempt in range(1, 16):
            deals = mt5.history_deals_get(position=ticket)
            if deals:
                found_out = False
                for deal in deals:
                    if deal.entry == mt5.DEAL_ENTRY_OUT:
                        ticket_profit += (deal.profit + deal.swap + deal.commission)
                        found_out = True
                
                if found_out:
                    if attempt > 2:
                        print(f"⚠️ [RCS] Delay MT5 terdeteksi. Profit untuk ticket #{ticket} berhasil diambil setelah retry {attempt}x.")
                    total_profit += ticket_profit
                    break
            import time
            time.sleep(0.25)
        
        if ticket_profit == 0.0 and attempt == 15:
            print(f"❌ [RCS] Gagal mengambil profit history untuk ticket #{ticket} setelah 15x retry! Mengembalikan $0.00.")

    if tracker and symbol:
        manual_summary = tracker.get_closed_manual_summary(symbol, since=state.freeze_start_time)
        total_profit += manual_summary.net_total

    return total_profit

def calculate_recovery(symbol: str, state: RCSState, config: RCSConfig, tracker=None) -> tuple[float, float]:
    """
    Hitung profit tertutup (Closed PnL) sejak masuk freeze.
    Hasil Recovery = profit_tertutup - freeze_start_floating_usd.
    
    Returns: (total_profit, hasil_recovery)
    """
    total_profit = calculate_cycle_profit(state, tracker=tracker, symbol=symbol)
    
    if state.freeze_start_time is None:
        return total_profit, 0.0
            
    hasil_recovery = total_profit - state.freeze_start_floating_usd
    return total_profit, hasil_recovery
