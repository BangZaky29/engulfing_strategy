# =====================================================
# strategies/strategy_rcs/engine/sl_checker.py
# Pengecekan Stop Loss (Software SL)
# =====================================================

import MetaTrader5 as mt5
from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState, RCSPhase
from strategies.strategy_rcs.rcs_order_manager import close_position_rcs
from utils.colors import cprint, Colors

def check_sl(symbol: str, tick, state: RCSState, config: RCSConfig) -> bool:
    """
    Cek apakah harga sekarang menyentuh SL.
    Jika ya, tutup seluruh posisi (OP1, OP2, dll) dan reset state.
    """
    if state.op1_ticket is None:
        return False
        
    sl_level = None
    if config.op2_mode == "SL":
        sl_level = state.op2_level
    elif config.op2_mode == "HEDGE_REENTRY" and config.op3_mode == "SL":
        sl_level = state.op3_level
        
    if sl_level is None:
        return False
        
    current_price = tick.bid if state.trigger_direction == "BUY" else tick.ask
    sl_hit = False
    
    # Trigger BUY = SL ada di bawah (harga makin turun)
    if state.trigger_direction == "BUY":
        if current_price <= sl_level:
            sl_hit = True
    else:
        # Trigger SELL = SL ada di atas (harga makin naik)
        if current_price >= sl_level:
            sl_hit = True
            
    if sl_hit:
        print(cprint(f"🛑 Harga menyentuh Stop Loss ({sl_level:.5f}). Menutup semua posisi...", Colors.RED))
        
        # Tutup OP1
        pos1 = mt5.positions_get(ticket=state.op1_ticket)
        if pos1 and len(pos1) > 0:
            close_position_rcs(symbol, pos1[0], config.magic_op1, "RCS_SL_CLOSE_OP1")
            
        # Tutup OP2 jika ada
        if state.op2_ticket is not None:
            pos2 = mt5.positions_get(ticket=state.op2_ticket)
            if pos2 and len(pos2) > 0:
                close_position_rcs(symbol, pos2[0], config.magic_op2, "RCS_SL_CLOSE_OP2")
                
        # Set cooldown 
        cooldown = config.sl_cooldown_candles
        if config.op2_mode == "HEDGE_REENTRY" and config.op3_mode == "SL":
            cooldown = config.op3_cooldown_candles
            
        print(cprint(f"✅ SL Eksekusi selesai. Cooldown aktif: {cooldown} candles.", Colors.YELLOW))
        
        if config.notif_result:
            # TODO: Notif WA SL
            pass
            
        state.reset()
        state.cooldown_until_candle = cooldown
        return True
        
    return False
