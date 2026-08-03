# =====================================================
# strategies/strategy_rcs/engine/op2_handler.py
# Logika deteksi dan eksekusi OP2 (Hedge / Hedge Reentry)
# =====================================================

from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState, RCSPhase
from strategies.strategy_rcs.rcs_order_manager import send_pending_order_rcs
from utils.colors import cprint, Colors
import MetaTrader5 as mt5

def calculate_tp2_price(op1_price: float, op2_price: float, state: RCSState, config: RCSConfig) -> float:
    """Hitung letak TP2 khusus mode HEDGE_REENTRY."""
    direction = state.trigger_direction
    risk_range = state.trigger_risk_range
    
    if config.tp2_mode == "PERCENT":
        # Target TP2 berbasis persentase dari Total Risk Range
        tp_dist = risk_range * (config.tp2_percent / 100.0)
    else:
        # USD Mode
        tp_dist = risk_range * 1.0
        
    # Karena ini re-entry searah (contoh: BUY lalu turun OP2 BUY lagi)
    # TP2 diletakkan di atas harga OP2. (Bisa dirata-rata, tapi blueprint 
    # menyebut TP2 diukur dari jarak OP1-OP2).
    # Untuk sementara kita gunakan jarak murni ke atas dari OP2.
    if direction == "BUY":
        return op2_price + tp_dist
    else:
        return op2_price - tp_dist


def place_op2_order(symbol: str, state: RCSState, config: RCSConfig) -> bool:
    """
    Pasang pending order OP2 langsung ke MT5 (Limit atau Stop Order).
    """
    if state.op2_ticket is not None:
        return False
        
    if config.op2_mode == "SL":
        return False # SL di-handle langsung di SL parameter OP1
        
    tp = 0.0
    sl = state.op3_level if config.op3_mode == "SL" else 0.0
    
    if config.op2_mode == "HEDGE":
        action_str = "SELL" if state.trigger_direction == "BUY" else "BUY"
        # Harga memburuk (OP2), mau HEDGE (potong berlawanan), jadi Stop Order
        order_type = mt5.ORDER_TYPE_SELL_STOP if state.trigger_direction == "BUY" else mt5.ORDER_TYPE_BUY_STOP
    else: # HEDGE_REENTRY
        action_str = state.trigger_direction
        # Harga memburuk, Averaging searah, jadi Limit Order
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if state.trigger_direction == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
        
        tp = calculate_tp2_price(state.op1_level, state.op2_level, state, config)
        state.tp2_price = tp

    print(cprint(f"⚡ Memasang Pending Order OP2 {action_str} ({config.op2_mode})...", Colors.CYAN))
    
    res = send_pending_order_rcs(
        symbol=symbol,
        order_type=order_type,
        price=state.op2_level,
        lot_size=config.lot_size_op2,
        magic_number=config.magic_op2,
        comment="RCS_OP2",
        sl=sl,
        tp=tp
    )
    
    if res:
        state.op2_ticket = res.order
        print(cprint(f"✅ OP2 Berhasil Terpasang! Tkt: {res.order}, Prc: {state.op2_level:.5f}, TP: {tp:.5f}, SL: {sl:.5f}", Colors.GREEN))
        return True
        
    return False
