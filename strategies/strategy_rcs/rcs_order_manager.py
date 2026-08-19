# =====================================================
# strategies/strategy_rcs/rcs_order_manager.py
# Helper untuk order dan posisi khusus modul RCS
# =====================================================

import MetaTrader5 as mt5

def get_filling_mode(symbol: str) -> int:
    info = mt5.symbol_info(symbol)
    if not info:
        return mt5.ORDER_FILLING_IOC
    # Beberapa broker HANYA mendukung FOK, beberapa IOC.
    # Di Python MT5, SYMBOL_FILLING_FOK dan IOC tidak diexpose secara konstan.
    # Nilai bitmask aslinya: FOK = 1, IOC = 2
    if (info.filling_mode & 1) == 1:
        return mt5.ORDER_FILLING_FOK
    elif (info.filling_mode & 2) == 2:
        return mt5.ORDER_FILLING_IOC
    else:
        return mt5.ORDER_FILLING_RETURN

def send_market_order_rcs(symbol: str, action_str: str, price: float, lot_size: float, magic_number: int, comment: str, sl: float = 0.0, tp: float = 0.0):
    """
    Kirim market order (Instant Execution).
    action_str: "BUY" atau "SELL"
    """
    import os
    order_type = mt5.ORDER_TYPE_BUY if action_str == "BUY" else mt5.ORDER_TYPE_SELL

    if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
        from mt5_client.multi_account_dispatcher import dispatch_multi_account_order
        order_role = "OP1" if "OP1" in comment else ("OP2" if "OP2" in comment else "OP3")
        payload = {
            "symbol": symbol,
            "action": mt5.TRADE_ACTION_DEAL,
            "type": order_type,
            "price": price,
            "sl": float(sl) if sl > 0 else 0.0,
            "tp": float(tp) if tp > 0 else 0.0,
            "magic": magic_number,
            "comment": comment,
            "order_role": order_role
        }
        primary_res, all_res = dispatch_multi_account_order("RCS", payload)
        if primary_res:
            return primary_res
        else:
            print(f"❌ Multi-Account Dispatcher Gagal mengeksekusi order.")
            return None

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
        "type_filling": get_filling_mode(symbol),
    }
    
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        return res
    else:
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
        "type_filling": get_filling_mode(symbol),
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
    import os
    if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
        from mt5_client.multi_account_dispatcher import dispatch_multi_account_order
        order_role = "OP2" if "OP2" in comment else ("OP3" if "OP3" in comment else "PENDING")
        payload = {
            "symbol": symbol,
            "action": mt5.TRADE_ACTION_PENDING,
            "type": order_type,
            "price": price,
            "sl": float(sl) if sl > 0 else 0.0,
            "tp": float(tp) if tp > 0 else 0.0,
            "magic": magic_number,
            "comment": comment,
            "order_role": order_role
        }
        primary_res, all_res = dispatch_multi_account_order("RCS", payload)
        if primary_res:
            return primary_res
        else:
            print(f"❌ Multi-Account Dispatcher Gagal memasang pending order.")
            return None

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

def remove_tp_from_position(ticket: int, strategy_name: str = "RCS", symbol: str = "") -> bool:
    """
    Hapus Take Profit dari posisi aktif (set TP = 0.0).
    SL tetap dipertahankan apa adanya.
    Mendukung Multi-Account MT5 (ACC1, ACC2, ACC3).
    """
    import os
    if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
        from mt5_client.multi_account_dispatcher import remove_multi_account_tp
        tickets_map = {"ACC1": [ticket], "ACC2": [ticket], "ACC3": [ticket]} if ticket else None
        cnt = remove_multi_account_tp(strategy_name, symbol, tickets_per_account=tickets_map)
        return cnt > 0

    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return False
    pos = positions[0]

    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": pos.symbol,
        "sl": pos.sl,       # Pertahankan SL yang ada
        "tp": 0.0,          # Hapus TP
    }
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        return True
    else:
        print(f"⚠️ Gagal hapus TP posisi Tkt:{ticket}: {res.comment if res else 'Unknown'} (retcode: {res.retcode if res else 'None'})")
        return False
