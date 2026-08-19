# =====================================================
# strategies/strategy_rcs/engine/op1_executor.py
# Modul untuk mengeksekusi OP1
# =====================================================

from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState
from strategies.strategy_rcs.rcs_order_manager import send_market_order_rcs, send_pending_order_rcs
from utils.colors import cprint, Colors
import MetaTrader5 as mt5

def calculate_tp1_distance(state: RCSState, config: RCSConfig) -> float:
    """Hitung jarak TP1 (dalam point/price delta) berdasarkan % dari Jarak OP1 ke OP2."""
    dist_op1_op2 = abs(state.op2_level - state.op1_level) if state.op2_level else 0.0
    if dist_op1_op2 == 0.0:
        dist_op1_op2 = state.trigger_risk_range * (config.op2_percent / 100.0)
        
    if config.tp_mode == "PERCENT":
        return dist_op1_op2 * (config.tp_percent / 100.0)
    else: # USD
        return dist_op1_op2 * 1.0

def calculate_tp1_price(op1_price: float, state: RCSState, config: RCSConfig) -> float:
    """Hitung letak TP1 berdasarkan % dari Jarak OP1 ke OP2."""
    direction = state.trigger_direction
    tp_dist = calculate_tp1_distance(state, config)

    if direction == "BUY":
        return op1_price + tp_dist
    else:
        return op1_price - tp_dist


def place_op1_order(symbol: str, current_price: float, state: RCSState, config: RCSConfig) -> bool:
    """
    Pasang order OP1 langsung ke MT5 (Bisa Market atau Limit).
    """
    if state.op1_ticket is not None:
        return False
        
    sl = state.op3_level if config.op3_mode == "SL" else 0.0
    actual_entry_price = current_price if config.op1_entry_mode == "INSTANT_ZERO" else state.op1_level
    tp_dist = calculate_tp1_distance(state, config)
    tp = calculate_tp1_price(actual_entry_price, state, config)
    state.tp1_price = tp
    
    print(cprint(f"⚡ Memasang OP1 {state.trigger_direction}...", Colors.CYAN))
    
    if config.op1_entry_mode == "INSTANT_ZERO":
        res = send_market_order_rcs(
            symbol=symbol,
            action_str=state.trigger_direction,
            price=current_price,
            lot_size=config.lot_size_op1,
            magic_number=config.magic_op1,
            comment="RCS_OP1",
            sl=sl,
            tp=tp,
            tp_dist=tp_dist
        )
    else: # PERCENT
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if state.trigger_direction == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
        res = send_pending_order_rcs(
            symbol=symbol,
            order_type=order_type,
            price=state.op1_level,
            lot_size=config.lot_size_op1,
            magic_number=config.magic_op1,
            comment="RCS_OP1",
            sl=sl,
            tp=tp
        )
        
    if res:
        state.op1_ticket = res.order
        state.op1_open_price = res.price if (config.op1_entry_mode == "INSTANT_ZERO" and res.price) else state.op1_level
        # Perbarui state.tp1_price dengan harga fill riil
        if config.op1_entry_mode == "INSTANT_ZERO" and res.price:
            state.tp1_price = calculate_tp1_price(res.price, state, config)
            tp = state.tp1_price
        
        # Simpan tiket per akun untuk audit multi-akun
        all_results = getattr(res, "all_results", [])
        if all_results:
            for r in all_results:
                if r.get("success") and r.get("order"):
                    k = r.get("key")
                    if k not in state.multi_account_tickets:
                        state.multi_account_tickets[k] = []
                    state.multi_account_tickets[k].append(r.get("order"))
        elif res.order:
            if "ACC1" not in state.multi_account_tickets:
                state.multi_account_tickets["ACC1"] = []
            state.multi_account_tickets["ACC1"].append(res.order)

        print(cprint(f"✅ OP1 Berhasil Terpasang! Tkt: {res.order}, Prc: {state.op1_open_price:.5f}, TP: {tp:.5f}, SL: {sl:.5f}", Colors.GREEN))
        return True
        
    return False
