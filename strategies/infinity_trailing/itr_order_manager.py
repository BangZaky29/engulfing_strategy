# =====================================================
# strategies/infinity_trailing/itr_order_manager.py
# Fungsi-fungsi helper untuk eksekusi MT5 ITR
# =====================================================

import MetaTrader5 as mt5

def send_market_order(symbol: str, action_str: str, price: float, lot_size: float, magic_number: int):
    import os
    order_type = mt5.ORDER_TYPE_BUY if action_str == "BUY" else mt5.ORDER_TYPE_SELL

    if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
        from mt5_client.multi_account_dispatcher import dispatch_multi_account_order
        payload = {
            "symbol": symbol,
            "action": mt5.TRADE_ACTION_DEAL,
            "type": order_type,
            "price": price,
            "magic": magic_number,
            "comment": "ITR_OP1",
            "order_role": "OP1"
        }
        dispatch_multi_account_order("ITR", payload)

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": magic_number,
        "comment": "ITR_OP1",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"✅ OP1 {action_str} Berhasil di harga {res.price}")
        return res
    else:
        print(f"❌ OP1 Gagal: {res.comment if res else 'Unknown'}")
        return None

def send_stop_order(symbol: str, action_str: str, price: float, lot_size: float, magic_number: int):
    order_type = mt5.ORDER_TYPE_BUY_STOP if action_str == "BUY" else mt5.ORDER_TYPE_SELL_STOP
    req = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": order_type,
        "price": price,
        "magic": magic_number,
        "comment": "ITR_OP2",
        "type_time": mt5.ORDER_TIME_GTC,
    }
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"✅ OP2 {action_str} STOP Berhasil dipasang di harga {price}")
        return res
    else:
        print(f"❌ OP2 Gagal: {res.comment if res else 'Unknown'}")
        return None

def modify_pending_order(ticket: int, new_price: float):
    req = {
        "action": mt5.TRADE_ACTION_MODIFY,
        "order": ticket,
        "price": new_price,
    }
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"🔄 OP2 Trailed ke harga baru: {new_price}")
        return True
    return False

def close_position(symbol: str, pos, magic_number: int):
    action_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(symbol)
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
        "comment": "ITR_REVERSAL_CLOSE",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"🚪 OP1 Lama (Ticket: {pos.ticket}) Berhasil ditutup.")
        return True
    else:
        print(f"❌ Gagal tutup OP1 Lama: {res.comment if res else 'Unknown'}")
        return False
