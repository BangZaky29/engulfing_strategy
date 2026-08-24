import time
import MetaTrader5 as mt5
from utils.colors import Colors, cprint
from strategies.recovery_marubozu.state.mrcv_state import MRCVState

def get_positions_profit(symbol: str, magics: list[int]) -> float:
    import os
    if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
        from mt5_client.multi_account_dispatcher import get_multi_account_positions_profit
        return get_multi_account_positions_profit("MRCV", symbol, magics)

    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return 0.0
    profit = 0.0
    for p in positions:
        if p.magic in magics:
            profit += p.profit
    return profit

def get_closed_profit(ticket: int, symbol: str = "", magic: int = 0) -> float:
    """Ambil total net profit (profit + swap + commission + fee) dari history deal MT5 berdasarkan ticket posisi."""
    if not ticket:
        return 0.0

    try:
        orders = mt5.history_orders_get(ticket=ticket)
        if orders and len(orders) > 0 and orders[0].state == mt5.ORDER_STATE_CANCELED:
            return 0.0
    except Exception:
        pass
    
    delays = [0.2] * 5 + [0.5] * 10 + [1.0] * 10

    for attempt, sleep_sec in enumerate(delays, 1):
        deals = mt5.history_deals_get(position=ticket)
        if not deals:
            deals = mt5.history_deals_get(ticket=ticket)

        if deals:
            total_net = 0.0
            found_out = False
            for d in deals:
                entry = getattr(d, 'entry', -1)
                if entry in (mt5.DEAL_ENTRY_OUT, 1, 2, 3):
                    profit = getattr(d, 'profit', 0.0)
                    swap = getattr(d, 'swap', 0.0)
                    commission = getattr(d, 'commission', 0.0)
                    fee = getattr(d, 'fee', 0.0)
                    total_net += (profit + swap + commission + fee)
                    found_out = True
            if found_out:
                if attempt > 3:
                    print(cprint(f"⚠️ [MRCV] Delay MT5 terdeteksi. Profit untuk ticket #{ticket} (${total_net:.2f}) berhasil diambil setelah retry {attempt}x.", Colors.YELLOW))
                return round(total_net, 2)
        time.sleep(sleep_sec)

    # Fallback ke time-based history query
    import datetime
    for fb_attempt in range(1, 4):
        now_ts = int(time.time())
        deals = mt5.history_deals_get(now_ts - 172800, now_ts + 86400)
        if not deals:
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
                print(cprint(f"⚠️ [MRCV] Profit untuk ticket #{ticket} (${total_net:.2f}) diambil menggunakan Fallback Time-based query.", Colors.YELLOW))
                return round(total_net, 2)
        time.sleep(1.0)

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
                        print(cprint(f"⚠️ [MRCV Safety Net] Profit ticket #{ticket} dipulihkan dari deal terakhir ({symbol}): ${fallback_pnl:.2f}", Colors.YELLOW))
                        return fallback_pnl

    print(cprint(f"❌ [CRITICAL WARNING] Gagal mengambil profit history untuk ticket #{ticket} setelah 25x retry & fallback! Mengembalikan $0.00.", Colors.RED))
    return 0.0

def calculate_mrcv_cycle_profit(state: MRCVState, symbol: str = "BTC") -> tuple[float, float, float]:
    """
    Hitung total profit aktual dari seluruh ticket OP MRCV (OP1, OP2, OP3) pada siklus ini.
    Returns: (total_profit, prof_op1, prof_op2)
    """
    time.sleep(0.3) # Tunggu settlement MT5
    
    import os
    if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
        from mt5_client.multi_account_dispatcher import get_multi_account_cycle_profit
        tickets_dict = dict(getattr(state, 'multi_account_tickets', {}))

        multi_pnl = get_multi_account_cycle_profit("MRCV", symbol, tickets_dict)
        tot = multi_pnl.get("total_profit", 0.0)
        return tot, tot, 0.0

    prof1 = get_closed_profit(state.op1_ticket) if state.op1_ticket else 0.0
    prof2 = get_closed_profit(state.op2_ticket) if state.op2_ticket and state.op2_filled else 0.0
    prof3 = get_closed_profit(state.op3_ticket) if state.op3_ticket and state.op3_filled else 0.0
    
    total = prof1 + prof2 + prof3
    return total, prof1, prof2
