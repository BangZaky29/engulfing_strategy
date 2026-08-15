import os
import MetaTrader5 as mt5
from indicatorInfo.triggerInfo.scanner.patterns.marubozu import MarubozuPattern
from utils.colors import Colors, cprint
from strategies.strategy_rcs.rcs_order_manager import (
    send_market_order_rcs, 
    send_pending_order_rcs, 
    cancel_pending_order_rcs,
    close_position_by_ticket
)
from mt5_client.connection import init_mt5
from strategies.recovery_marubozu.mrcv_state import MRCVState, MRCVPhase
from strategies.recovery_marubozu.mrcv_notifier import notify_mrcv_trigger

def calculate_ring_c1(symbol: str, candle: dict) -> float:
    """
    Hitung jarak Ring C1 dalam point.
    Candle Hijau (BUY): Close -> Low
    Candle Merah (SELL): High -> Close
    """
    point = mt5.symbol_info(symbol).point
    if not point: return 0.0

    c_close = candle["close_"]
    c_open = candle["open_"]
    c_high = candle["high_"]
    c_low = candle["low_"]

    if c_close > c_open: # Hijau
        return (c_close - c_low) / point
    elif c_close < c_open: # Merah
        return (c_high - c_close) / point
    else:
        return 0.0

def process_marubozu_trigger(symbol: str, candle: dict, state: MRCVState):
    """
    Eksekusi saat trigger Marubozu muncul.
    """
    print(cprint(f"🚀 [MRCV] Trigger Marubozu Terdeteksi pada {symbol}", Colors.YELLOW))
    
    point = mt5.symbol_info(symbol).point
    if not point: return

    c_close = candle["close_"]
    c_open = candle["open_"]
    
    # 1. Hitung Ring C1
    ring_pts = calculate_ring_c1(symbol, candle)
    if ring_pts <= 0:
        return

    # Arah eksekusi
    direction = "BUY" if c_close > c_open else "SELL"
    
    lot_op1 = float(os.getenv("MRCV_LOT_OP1", "0.01"))
    lot_op2 = round(lot_op1 * 2, 2)
    lot_op3 = round(lot_op1 + lot_op2, 2)
    magic = int(os.getenv("MRCV_MAGIC_NUMBER", "999000"))
    
    tick = mt5.symbol_info_tick(symbol)
    if not tick: return
    
    op1_price = tick.ask if direction == "BUY" else tick.bid
    
    # Kalkulasi Target & Level
    # OP1
    tp1_pts = ring_pts * 0.5
    tp1_price = op1_price + (tp1_pts * point) if direction == "BUY" else op1_price - (tp1_pts * point)
    
    # OP2
    op2_pts = ring_pts * 0.5
    op2_price = op1_price - (op2_pts * point) if direction == "BUY" else op1_price + (op2_pts * point)
    # Jarak OP1 ke OP2 (dalam pts)
    dist_op1_op2 = abs(op1_price - op2_price) / point
    tp2_pts = dist_op1_op2 * 0.9
    tp2_price = op2_price + (tp2_pts * point) if direction == "BUY" else op2_price - (tp2_pts * point)
    
    # OP3 (Hedge)
    op3_pts = ring_pts * 1.1
    op3_price = op1_price - (op3_pts * point) if direction == "BUY" else op1_price + (op3_pts * point)
    
    # 2. Eksekusi OP1 Market
    print(cprint(f"📈 [MRCV] OP1 {direction} di {op1_price:.5f} | TP1: {tp1_price:.5f}", Colors.CYAN))
    op1_res = send_market_order_rcs(symbol, direction, op1_price, lot_op1, magic, "MRCV_OP1", sl=0.0, tp=tp1_price)
    if not op1_res:
        print(cprint(f"❌ [MRCV] Gagal Open OP1", Colors.RED))
        return
        
    state.op1_ticket = op1_res.order
    state.op1_open_price = op1_res.price
    
    # 3. Pasang Limit Order OP2
    op2_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
    print(cprint(f"📉 [MRCV] Pending OP2 {direction} LIMIT di {op2_price:.5f} | TP2: {tp2_price:.5f}", Colors.CYAN))
    op2_res = send_pending_order_rcs(symbol, op2_type, op2_price, lot_op2, magic+1, "MRCV_OP2", tp=tp2_price)
    if op2_res:
        state.op2_ticket = op2_res.order
        
    # 4. Pasang Stop Order OP3 (Hedge - Berlawanan Arah)
    op3_direction = "SELL" if direction == "BUY" else "BUY"
    op3_type = mt5.ORDER_TYPE_SELL_STOP if direction == "BUY" else mt5.ORDER_TYPE_BUY_STOP
    print(cprint(f"❄️ [MRCV] Pending OP3 (HEDGE) {op3_direction} STOP di {op3_price:.5f}", Colors.CYAN))
    op3_res = send_pending_order_rcs(symbol, op3_type, op3_price, lot_op3, magic+2, "MRCV_OP3")
    if op3_res:
        state.op3_ticket = op3_res.order
        
    # Update state
    state.phase = MRCVPhase.ACTIVE
    state.trigger_direction = direction
    state.trigger_ring_c1_pts = ring_pts
    state.op1_level = state.op1_open_price
    state.op2_level = op2_price
    state.op3_level = op3_price
    state.tp1_price = tp1_price
    state.tp2_price = tp2_price

    tf_label = os.getenv("MRCV_TIMEFRAME", "M5")
    c_high = float(candle.get("high_", 0.0))
    c_low = float(candle.get("low_", 0.0))
    ts = candle.get("timestamp")
    if hasattr(ts, 'strftime'):
        time_str = ts.strftime("%H:%M")
    else:
        time_str = str(ts) if ts else "-"

    pips = ring_pts / 10.0

    notify_mrcv_trigger(
        symbol=symbol,
        tf_label=tf_label,
        direction=direction,
        c_high=c_high,
        c_low=c_low,
        ring_pts=ring_pts,
        pips=pips,
        time_str=time_str,
        state=state,
        lot_op1=lot_op1,
        lot_op2=lot_op2,
        lot_op3=lot_op3,
        op3_direction=op3_direction
    )

def cleanup_pending_orders(state: MRCVState):
    """Menghapus pending order yang masih aktif jika siklus selesai."""
    if state.op2_ticket:
        cancel_pending_order_rcs(state.op2_ticket)
        state.op2_ticket = None
    if state.op3_ticket:
        cancel_pending_order_rcs(state.op3_ticket)
        state.op3_ticket = None

