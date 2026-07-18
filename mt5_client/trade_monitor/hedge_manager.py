# =====================================================
# mt5_client/trade_monitor/hedge_manager.py
# Hedge management: cancel/cek OP-2 hedge terkait OP-1.
# =====================================================

import MetaTrader5 as mt5

from database.supabase_client import get_supabase
from mt5_client.error_helper import get_last_error
from .tracker_store import save_tracked_trades


def cancel_hedge_if_op1_expired(info: dict, state_name: str, msg: str) -> str:
    """
    Cancel OP-2 hedge jika OP-1 expired/canceled.
    Returns updated msg string.
    """
    # --- CANCEL OP-2 HEDGE JIKA OP-1 EXPIRED/CANCELED ---
    hedge_ticket = info.get("hedge_ticket")
    if hedge_ticket:
        h_orders = mt5.orders_get(ticket=hedge_ticket)  # type: ignore
        if h_orders is not None and len(h_orders) > 0:
            print(f"🧹 Menghapus OP-2 (Hedge #{hedge_ticket}) otomatis karena OP-1 {state_name}.")
            req = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": hedge_ticket
            }
            res = mt5.order_send(req)  # type: ignore
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ OP-2 (#{hedge_ticket}) berhasil dihapus mengikuti OP-1 yang batal.")
                msg += f"\n🗑️ _Info Tambahan: Limit Order Hedging (OP-2) juga telah dihapus otomatis._"
    # ---------------------------------------------------
    return msg


def check_hedge_touched(ticket: int, info: dict, data: dict, session_str: str) -> None:
    """
    Cek apakah OP-2 hedge sudah tersentuh (filled).
    Jika ya, hapus TP dari OP-1 agar bisa float.
    """
    # --- CEK HEDGING OP-2 TERSENTUH ---
    hedge_ticket = info.get("hedge_ticket")
    hedge_triggered = info.get("hedge_triggered", False)
    
    if hedge_ticket and not hedge_triggered:
        hedge_positions = mt5.positions_get(ticket=hedge_ticket)  # type: ignore
        if hedge_positions and len(hedge_positions) > 0:
            print(f"⚠️ HEDGE OP-2 (#{hedge_ticket}) TERSENTUH! Menghapus TP dari OP-1 (#{ticket})")
            req = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": info["symbol"],
                "sl": 0.0,
                "tp": 0.0
            }
            res = mt5.order_send(req)  # type: ignore
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print("✅ TP OP-1 berhasil dihapus karena Hedging aktif.")
                info["hedge_triggered"] = True
                info["tp_price"] = 0.0
                save_tracked_trades(data)
                
                # Opsional: Log ke wa_trigger
                try:
                    supabase = get_supabase()
                    log_data = {
                        "ticket_id": hedge_ticket,
                        "symbol": info['symbol'],
                        "mode": info['mode'],
                        "message": f"⚠️ HEDGE OP-2 TERSENTUH! TP untuk OP-1 (#{ticket}) otomatis dihapus.",
                        "op_price": info['op_price'],
                        "sl_price": 0.0,
                        "tp_price": 0.0,
                        "trading_session": session_str
                    }
                    res_log = supabase.table("trade_active_logs").insert(log_data).execute()
                except Exception as ex:
                    print(f"⚠️ Gagal menyimpan log Hedge ke Supabase: {ex}")
            else:
                err_txt = res.comment if res else get_last_error()
                print(f"❌ Gagal hapus TP OP-1: {err_txt}")
    # ----------------------------------


def cancel_hedge_if_tp_hit(ticket: int, info: dict, result_str: str, session_str: str) -> None:
    """
    Cancel OP-2 hedge jika OP-1 kena TP profit.
    """
    # --- CANCEL HEDGE JIKA OP-1 KENA TP PROFIT ---
    hedge_ticket = info.get("hedge_ticket")
    if result_str == "PROFIT" and hedge_ticket:
        hedge_orders = mt5.orders_get(ticket=hedge_ticket)  # type: ignore
        if hedge_orders is not None and len(hedge_orders) > 0:
            print(f"🧹 Menghapus OP-2 (Hedge #{hedge_ticket}) otomatis karena OP-1 sudah Kena TP Profit.")
            req = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": hedge_ticket
            }
            res = mt5.order_send(req)  # type: ignore
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ OP-2 (#{hedge_ticket}) berhasil dihapus otomatis.")
                try:
                    supabase = get_supabase()
                    log_data = {
                        "ticket_id": hedge_ticket,
                        "symbol": info['symbol'],
                        "mode": info['mode'],
                        "message": f"🧹 HAPUS OP-2 OTOMATIS! OP-1 telah mencapai Take Profit, sehingga Pending Order Hedging OP-2 (#{hedge_ticket}) dihapus secara otomatis dari market.",
                        "op_price": 0.0,
                        "sl_price": 0.0,
                        "tp_price": 0.0,
                        "trading_session": session_str
                    }
                    supabase.table("trade_active_logs").insert(log_data).execute()
                except Exception as ex:
                    pass
            else:
                err_txt = res.comment if res else get_last_error()
                print(f"❌ Gagal hapus otomatis OP-2 (#{hedge_ticket}): {err_txt}")
    # ---------------------------------------------
