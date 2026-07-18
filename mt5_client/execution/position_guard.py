# =====================================================
# mt5_client/execution/position_guard.py
# Modul untuk mengecek posisi aktif dan cancel pending order lama.
# =====================================================

import MetaTrader5 as mt5
from mt5_client.trade_monitor import load_tracked_trades, save_tracked_trades
from mt5_client.error_helper import get_last_error

def check_active_positions(symbol: str) -> tuple[bool, str | None]:
    """Mengecek apakah simbol saat ini sudah memiliki posisi aktif di MT5."""
    positions = mt5.positions_get(symbol=symbol)  # type: ignore
    if positions is None:
        err_msg = f"Gagal cek posisi: {get_last_error()}"
        print(f"❌ Eksekusi dibatalkan: {err_msg} untuk {symbol}")  # type: ignore
        return False, err_msg
    elif len(positions) > 0:
        active_info = []
        for pos in positions:
            pos_type = "BUY" if getattr(pos, "type", None) == mt5.POSITION_TYPE_BUY else "SELL"
            pos_ticket = getattr(pos, "ticket", None)
            pos_price = getattr(pos, "price_open", None) or getattr(pos, "price_current", None) or getattr(pos, "price", None)
            pos_vol = getattr(pos, "volume", None)
            pair = f"#{pos_ticket} {pos_type} @ {pos_price:.2f}" if pos_price is not None else f"#{pos_ticket} {pos_type}"
            if pos_vol is not None:
                pair += f" ({pos_vol:.2f})"
            active_info.append(pair)

        active_summary = ", ".join(active_info)
        err_msg = f"Ada posisi aktif ({len(positions)}): {active_summary}"
        print(f"⚠️ Eksekusi di-skip: {err_msg} untuk {symbol}. Menunggu OP sebelumnya close (kena TP/SL).")
        return False, err_msg
        
    return True, None

def cancel_old_pending_orders(symbol: str) -> None:
    """Membatalkan semua pending order lama untuk simbol tertentu."""
    orders = mt5.orders_get(symbol=symbol)  # type: ignore
    if orders is not None and len(orders) > 0:
        for old_order in orders:
            cancel_req = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": old_order.ticket
            }
            res = mt5.order_send(cancel_req)  # type: ignore
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"🧹 PENDING ORDER LAMA ({old_order.ticket}) DIBATALKAN karena ada trigger baru!")
                
                # Kirim log pembatalan ke Supabase agar WA bot men-trigger notifikasi
                try:
                    from database.supabase_client import get_supabase
                    supabase = get_supabase()
                    data_tracker = load_tracked_trades()
                    old_info = data_tracker.get(str(old_order.ticket), {})
                    log_data = {
                        "ticket_id": old_order.ticket,
                        "symbol": symbol,
                        "mode": old_info.get("mode", "BUY"),
                        "message": f"🧹 PENDING ORDER OVERRIDDEN! Dibatalkan karena ada trigger baru (sinyal ke-2) yang aktif.",
                        "op_price": old_info.get("op_price"),
                        "sl_price": old_info.get("sl_price"),
                        "tp_price": old_info.get("tp_price"),
                        "trading_session": old_info.get("trading_session", "Unknown")
                    }
                    supabase.table("trade_active_logs").insert(log_data).execute()
                    
                    # Hapus dari tracker agar tidak dicek oleh trade_monitor
                    if str(old_order.ticket) in data_tracker:
                        del data_tracker[str(old_order.ticket)]
                        save_tracked_trades(data_tracker)
                except Exception as ex:
                    print(f"⚠️ Gagal memproses log override ke Supabase: {ex}")
            else:
                print(f"⚠️ Gagal membatalkan pending order lama ({old_order.ticket}): {get_last_error()}")
