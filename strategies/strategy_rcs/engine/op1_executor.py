# =====================================================
# strategies/strategy_rcs/engine/op1_executor.py
# Modul untuk mengeksekusi OP1
# =====================================================

from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState
from strategies.strategy_rcs.rcs_order_manager import send_market_order_rcs
from utils.colors import cprint, Colors

def calculate_tp1_price(op1_price: float, state: RCSState, config: RCSConfig) -> float:
    """Hitung letak TP1 berdasarkan konfigurasi."""
    direction = state.trigger_direction
    risk_range = state.trigger_risk_range
    
    if config.tp_mode == "PERCENT":
        # TP dalam mode PERCENT menggunakan jarak OP1 ke OP2 (yang diset dari risk range dan op2_percent).
        # Karena kita sudah punya risk_range, jarak OP1 ke OP2 = risk_range * (op2_percent - entry_percent)/100 ?
        # Blueprint: "TP1 dihitung dari OP1_OpenPrice ... persen jarak OP1-OP2"
        dist = abs(state.op1_level - state.op2_level)
        tp_dist = dist * (config.tp_percent / 100.0)
    else: # USD
        # Nanti USD mode butuh kalkulasi poin ke USD. 
        # Untuk simplifikasi phase ini, kita gunakan risk_range * 100% jika USD belum dikonversi.
        # Konversi USD ke pts perlu tick_value. Kita biarkan fallback ke PERCENT 100% dulu jika belum sempurna.
        tp_dist = risk_range * 1.0 # fallback

    if direction == "BUY":
        return op1_price + tp_dist
    else:
        return op1_price - tp_dist


def try_execute_op1(symbol: str, tick, info, state: RCSState, config: RCSConfig) -> bool:
    """
    Coba eksekusi OP1. Return True jika berhasil tereksekusi.
    """
    if state.op1_ticket is not None:
        return False # Sudah dieksekusi sebelumnya
        
    current_price = tick.ask if state.trigger_direction == "BUY" else tick.bid
    point = info.point
    
    target_price = state.op1_level
    
    should_execute = False
    
    if config.op1_entry_mode == "INSTANT_ZERO":
        # Instant-Zero: langsung eksekusi selama belum slip jauh
        slip_pts = abs(current_price - target_price) / point
        if slip_pts <= config.max_instant_slip_pts:
            should_execute = True
            
    elif config.op1_entry_mode == "PERCENT":
        tol = config.entry_tolerance_pts * point
        
        # BUY: OP1 di bawah, kita tunggu harga turun menyentuh target
        if state.trigger_direction == "BUY":
            if current_price <= target_price + tol:
                should_execute = True
        # SELL: OP1 di atas, kita tunggu harga naik menyentuh target
        else:
            if current_price >= target_price - tol:
                should_execute = True
                
        # Slip filter target: jangan eksekusi kalau tiba-tiba loncat harga kejauhan
        if should_execute:
            if state.trigger_direction == "BUY" and current_price < target_price - (config.max_target_slip_pts * point):
                should_execute = False
            elif state.trigger_direction == "SELL" and current_price > target_price + (config.max_target_slip_pts * point):
                should_execute = False

    if should_execute:
        print(cprint(f"⚡ Mengeksekusi OP1 {state.trigger_direction} @ Market...", Colors.CYAN))
        res = send_market_order_rcs(
            symbol=symbol,
            action_str=state.trigger_direction,
            price=current_price,
            lot_size=config.lot_size_op1,
            magic_number=config.magic_op1,
            comment="RCS_OP1"
        )
        if res:
            state.op1_ticket = res.order
            state.op1_open_price = res.price
            state.tp1_price = calculate_tp1_price(res.price, state, config)
            print(cprint(f"✅ OP1 Berhasil! Tkt: {res.order}, Prc: {res.price}, TP1: {state.tp1_price:.5f}", Colors.GREEN))
            
            if config.notif_open:
                # TODO: WA Notification open posisi
                pass
            return True
            
    return False
