# =====================================================
# strategies/strategy_rcs/rcs_order_manager.py
# Helper untuk order dan posisi khusus modul RCS
# =====================================================

import MetaTrader5 as mt5

def send_market_order_rcs(symbol: str, action_str: str, price: float, lot_size: float, magic_number: int, comment: str, sl: float = 0.0, tp: float = 0.0):
    """
    Kirim market order (Instant Execution).
    action_str: "BUY" atau "SELL"
    """
    order_type = mt5.ORDER_TYPE_BUY if action_str == "BUY" else mt5.ORDER_TYPE_SELL
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": order_type,
        "price": price,
        "sl": float(sl) if sl > 0 else 0.0,
        "tp": float(tp) if tp > 0 else 0.0,
        "deviation": 20,
        "magic": magic_number,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        return res
    else:
        # Jika perlu log error MT5
        print(f"❌ Order Gagal: {res.comment if res else 'Unknown'} (retcode: {res.retcode if res else 'None'})")
        return None

def close_position_rcs(symbol: str, pos, magic_number: int, comment: str) -> bool:
    """
    Tutup suatu posisi yang ada di market.
    """
    action_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return False
        
    price = tick.bid if action_type == mt5.ORDER_TYPE_SELL else tick.ask
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": pos.ticket,
        "symbol": symbol,
        "volume": pos.volume,
        "type": action_type,
        "price": price,
        "deviation": 20,
        "magic": magic_number,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        return True
    return False

def get_positions_by_magic(symbol: str, magic: int) -> list:
    """Ambil semua posisi aktif berdasar magic number"""
    pos = mt5.positions_get(symbol=symbol)
    if pos is None:
        return []
    return [p for p in pos if p.magic == magic]

def send_pending_order_rcs(symbol: str, order_type: int, price: float, lot_size: float, magic_number: int, comment: str, sl: float = 0.0, tp: float = 0.0):
    """
    Kirim pending order (BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP).
    """
    req = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": order_type,
        "price": price,
        "sl": float(sl) if sl > 0 else 0.0,
        "tp": float(tp) if tp > 0 else 0.0,
        "deviation": 20,
        "magic": magic_number,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN, # RETURN for pending orders
    }
    
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        return res
    else:
        print(f"❌ Pending Order Gagal: {res.comment if res else 'Unknown'} (retcode: {res.retcode if res else 'None'})")
        return None

def cancel_pending_order_rcs(ticket: int) -> bool:
    """
    Batalkan pending order yang belum tereksekusi.
    """
    req = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket
    }
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        return True
    return False

def get_orders_by_magic(symbol: str, magic: int) -> list:
    """Ambil semua pending order aktif berdasar magic number"""
    orders = mt5.orders_get(symbol=symbol)
    if orders is None:
        return []
    return [o for o in orders if o.magic == magic]

def close_position_by_ticket(ticket: int) -> bool:
    """
    Tutup posisi aktif MT5 berdasarkan tiket posisi.
    """
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return False
    pos = positions[0]
    return close_position_rcs(pos.symbol, pos, pos.magic, f"Close Ticket {ticket}")
