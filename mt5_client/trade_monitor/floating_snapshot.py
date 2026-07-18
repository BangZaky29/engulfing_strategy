# =====================================================
# mt5_client/trade_monitor/floating_snapshot.py
# Sampling floating PnL snapshots ke Supabase saat trade ACTIVE.
# =====================================================

import json
from datetime import datetime, timezone

import MetaTrader5 as mt5

from database.supabase_client import get_supabase
from .tracker_store import save_tracked_trades


def sample_floating_snapshot(ticket: int, info: dict, positions, data: dict) -> None:
    """Mengambil snapshot floating profit untuk order yang aktif dan menyimpannya ke database Supabase."""
    # --- sampling floating snapshots saat trade ACTIVE ---
    # ambil snapshot tidak terlalu sering: minimal setiap 10 detik
    try:
        if positions is not None and len(positions) > 0:
            pos = positions[0]
            now_dt = datetime.now(timezone.utc)
            last_snap_str = info.get("latest_snapshot_time")
            last_snap = None
            if last_snap_str:
                try:
                    last_snap = datetime.fromisoformat(last_snap_str)
                    if last_snap.tzinfo is None:
                        last_snap = last_snap.replace(tzinfo=timezone.utc)
                except:
                    last_snap = None

            min_interval_sec = 3
            should_snap = True
            if last_snap:
                should_snap = (now_dt - last_snap).total_seconds() >= min_interval_sec

            if should_snap:
                entry_price = getattr(pos, "price_open", None) or getattr(pos, "price", None) or info.get("op_price")
                sl_price = info.get("sl_price", 0.0)
                current_profit = float(getattr(pos, "profit", 0.0) or 0.0)
                current_price = getattr(pos, "price_current", None) or getattr(pos, "price", None) or None

                # lot size sangat penting untuk konversi USD <-> points/pips per symbol
                volume_lot = float(getattr(pos, "volume", 0.0) or 0.0)

                # risk-normalized floating pct (berdasarkan entry dan jarak entry->sl)
                # BUY: adverse saat current < entry
                # SELL: adverse saat current > entry
                # SESUDAH (persen pergerakan dari OP price):
                floating_pct = None
                try:
                    if entry_price is not None and float(entry_price) != 0 and current_price is not None:
                        if info.get("mode") == "BUY":
                            floating_pct = (float(current_price) - float(entry_price)) / float(entry_price) * 100.0
                        else:
                            floating_pct = (float(entry_price) - float(current_price)) / float(entry_price) * 100.0
                except:
                    floating_pct = None

                if floating_pct is None:
                    # fallback: gunakan 0 agar tidak crash
                    floating_pct = 0.0

                # Tentukan tf_execute dan tf_monitor dari tracker info
                snap_tf_execute = info.get("tf", "M5")
                snap_tf_monitor = info.get("tf_monitor", "M15")

                # insert ke Supabase
                try:
                    supabase = get_supabase()
                    trigger_type = info.get("trigger_type") or "Engulfing"

                    symbol_info = mt5.symbol_info(info["symbol"])  # type: ignore

                    sb_payload = {
                        "ticket_id": ticket,
                        "symbol": info["symbol"],
                        "timeframe": info["tf"],
                        "mode": info["mode"],
                        "trigger_type": trigger_type,
                        "tf_execute": snap_tf_execute,
                        "tf_monitor": snap_tf_monitor,
                        "snapshot_time": now_dt.isoformat(),
                        "floating_profit_usd": current_profit,
                        "floating_pct_from_entry": floating_pct,
                        "volume_lot": volume_lot,
                        "distance_price_units": abs(float(current_price) - float(entry_price)) if current_price and entry_price else None,
                        "trigger_tf_list": json.dumps(info.get("tf_list", [info.get("tf", "M5")])),

                        "entry_price": float(entry_price) if entry_price is not None else None,
                        "current_price": float(current_price) if current_price is not None else None,
                        "sl_price": float(sl_price) if sl_price is not None else None,
                        "tp_price": float(info.get("tp_price") or 0.0),
                        "phase": "BEFORE_PROFIT",

                        # spec symbol untuk konversi distance harga -> points/pip
                        "digits": int(getattr(symbol_info, 'digits', 0) or 0) if symbol_info else None,
                        "point": float(getattr(symbol_info, 'point', 0.0) or 0.0) if symbol_info else None,
                        "tick_size": float(getattr(symbol_info, 'trade_tick_size', 0.0) or 0.0) if symbol_info else None,
                        "tick_value": float(getattr(symbol_info, 'trade_tick_value', 0.0) or 0.0) if symbol_info else None,
                        
                    }

                    supabase.table("trade_floating_snapshots").insert(sb_payload).execute()
                    info["latest_snapshot_time"] = now_dt.isoformat()
                    if not info.get("entry_time"):
                        try:
                            entry_time_ts = getattr(pos, "time", None)
                            if entry_time_ts:
                                # time biasanya berupa epoch seconds
                                info["entry_time"] = datetime.fromtimestamp(entry_time_ts, tz=timezone.utc).isoformat()
                        except:
                            pass
                    save_tracked_trades(data)
                except Exception as ex:
                    print(f"⚠️ Gagal insert floating snapshot untuk #{ticket}: {ex}")
    except Exception as ex:
        # sampling jangan pernah block trade_monitor loop
        print(f"⚠️ Gagal sampling floating snapshot untuk #{ticket}: {ex}")
