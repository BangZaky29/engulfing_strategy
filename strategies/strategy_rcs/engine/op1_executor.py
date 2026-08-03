# =====================================================
# strategies/strategy_rcs/engine/op1_executor.py
# Modul untuk mengeksekusi OP1
# =====================================================

from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState
from strategies.strategy_rcs.rcs_order_manager import send_market_order_rcs, send_pending_order_rcs
from utils.colors import cprint, Colors
import MetaTrader5 as mt5

def calculate_tp1_price(op1_price: float, state: RCSState, config: RCSConfig) -> float:
    """Hitung letak TP1 berdasarkan konfigurasi."""
    direction = state.trigger_direction
    risk_range = state.trigger_risk_range
    
    if config.tp_mode == "PERCENT":
        # TP diukur persis x persen dari ukuran Risk Range total
        tp_dist = risk_range * (config.tp_percent / 100.0)
    else: # USD
        # Nanti USD mode butuh kalkulasi poin ke USD. 
        # Untuk simplifikasi phase ini, kita gunakan risk_range * 100% jika USD belum dikonversi.
        # Konversi USD ke pts perlu tick_value. Kita biarkan fallback ke PERCENT 100% dulu jika belum sempurna.
        tp_dist = risk_range * 1.0 # fallback

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
    tp = calculate_tp1_price(state.op1_level, state, config)
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
            tp=tp
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
        state.op1_open_price = res.price if config.op1_entry_mode == "INSTANT_ZERO" else state.op1_level
        print(cprint(f"✅ OP1 Berhasil Terpasang! Tkt: {res.order}, Prc: {state.op1_open_price:.5f}, TP: {tp:.5f}, SL: {sl:.5f}", Colors.GREEN))
        return True
        
    return False
