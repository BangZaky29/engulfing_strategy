# =====================================================
# mt5_client/trade_monitor.py
# Monitor order yang aktif, cek apakah sudah kena SL/TP, lalu upload SS.
# =====================================================

import json
import os
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import locale

from database.supabase_storage import upload_screenshot
from database.supabase_client import get_supabase
from mt5_client.visualizer import generate_screenshot
from config.mt5_config import MT5Config, EMAConfig

TRACKER_FILE = "trade_tracker.json"
TEMP_DIR = "temp_screenshots"
BUCKET_NAME = "engulfing"


def load_tracked_trades() -> dict:
    if not os.path.exists(TRACKER_FILE):
        return {}
    with open(TRACKER_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}


def save_tracked_trades(data: dict):
    with open(TRACKER_FILE, "w") as f:
        json.dump(data, f, indent=4)


def add_tracked_trade(ticket: int, symbol: str, mode: str, tf: str, op_price: float, sl_price: float, tp_price: float, status: str = "ACTIVE", trading_session: str = "Unknown"):
    """
    Simpan tiket order ke file tracker untuk dimonitor.
    """
    data = load_tracked_trades()
    data[str(ticket)] = {
        "symbol": symbol,
        "mode": mode,  # BUY atau SELL
        "tf": tf,
        "op_price": op_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "status": status,
        "trading_session": trading_session
    }
    save_tracked_trades(data)


def get_indonesian_date_str():
    """Format: Kamis, 11/06/2026"""
    # Gunakan mapping manual hari bahasa indonesia
    hari_map = {
        0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis", 
        4: "Jumat", 5: "Sabtu", 6: "Minggu"
    }
    now = datetime.now()
    hari = hari_map[now.weekday()]
    tgl = now.strftime("%d/%m/%Y")
    # File system kadang bermasalah dengan slash '/'.
    # Untuk Supabase Path, slash '/' berarti folder baru.
    # User minta format: Kamis, 11/06/2026
    # Supabase bisa handle '/', tapi kita buat aman:
    return f"{hari}, {tgl}"


def check_closed_trades(mt5_cfg: MT5Config, ema_cfg: EMAConfig):
    """
    Cek semua trade di tracker. Jika posisi sudah tidak ada, 
    berarti sudah ditutup (SL/TP). Cek profit, ambil SS chart, upload, hapus.
    """
    data = load_tracked_trades()
    if not data:
        return

    keys_to_remove = []

    for ticket_str, info in data.items():
        ticket = int(ticket_str)
        
        status = info.get("status", "ACTIVE")
        session_str = info.get("trading_session", info.get("session", "Unknown"))
        
        # Fallback calculation if session is Unknown and timestamp is present
        if session_str == "Unknown" and "timestamp" in info:
            try:
                dt_local = datetime.strptime(info["timestamp"], "%Y%m%d_%H%M%S")
                dt_local = dt_local.astimezone()  # Local machine timezone
                wib_tz = timezone(timedelta(hours=7))
                dt_wib = dt_local.astimezone(wib_tz)
                hour = dt_wib.hour
                
                sessions = []
                if 7 <= hour < 16:
                    sessions.append("Asia")
                if 14 <= hour < 23:
                    sessions.append("Euro")
                if 19 <= hour <= 23 or 0 <= hour < 4:
                    sessions.append("NY")
                session_str = "/".join(sessions) if sessions else "Off-Market"
                
                info["trading_session"] = session_str
                save_tracked_trades(data)
            except Exception as ex:
                print(f"⚠️ Gagal menghitung session fallback untuk ticket {ticket}: {ex}")
        
        # 1. State Machine: PENDING -> ACTIVE
        if status == "PENDING":
            # Cek apakah masih jadi pending order
            orders = mt5.orders_get(ticket=ticket)  # type: ignore
            if orders is not None and len(orders) > 0:
                # Masih pending, belum tersentuh
                continue
                
            # Jika sudah hilang dari orders_get, cek apakah muncul di positions_get
            positions = mt5.positions_get(ticket=ticket)  # type: ignore
            if positions is not None and len(positions) > 0:
                # ORDER TERSENTUH (FILLED)!
                print(f"🎯 PENDING ORDER TERSENTUH: #{ticket} ({info['symbol']}) | Sesi: {session_str}")
                info["status"] = "ACTIVE"
                # Simpan perubahan status ke JSON
                save_tracked_trades(data)
                
                # Kirim log ke Supabase agar WA bot men-trigger notifikasi
                try:
                    supabase = get_supabase()
                    log_data = {
                        "ticket_id": ticket,
                        "symbol": info['symbol'],
                        "mode": info['mode'],
                        "message": f"🔥 LIMIT ORDER TERSENTUH! Posisi {info['mode']} aktif sekarang.",
                        "op_price": info['op_price'],
                        "sl_price": info['sl_price'],
                        "tp_price": info['tp_price'],
                        "trading_session": session_str
                    }
                    supabase.table("trade_active_logs").insert(log_data).execute()
                except Exception as ex:
                    print(f"⚠️ Gagal menyimpan log aktif ke Supabase: {ex}")
                    
                continue
            
            # Jika tidak ada di orders dan tidak ada di positions, 
            # berarti either Cancelled atau sudah langsung hit TP/SL.
            # Cek di history_orders_get
            hist_orders = mt5.history_orders_get(ticket=ticket)  # type: ignore
            if hist_orders is not None and len(hist_orders) > 0:
                h_order = hist_orders[0]
                if h_order.state in [mt5.ORDER_STATE_EXPIRED, mt5.ORDER_STATE_CANCELED]:
                    from config.execution_config import ExecutionConfig
                    exec_cfg = ExecutionConfig()
                    expire_candles = exec_cfg.pending_order_expire_candles
                    
                    state_name = "EXPIRED" if h_order.state == mt5.ORDER_STATE_EXPIRED else "CANCELED"
                    print(f"🧹 PENDING ORDER {ticket} KADALUWARSA/DIBATALKAN ({state_name}). Menghapus dari tracker.")
                    
                    # Kirim log pembatalan ke Supabase agar WA bot men-trigger notifikasi
                    try:
                        log_data = {
                            "ticket_id": ticket,
                            "symbol": info['symbol'],
                            "mode": info['mode'],
                            "message": f"⏳ PENDING ORDER EXPIRED! Batas waktu {expire_candles} candle terlewati tanpa tersentuh harga.",
                            "op_price": info['op_price'],
                            "sl_price": info['sl_price'],
                            "tp_price": info['tp_price'],
                            "trading_session": session_str
                        }
                        supabase = get_supabase()
                        supabase.table("trade_active_logs").insert(log_data).execute()
                    except Exception as ex:
                        print(f"⚠️ Gagal menyimpan log expired ke Supabase: {ex}")

                    keys_to_remove.append(ticket_str)
                    continue

        # 2. Cek apakah posisi masih aktif (Status = ACTIVE)
        if status == "ACTIVE":
            positions = mt5.positions_get(ticket=ticket)  # type: ignore
            if positions is not None and len(positions) > 0:
                # Posisi masih running, skip
                continue
            
        # 3. Jika tidak ada di positions, berarti sudah closed. Cek history deals.
        # Ambil deal berdasarkan position ID
        deals = mt5.history_deals_get(position=ticket)  # type: ignore
        if deals is None or len(deals) == 0:
            # Belum ada di history, mungkin mt5 butuh waktu sync. Skip dulu.
            continue
            
        # Hitung total profit dan dapatkan waktu entry & exit serta volume (lot size)
        total_profit = 0.0
        entry_time = None
        entry_price = None
        exit_time = None
        exit_price = None
        trade_volume = None
        
        for d in deals:
            if d.entry == mt5.DEAL_ENTRY_IN:
                entry_time = d.time
                entry_price = d.price
                trade_volume = float(d.volume) if hasattr(d, "volume") else None
            elif d.entry == mt5.DEAL_ENTRY_OUT:
                exit_time = d.time
                exit_price = d.price
                total_profit += d.profit
                if trade_volume is None and hasattr(d, "volume"):
                    trade_volume = float(d.volume)
        
        # Tentukan RESULT (LOSS / PROFIT)
        result_str = "PROFIT" if total_profit > 0 else "LOSS"
        print(f"🏁 TRADE CLOSED: #{ticket} ({info['symbol']}) | Result: {result_str} | Profit: ${total_profit:.2f} | Sesi: {session_str}")
        
        # 3. Generate Screenshot Saat Ini
        time_suffix = info["timestamp"].split("_")[1]
        new_filename = f"{info['mode']}_{result_str}_{info['symbol']}_{info['tf']}_{time_suffix}.png"
        new_path = os.path.join(TEMP_DIR, new_filename)
        
        try:
            tf_const = mt5_cfg.get_mt5_timeframe(info['tf'])
            # Ambil candle lebih banyak agar kelihatan dari OP sampai Close
            rates = mt5.copy_rates_from_pos(info['symbol'], tf_const, 0, mt5_cfg.candle_count)  # type: ignore
            if rates is not None and len(rates) > 0:
                img_path = generate_screenshot(
                    rates=rates,
                    ticket_id=ticket,
                    op_price=info['op_price'],
                    sl_price=info['sl_price'],
                    tp_price=info['tp_price'],
                    ema_cfg=ema_cfg,
                    mode=info['mode'],
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=exit_time,
                    exit_price=exit_price,
                    tf_label=info['tf'],
                    output_dir=TEMP_DIR,
                    num_candles=30  # Capture 30 candle terakhir agar history tradenya kelihatan semua
                )
                
                if img_path and os.path.exists(img_path):
                    # Rename ke format yang benar
                    os.rename(img_path, new_path)
                    
                    # 4. Upload ke Supabase
                    folder_date = get_indonesian_date_str().replace('/', '-') 
                    success, public_url = upload_screenshot(new_path, BUCKET_NAME, folder_date, new_filename)
                    
                    if success:
                        os.remove(new_path)
                        
                        # 5. Simpan data ke table trade_analytics
                        try:
                            supabase = get_supabase()
                            analytics_data = {
                                "ticket_id": ticket,
                                "symbol": info['symbol'],
                                "timeframe": info['tf'],
                                "mode": info['mode'],
                                "result": result_str,
                                "op_price": info['op_price'],
                                "sl_price": info['sl_price'],
                                "tp_price": info['tp_price'],
                                "exit_price": exit_price,
                                "volume": trade_volume,
                                "profit": total_profit,
                                "entry_time": datetime.utcfromtimestamp(entry_time).isoformat() if entry_time else None,
                                "exit_time": datetime.utcfromtimestamp(exit_time).isoformat() if exit_time else None,
                                "image_url": public_url,
                                "trading_session": session_str
                            }
                            supabase.table("trade_analytics").insert(analytics_data).execute()
                            print(f"✅ Data analytics sukses disimpan ke Supabase untuk ticket #{ticket}")
                        except Exception as ex:
                            print(f"⚠️ Gagal menyimpan ke tabel trade_analytics: {ex}")
                            
        except Exception as e:
            print(f"⚠️ Gagal generate/upload SS untuk ticket {ticket}: {e}")
 
        # Hapus dari tracker
        keys_to_remove.append(ticket_str)

    # Simpan kembali sisa tracker
    if keys_to_remove:
        for k in keys_to_remove:
            del data[k]
        save_tracked_trades(data)
