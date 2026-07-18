# =====================================================
# mt5_client/trade_monitor/closed_trade_handler.py
# Orchestrator: check_closed_trades — loop utama monitor trade.
# Memanggil submodul floating_snapshot, hedge_manager,
# trigger_analytics, session_utils untuk concern masing-masing.
# =====================================================

import json
import os

import MetaTrader5 as mt5

from datetime import datetime, timezone

from database.supabase_storage import upload_screenshot
from database.supabase_client import get_supabase
from mt5_client.visualizer import generate_screenshot
from config.mt5_config import MT5Config, EMAConfig
from mt5_client.error_helper import get_last_error

from .tracker_store import (
    load_tracked_trades, save_tracked_trades,
    TEMP_DIR, BUCKET_NAME, _SS_TF_ENV, _SS_CANDLES,
)
from .session_utils import get_indonesian_date_str, resolve_trading_session
from .floating_snapshot import sample_floating_snapshot
from .hedge_manager import (
    cancel_hedge_if_op1_expired,
    check_hedge_touched,
    cancel_hedge_if_tp_hit,
)
from .trigger_analytics import build_and_upsert_trigger_analytics


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
        session_str = resolve_trading_session(ticket, info, data)
        
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
                    
                # --- SNAPSHOT INSTAN saat order baru fill (jangan tunggu poll berikutnya) ---
                try:
                    pos0 = positions[0]
                    entry_price0 = getattr(pos0, "price_open", None) or info.get("op_price")
                    current_price0 = getattr(pos0, "price_current", None) or entry_price0
                    current_profit0 = float(getattr(pos0, "profit", 0.0) or 0.0)
                    volume_lot0 = float(getattr(pos0, "volume", 0.0) or 0.0)
                    now_dt0 = datetime.now(timezone.utc)

                    floating_pct0 = 0.0
                    try:
                        if entry_price0 and float(entry_price0) != 0:
                            if info.get("mode") == "BUY":
                                floating_pct0 = (float(current_price0) - float(entry_price0)) / float(entry_price0) * 100.0
                            else:
                                floating_pct0 = (float(entry_price0) - float(current_price0)) / float(entry_price0) * 100.0
                    except:
                        floating_pct0 = 0.0

                    symbol_info0 = mt5.symbol_info(info["symbol"])  # type: ignore
                    sb_payload0 = {
                        "ticket_id": ticket,
                        "symbol": info["symbol"],
                        "timeframe": info["tf"],
                        "mode": info["mode"],
                        "trigger_type": info.get("trigger_type") or "Engulfing",
                        "tf_execute": info.get("tf", "M5"),
                        "tf_monitor": info.get("tf_monitor", "M15"),
                        "snapshot_time": now_dt0.isoformat(),
                        "floating_profit_usd": current_profit0,
                        "floating_pct_from_entry": floating_pct0,
                        "volume_lot": volume_lot0,
                        "distance_price_units": abs(float(current_price0) - float(entry_price0)) if current_price0 and entry_price0 else None,
                        "trigger_tf_list": json.dumps(info.get("tf_list", [info.get("tf", "M5")])),
                        "entry_price": float(entry_price0) if entry_price0 is not None else None,
                        "current_price": float(current_price0) if current_price0 is not None else None,
                        "sl_price": float(info.get("sl_price") or 0.0),
                        "tp_price": float(info.get("tp_price") or 0.0),
                        "phase": "BEFORE_PROFIT",
                        "digits": int(getattr(symbol_info0, 'digits', 0) or 0) if symbol_info0 else None,
                        "point": float(getattr(symbol_info0, 'point', 0.0) or 0.0) if symbol_info0 else None,
                        "tick_size": float(getattr(symbol_info0, 'trade_tick_size', 0.0) or 0.0) if symbol_info0 else None,
                        "tick_value": float(getattr(symbol_info0, 'trade_tick_value', 0.0) or 0.0) if symbol_info0 else None,
                    }
                    supabase.table("trade_floating_snapshots").insert(sb_payload0).execute()
                    info["latest_snapshot_time"] = now_dt0.isoformat()
                    save_tracked_trades(data)
                except Exception as ex:
                    print(f"⚠️ Gagal insert snapshot instan untuk #{ticket}: {ex}")
                # -------------------------------------------------------------------------

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
                    
                    # 1. Tentukan pesan dan file name
                    if h_order.state == mt5.ORDER_STATE_EXPIRED:
                        msg = f"⏳ PENDING ORDER EXPIRED! Batas waktu {expire_candles} candle terlewati tanpa tersentuh harga."
                    else:
                        msg = f"🧹 PENDING ORDER DIBATALKAN (OVERRIDE)! Dibatalkan karena ada trigger baru yang aktif atau manual cancel."
                        
                    # --- CANCEL OP-2 HEDGE JIKA OP-1 EXPIRED/CANCELED ---
                    msg = cancel_hedge_if_op1_expired(info, state_name, msg)
                        
                    # 2. Ambil screenshot chart pending order sebelum dihapus
                    public_url = None
                    try:
                        tf_const = mt5_cfg.get_mt5_timeframe(info['tf'])
                        rates = mt5.copy_rates_from_pos(info['symbol'], tf_const, 0, mt5_cfg.candle_count)  # type: ignore
                        if rates is not None and len(rates) > 0:
                            new_filename = f"{info['mode']}_{state_name}_{info['symbol']}_{info['tf']}_{ticket}.png"
                            new_path = os.path.join(TEMP_DIR, new_filename)
                            
                            img_path = generate_screenshot(
                                rates=rates,
                                ticket_id=ticket,
                                op_price=info['op_price'],
                                sl_price=info['sl_price'],
                                tp_price=info['tp_price'],
                                ema_cfg=ema_cfg,
                                mode=info['mode'],
                                entry_time=None,
                                entry_price=None,
                                exit_time=None,
                                exit_price=None,
                                tf_label=info['tf'],
                                output_dir=TEMP_DIR,
                                num_candles=30
                            )
                            
                            if img_path and os.path.exists(img_path):
                                os.rename(img_path, new_path)
                                folder_date = get_indonesian_date_str().replace('/', '-')
                                success, uploaded_url = upload_screenshot(new_path, "order_expired", folder_date, new_filename)
                                if success:
                                    public_url = uploaded_url
                                    try:
                                        os.remove(new_path)
                                    except:
                                        pass
                    except Exception as e:
                        print(f"⚠️ Gagal generate/upload SS untuk active log {ticket}: {e}")
                    
                    # 3. Kirim log pembatalan ke Supabase agar WA bot men-trigger notifikasi
                    try:
                        log_data = {
                            "ticket_id": ticket,
                            "symbol": info['symbol'],
                            "mode": info['mode'],
                            "message": msg,
                            "op_price": info['op_price'],
                            "sl_price": info['sl_price'],
                            "tp_price": info['tp_price'],
                            "trading_session": session_str,
                            "image_url": public_url
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
            
            # --- sampling floating snapshots saat trade ACTIVE ---
            sample_floating_snapshot(ticket, info, positions, data)

            # --- CEK HEDGING OP-2 TERSENTUH ---
            check_hedge_touched(ticket, info, data, session_str)

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

        # --- agregasi trigger analytics dari floating snapshots ---
        trigger_type = info.get("trigger_type") or "Engulfing"
        analytics = build_and_upsert_trigger_analytics(
            ticket, info, exit_time, total_profit, result_str, trigger_type
        )
        max_neg = analytics["max_neg"]
        max_neg_distance_points = analytics["max_neg_distance_points"]
        max_neg_distance_price_points = analytics["max_neg_distance_price_points"]

        # --- CANCEL HEDGE JIKA OP-1 KENA TP PROFIT ---
        cancel_hedge_if_tp_hit(ticket, info, result_str, session_str)
        
        # 3. Generate Screenshot Saat Ini
        # Gunakan SCREENSHOT_TIMEFRAME dari .env jika ada, fallback ke TF trade
        ss_tf_label = _SS_TF_ENV if _SS_TF_ENV else info['tf']
        time_suffix = info["timestamp"].split("_")[1]
        new_filename = f"{info['mode']}_{result_str}_{info['symbol']}_{ss_tf_label}_{time_suffix}.png"
        new_path = os.path.join(TEMP_DIR, new_filename)
        
        try:
            tf_const = mt5_cfg.get_mt5_timeframe(ss_tf_label)
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
                    tf_label=ss_tf_label,
                    output_dir=TEMP_DIR,
                    num_candles=_SS_CANDLES  # Configurable via SCREENSHOT_CANDLES di .env
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
                            
                            # --- ANALYTICS DATA FOR DASHBOARD ---
                            # Hitung persentase max floating (MAE) terhadap jarak SL
                            dist_to_sl = abs(float(info.get("op_price", 0)) - float(info.get("sl_price", 0)))
                            max_loss_to_sl_pct = 0
                            if dist_to_sl > 0 and max_neg_distance_price_points is not None:
                                max_loss_to_sl_pct = (max_neg_distance_price_points / dist_to_sl) * 100

                            notes_obj = {
                                "h1_trigger_source": info.get("h1_trigger_source", ""),
                                "m15_trigger_source": info.get("m15_trigger_source", ""),
                                "m5_trigger_source": info.get("m5_trigger_source", ""),
                                "op_level_pts": info.get("op_level_pts", 0),
                                "op_level_pct": info.get("op_level_pct", 0.0),
                                "max_floating_usd": -max_neg if max_neg else 0,
                                "max_floating_pts": max_neg_distance_points if max_neg_distance_points else 0,
                                "max_loss_to_sl_pct": -max_loss_to_sl_pct if max_loss_to_sl_pct else 0
                            }
                            
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
                                "entry_time": datetime.fromtimestamp(entry_time, tz=timezone.utc).isoformat() if entry_time else None,
                                "exit_time": datetime.fromtimestamp(exit_time, tz=timezone.utc).isoformat() if exit_time else None,
                                "image_url": public_url,
                                "trigger_type": trigger_type,
                                "trading_session": session_str,
                                "notes": json.dumps(notes_obj)
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
