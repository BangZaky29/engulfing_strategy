# =====================================================
# strategies/strategy_rcs/engine/op3_handler.py
# Logika deteksi dan eksekusi OP3
# =====================================================

from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState, RCSPhase
from strategies.strategy_rcs.rcs_order_manager import send_market_order_rcs
from utils.colors import cprint, Colors

def check_op3(symbol: str, tick, info, state: RCSState, config: RCSConfig) -> bool:
    """
    Cek apakah harga menyentuh level OP3 khusus untuk HEDGE.
    (Hanya dipanggil jika OP2_MODE == HEDGE_REENTRY)
    """
    # Jika OP2 belum ada atau OP3 sudah ada, lewati
    if state.op2_ticket is None or state.op3_ticket is not None:
        return False
        
    # Jika OP3 mode-nya SL, di-handle sl_checker
    if config.op3_mode == "SL":
        return False
        
    target_price = state.op3_level
    current_price = tick.bid if state.trigger_direction == "BUY" else tick.ask
    
    op3_hit = False
    if state.trigger_direction == "BUY":
        if current_price <= target_price:
            op3_hit = True
    else:
        if current_price >= target_price:
            op3_hit = True
            
    if op3_hit:
        # HEDGE
        action_str = "SELL" if state.trigger_direction == "BUY" else "BUY"
        execute_price = tick.ask if action_str == "BUY" else tick.bid
        
        # OP3 Lot = OP1 + OP2
        lot_size = config.lot_size_op1 + config.lot_size_op2
        
        print(cprint(f"⚡ Harga menyentuh OP3 ({target_price:.5f}). Eksekusi OP3 {action_str} HEDGE...", Colors.CYAN))
        
        res = send_market_order_rcs(
            symbol=symbol,
            action_str=action_str,
            price=execute_price,
            lot_size=lot_size,
            magic_number=config.magic_op3,
            comment="RCS_OP3"
        )
        
        if res:
            state.op3_ticket = res.order
            print(cprint(f"❄️ HEDGE (OP3) Terbuka. Beralih ke PHASE_FREEZE.", Colors.CYAN))
            state.phase = RCSPhase.FREEZE
            state.freeze_is_hedge = True
            
            if config.notif_open:
                # TODO: WA Notification open posisi OP3
                pass
                
            return True
            
    return False
