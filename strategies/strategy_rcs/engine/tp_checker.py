# =====================================================
# strategies/strategy_rcs/engine/tp_checker.py
# Pengecekan TP1/TP2 
# =====================================================

import MetaTrader5 as mt5
from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState
from strategies.strategy_rcs.rcs_order_manager import close_position_rcs
from utils.colors import cprint, Colors

def check_tp(symbol: str, tick, state: RCSState, config: RCSConfig) -> bool:
    """
    Cek apakah harga sekarang menyentuh TP. 
    (Jika OP1 saja -> cek TP1. Jika ada OP2 -> cek TP2)
    Return True jika posisi ditutup karena kena TP.
    """
    # Untuk simplifikasi pada phase 3, kita hanya cek TP1 untuk OP1
    if state.op1_ticket is None:
        return False
        
    current_price = tick.bid if state.trigger_direction == "BUY" else tick.ask
    tp_hit = False
    
    if state.trigger_direction == "BUY":
        if current_price >= state.tp1_price:
            tp_hit = True
    else:
        if current_price <= state.tp1_price:
            tp_hit = True
            
    if tp_hit:
        print(cprint(f"🎯 Harga menyentuh TP1 ({state.tp1_price:.5f}). Menutup OP1...", Colors.CYAN))
        pos = mt5.positions_get(ticket=state.op1_ticket)
        if pos and len(pos) > 0:
            res = close_position_rcs(symbol, pos[0], config.magic_op1, "RCS_TP1_CLOSE")
            if res:
                print(cprint(f"✅ OP1 Closed by TP!", Colors.GREEN))
                if config.notif_result:
                    # TODO: Notifikasi result
                    pass
                return True
        else:
            # Posisi sudah hilang (mungkin SL/TP broker)
            return True
            
    return False
