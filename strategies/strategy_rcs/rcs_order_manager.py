# =====================================================
# strategies/strategy_rcs/rcs_order_manager.py
# Helper untuk order dan posisi khusus modul RCS
# =====================================================

import MetaTrader5 as mt5

def send_market_order_rcs(symbol: str, action_str: str, price: float, lot_size: float, magic_number: int, comment: str):
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
