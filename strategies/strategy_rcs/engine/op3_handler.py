# =====================================================
# strategies/strategy_rcs/engine/op3_handler.py
# Logika deteksi dan eksekusi OP3
# =====================================================

from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState, RCSPhase
from strategies.strategy_rcs.rcs_order_manager import send_pending_order_rcs
from utils.colors import cprint, Colors
import MetaTrader5 as mt5

def place_op3_order(symbol: str, state: RCSState, config: RCSConfig) -> bool:
    """
    Pasang pending order OP3 (HEDGE) langsung ke MT5 (Stop Order).
    (Hanya dieksekusi jika OP3 mode != SL)
    """
    if state.op3_ticket is not None:
        return False
        
    if config.op3_mode == "SL":
        return False # SL di-handle langsung di SL parameter OP1 & OP2
        
    action_str = "SELL" if state.trigger_direction == "BUY" else "BUY"
    # Harga makin memburuk (menyentuh OP3), kita mau cut loss virtual via HEDGE, jadi Stop Order
    order_type = mt5.ORDER_TYPE_SELL_STOP if state.trigger_direction == "BUY" else mt5.ORDER_TYPE_BUY_STOP
    
    lot_size = round(config.lot_size_op1 + config.lot_size_op2, 2)
    
    print(cprint(f"⚡ Memasang Pending Order OP3 {action_str} (HEDGE)...", Colors.CYAN))
    
    res = send_pending_order_rcs(
        symbol=symbol,
        order_type=order_type,
        price=state.op3_level,
        lot_size=lot_size,
        magic_number=config.magic_op3,
        comment="RCS_OP3",
        sl=0.0,
        tp=0.0
    )
    
    if res:
        state.op3_ticket = res.order
        
        # Simpan tiket OP3 per akun
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

        print(cprint(f"✅ OP3 Berhasil Terpasang! Tkt: {res.order}, Prc: {state.op3_level:.5f}", Colors.GREEN))
        return True
        
    return False
