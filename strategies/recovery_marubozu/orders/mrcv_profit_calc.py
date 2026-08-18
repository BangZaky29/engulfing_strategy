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

def get_closed_profit(ticket: int) -> float:
    """Ambil total net profit (profit + swap + commission) dari history deal MT5 berdasarkan ticket posisi."""
    if not ticket:
        return 0.0
    
    # Coba hingga 15 kali (maks ~3.75 detik) untuk mengantisipasi lagging broker saat High Impact News
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
                    print(cprint(f"⚠️ [MRCV] Delay MT5 terdeteksi. Profit untuk ticket #{ticket} berhasil diambil setelah retry {attempt}x.", Colors.YELLOW))
                return total_net
        time.sleep(0.25)

    # Fallback ke time-based history query jika position=ticket masih belum terindeks
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
            print(cprint(f"⚠️ [MRCV] Profit untuk ticket #{ticket} diambil menggunakan Fallback Time-based query.", Colors.YELLOW))
            return total_net

    print(cprint(f"❌ [CRITICAL WARNING] Gagal mengambil profit history untuk ticket #{ticket} setelah 15x retry! MT5 Lagging parah. Mengembalikan $0.00.", Colors.RED))
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
