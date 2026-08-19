# =====================================================
# strategies/strategy_rcs/freeze/recovery_calculator.py
# Menghitung hasil profit/loss saat keluar dari freeze
# Terintegrasi dengan PositionTracker untuk deteksi OP manual
# =====================================================

import time
import datetime
import MetaTrader5 as mt5
from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState

def get_closed_profit_rcs(ticket: int) -> float:
    """
    Ambil total net profit (profit + swap + commission) dari history deal MT5 berdasarkan ticket posisi.
    Jika order dibatalkan tanpa pernah filled (ORDER_STATE_CANCELED), langsung mengembalikan 0.0 tanpa delay retry.
    """
    if not ticket:
        return 0.0

    # 1. Cek status order awal di history order MT5
    # Jika order dibatalkan (ORDER_STATE_CANCELED), pending order tersebut tidak pernah filled.
    orders = mt5.history_orders_get(ticket=ticket)
    if orders:
        ord_info = orders[0]
        if ord_info.state == mt5.ORDER_STATE_CANCELED:
            return 0.0

    # 2. Retry mechanism untuk settlement delay broker (maks 15x / 3.75s)
    for attempt in range(1, 16):
        deals = mt5.history_deals_get(position=ticket)
        if deals:
            total_net = 0.0
            found_out = False
            for d in deals:
                if d.entry == mt5.DEAL_ENTRY_OUT:
                    total_net += (d.profit + d.swap + d.commission)
                    found_out = True
            if found_out:
                if attempt > 2:
                    print(f"⚠️ [RCS] Delay MT5 terdeteksi. Profit untuk ticket #{ticket} berhasil diambil setelah retry {attempt}x.")
                return total_net
        time.sleep(0.25)

    # 3. Fallback: query time-based / order-based jika position_id belum terindeks oleh broker
    now = int(time.time())
    deals = mt5.history_deals_get(now - 86400, now + 3600)
    if deals:
        total_net = 0.0
        found = False
        for d in deals:
            if (d.position_id == ticket or d.order == ticket) and d.entry == mt5.DEAL_ENTRY_OUT:
                total_net += (d.profit + d.swap + d.commission)
                found = True
        if found:
            print(f"⚠️ [RCS] Profit untuk ticket #{ticket} diambil menggunakan Fallback Time-based query.")
            return total_net

    # 4. Jika masih tidak ada deal, periksa kembali apakah order sebenarnya dibatalkan
    orders = mt5.history_orders_get(ticket=ticket)
    if orders and orders[0].state == mt5.ORDER_STATE_CANCELED:
        return 0.0

    print(f"❌ [RCS] Gagal mengambil profit history untuk ticket #{ticket} setelah 15x retry! Mengembalikan $0.00.")
    return 0.0

def calculate_cycle_profit(state: RCSState, tracker=None, symbol: str = "") -> float:
    """
    Mengambil total profit/loss aktual dari histori transaksi broker untuk siklus ini berdasarkan tiket posisi.
    Hanya memeriksa tiket OP2 & OP3 jika tiket tersebut pernah tereksekusi (op2_filled / op3_filled = True).
    Juga menghitung profit dari OP manual yang dibuka/ditutup selama siklus jika tracker tersedia.
    Mendukung Multi-Account MT5 (ACC1, ACC2, ACC3).
    """
    import os
    if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
        from mt5_client.multi_account_dispatcher import get_multi_account_cycle_profit
        tickets_dict = dict(getattr(state, 'multi_account_tickets', {}))
        multi_pnl_data = get_multi_account_cycle_profit("RCS", symbol, tickets_dict)
        total_profit = multi_pnl_data.get("total_profit", 0.0)
        if tracker and symbol:
            manual_summary = tracker.get_closed_manual_summary(symbol, since=state.freeze_start_time)
            total_profit += manual_summary.net_total
        return total_profit

    total_profit = 0.0
    
    # OP1: jika ada ticket (OP1 selalu market order jika terpasang)
    if state.op1_ticket:
        total_profit += get_closed_profit_rcs(state.op1_ticket)
        
    # OP2: hanya hitung jika op2_ticket ada DAN op2_filled True
    if state.op2_ticket and state.op2_filled:
        total_profit += get_closed_profit_rcs(state.op2_ticket)
        
    # OP3: hanya hitung jika op3_ticket ada DAN op3_filled True
    if state.op3_ticket and state.op3_filled:
        total_profit += get_closed_profit_rcs(state.op3_ticket)

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
