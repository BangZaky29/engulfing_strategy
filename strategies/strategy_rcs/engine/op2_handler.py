# =====================================================
# strategies/strategy_rcs/engine/op2_handler.py
# Logika deteksi dan eksekusi OP2 (Hedge / Hedge Reentry)
# =====================================================

from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState, RCSPhase
from strategies.strategy_rcs.rcs_order_manager import send_market_order_rcs
from utils.colors import cprint, Colors

def calculate_tp2_price(op1_price: float, op2_price: float, state: RCSState, config: RCSConfig) -> float:
    """Hitung letak TP2 khusus mode HEDGE_REENTRY."""
    direction = state.trigger_direction
    risk_range = state.trigger_risk_range
    
    if config.tp2_mode == "PERCENT":
        # Target TP2 berbasis persentase jarak OP1 ke OP2 (range risiko)
        dist = abs(state.op1_level - state.op2_level)
        tp_dist = dist * (config.tp2_percent / 100.0)
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


def check_op2(symbol: str, tick, info, state: RCSState, config: RCSConfig) -> bool:
    """
    Cek apakah harga menyentuh level OP2 dan lakukan eksekusi jika perlu.
    """
    if state.op1_ticket is None or state.op2_ticket is not None:
        return False
        
    if config.op2_mode == "SL":
        return False # SL di-handle oleh sl_checker
        
    target_price = state.op2_level
    current_price = tick.bid if state.trigger_direction == "BUY" else tick.ask
    
    op2_hit = False
    if state.trigger_direction == "BUY":
        if current_price <= target_price:
            op2_hit = True
    else:
        if current_price >= target_price:
            op2_hit = True
            
    if op2_hit:
        action_str = ""
        is_hedge = False
        
        if config.op2_mode == "HEDGE":
            action_str = "SELL" if state.trigger_direction == "BUY" else "BUY"
            is_hedge = True
        elif config.op2_mode == "HEDGE_REENTRY":
            action_str = state.trigger_direction
            is_hedge = False
            
        print(cprint(f"⚡ Harga menyentuh level OP2 ({target_price:.5f}). Mengeksekusi OP2 {action_str}...", Colors.CYAN))
        
        # Eksekusi Market
        execute_price = tick.ask if action_str == "BUY" else tick.bid
        res = send_market_order_rcs(
            symbol=symbol,
            action_str=action_str,
            price=execute_price,
            lot_size=config.lot_size_op2,
            magic_number=config.magic_op2,
            comment="RCS_OP2"
        )
        
        if res:
            state.op2_ticket = res.order
            
            if is_hedge:
                print(cprint(f"❄️ HEDGE (OP2) Terbuka. Beralih ke PHASE_FREEZE.", Colors.CYAN))
                state.phase = RCSPhase.FREEZE
                state.freeze_is_hedge = True
                # Nanti set floating_usd di phase freeze manager (Phase 5)
            else:
                # HEDGE_REENTRY
                state.tp2_price = calculate_tp2_price(state.op1_open_price, res.price, state, config)
                print(cprint(f"✅ HEDGE_REENTRY (OP2) Terbuka. Target baru TP2: {state.tp2_price:.5f}", Colors.GREEN))
                
            if config.notif_open:
                # TODO: WA Notification open posisi OP2
                pass
                
            return True
            
    return False
