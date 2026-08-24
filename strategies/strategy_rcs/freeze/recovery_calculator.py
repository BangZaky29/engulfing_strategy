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

def get_closed_profit_rcs(ticket: int, symbol: str = "", magic: int = 0) -> float:
    """
    Ambil total net profit (profit + swap + commission + fee) dari history deal MT5 berdasarkan ticket posisi.
    Dirancang khusus tahan terhadap delay settlement broker (Headway, HFM, IC Markets, dll).
    Jika order dibatalkan tanpa pernah filled (ORDER_STATE_CANCELED), langsung mengembalikan 0.0 tanpa delay retry.
    """
    if not ticket:
        return 0.0

    # 1. Cek status order awal di history order MT5
    # Jika order dibatalkan (ORDER_STATE_CANCELED), pending order tersebut tidak pernah filled.
    try:
        orders = mt5.history_orders_get(ticket=ticket)
        if orders and len(orders) > 0:
            if orders[0].state == mt5.ORDER_STATE_CANCELED:
                return 0.0
    except Exception:
        pass

    # 2. Multi-stage Progressive Retry mechanism untuk settlement delay broker:
    #    - Tahap 1: 5x @ 0.2s = 1.0s (cepat untuk broker responsif)
    #    - Tahap 2: 10x @ 0.5s = 5.0s (standar settlement)
    #    - Tahap 3: 10x @ 1.0s = 10.0s (patience untuk broker Headway/HFM saat volatile)
    #    Total durasi: ~16.0 detik
    delays = [0.2] * 5 + [0.5] * 10 + [1.0] * 10

    for attempt, sleep_sec in enumerate(delays, 1):
        # A. Coba query berdasarkan position_id
        deals = mt5.history_deals_get(position=ticket)
        if not deals:
            # B. Coba query berdasarkan deal/order ticket langsung
            deals = mt5.history_deals_get(ticket=ticket)

        if deals:
            total_net = 0.0
            found_out = False
            for d in deals:
                entry = getattr(d, 'entry', -1)
                # DEAL_ENTRY_OUT = 1, DEAL_ENTRY_INOUT = 2, DEAL_ENTRY_OUT_BY = 3
                if entry in (mt5.DEAL_ENTRY_OUT, 1, 2, 3):
                    profit = getattr(d, 'profit', 0.0)
                    swap = getattr(d, 'swap', 0.0)
                    commission = getattr(d, 'commission', 0.0)
                    fee = getattr(d, 'fee', 0.0)
                    total_net += (profit + swap + commission + fee)
                    found_out = True

            if found_out:
                if attempt > 3:
                    print(f"⚠️ [RCS] Delay settlement broker terdeteksi. Profit ticket #{ticket} (${total_net:.2f}) berhasil diambil pada retry {attempt}x ({sum(delays[:attempt]):.1f}s).")
                return round(total_net, 2)

        time.sleep(sleep_sec)

    # 3. Fallback: Query rentang waktu diperluas (48 jam terakhir sampai 24 jam ke depan)
    for fb_attempt in range(1, 4):
        now_ts = int(time.time())
        deals = mt5.history_deals_get(now_ts - 172800, now_ts + 86400)
        if not deals:
            # Coba menggunakan datetime object
            dt_from = datetime.datetime.now() - datetime.timedelta(days=2)
            dt_to = datetime.datetime.now() + datetime.timedelta(days=1)
            deals = mt5.history_deals_get(dt_from, dt_to)

        if deals:
            total_net = 0.0
            found = False
            for d in reversed(deals):
                entry = getattr(d, 'entry', -1)
                pos_id = getattr(d, 'position_id', 0)
                ord_id = getattr(d, 'order', 0)
                deal_id = getattr(d, 'deal', 0)

                if (pos_id == ticket or ord_id == ticket or deal_id == ticket) and entry in (mt5.DEAL_ENTRY_OUT, 1, 2, 3):
                    profit = getattr(d, 'profit', 0.0)
                    swap = getattr(d, 'swap', 0.0)
                    commission = getattr(d, 'commission', 0.0)
                    fee = getattr(d, 'fee', 0.0)
                    total_net += (profit + swap + commission + fee)
                    found = True

            if found:
                print(f"⚠️ [RCS] Profit untuk ticket #{ticket} (${total_net:.2f}) berhasil diambil via Fallback Time-based query (attempt {fb_attempt}).")
                return round(total_net, 2)

        time.sleep(1.0)

    # 4. Fallback: Cek apakah order sebenarnya dibatalkan (CANCELED)
    try:
        orders = mt5.history_orders_get(ticket=ticket)
        if orders and len(orders) > 0 and orders[0].state == mt5.ORDER_STATE_CANCELED:
            return 0.0
    except Exception:
        pass

    # 5. Safety Net: Jika ada symbol, cari deal penutup terbaru dalam 10 menit terakhir
    if symbol:
        now_ts = int(time.time())
        deals = mt5.history_deals_get(now_ts - 600, now_ts + 60)
        if deals:
            for d in reversed(deals):
                if getattr(d, 'symbol', '') == symbol and getattr(d, 'entry', -1) in (mt5.DEAL_ENTRY_OUT, 1, 2, 3):
                    if magic == 0 or getattr(d, 'magic', 0) == magic:
                        profit = getattr(d, 'profit', 0.0)
                        swap = getattr(d, 'swap', 0.0)
                        commission = getattr(d, 'commission', 0.0)
                        fee = getattr(d, 'fee', 0.0)
                        fallback_pnl = round(profit + swap + commission + fee, 2)
                        print(f"⚠️ [RCS Safety Net] Profit ticket #{ticket} dipulihkan dari deal terakhir ({symbol}, deal #{getattr(d, 'deal', 0)}): ${fallback_pnl:.2f}")
                        return fallback_pnl

    last_err = mt5.last_error()
    print(f"❌ [RCS] Gagal mengambil profit history untuk ticket #{ticket} setelah 25x retry & time fallback! MT5 Last Error: {last_err}. Mengembalikan $0.00.")
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
        total_profit += get_closed_profit_rcs(state.op1_ticket, symbol=symbol)
        
    # OP2: hanya hitung jika op2_ticket ada DAN op2_filled True
    if state.op2_ticket and state.op2_filled:
        total_profit += get_closed_profit_rcs(state.op2_ticket, symbol=symbol)
        
    # OP3: hanya hitung jika op3_ticket ada DAN op3_filled True
    if state.op3_ticket and state.op3_filled:
        total_profit += get_closed_profit_rcs(state.op3_ticket, symbol=symbol)

    if tracker and symbol:
        manual_summary = tracker.get_closed_manual_summary(symbol, since=state.freeze_start_time)
        total_profit += manual_summary.net_total

    return round(total_profit, 2)

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
    return total_profit, round(hasil_recovery, 2)
