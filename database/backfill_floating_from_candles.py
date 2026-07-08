import sys
import os
import json
from datetime import datetime, timezone

# Add root folder to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import get_supabase
import MetaTrader5 as mt5

def parse_iso(dt_str: str) -> datetime:
    if not dt_str:
        return None
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    return datetime.fromisoformat(dt_str)

def backfill_floating():
    if not mt5.initialize():
        print("MetaTrader5 initialization failed")
        return

    supabase = get_supabase()

    # Ambil trade yang mungkin belum punya snapshot (atau mau direkalkulasi)
    print("Mengambil data trade_analytics...")
    res = supabase.table("trade_analytics").select("*").execute()
    trades = res.data or []

    print(f"Ditemukan {len(trades)} trades.")

    total_ok = 0
    total_skip = 0

    for trade in trades:
        ticket = trade.get("ticket_id")
        symbol = trade.get("symbol")
        mode = trade.get("mode")
        op_price = trade.get("op_price")
        entry_time_str = trade.get("entry_time")
        exit_time_str = trade.get("exit_time")
        volume = trade.get("volume") or 0.0   # ← guard: NULL di DB jadi 0.0

        if not entry_time_str or not exit_time_str or not symbol or op_price is None:
            total_skip += 1
            continue

        if not volume or volume <= 0:
            print(f"  ⚠️ Ticket #{ticket}: volume kosong/0 di trade_analytics, skip (gak bisa hitung profit USD akurat).")
            total_skip += 1
            continue

        entry_time = parse_iso(entry_time_str)
        exit_time = parse_iso(exit_time_str)

        # Cek apakah sudah ada snapshot
        snap_res = supabase.table("trade_floating_snapshots").select("id").eq("ticket_id", ticket).limit(1).execute()
        if snap_res.data and len(snap_res.data) > 0:
            # Sudah ada snapshot, skip yang sudah ada
            total_skip += 1
            continue

        print(f"Processing fallback untuk ticket #{ticket} ({symbol})")

        # Ambil OHLC dari tabel candles di rentang waktu entry - exit
        candles_res = supabase.table("candles")\
            .select("timestamp, high_, low_, close_")\
            .eq("symbol", symbol)\
            .gte("timestamp", entry_time.isoformat())\
            .lte("timestamp", exit_time.isoformat())\
            .execute()

        candles = candles_res.data or []
        if not candles:
            print(f"  ⚠️ Tidak ada data candle antara {entry_time} dan {exit_time}")
            total_skip += 1
            continue

        # Cari worst price & best price
        worst_price = op_price
        worst_time = entry_time_str
        best_price = op_price
        best_time = entry_time_str
        
        for c in candles:
            c_high = float(c["high_"])
            c_low = float(c["low_"])
            c_time = c["timestamp"]
            
            if mode == "BUY":
                if c_low < worst_price:
                    worst_price = c_low
                    worst_time = c_time
                if c_high > best_price:
                    best_price = c_high
                    best_time = c_time
            else: # SELL
                if c_high > worst_price:
                    worst_price = c_high
                    worst_time = c_time
                if c_low < best_price:
                    best_price = c_low
                    best_time = c_time

        # Ambil symbol info dari MT5 untuk perhitungan profit
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            print(f"  ⚠️ Gagal mendapatkan symbol info untuk {symbol}")
            total_skip += 1
            continue

        point = symbol_info.point or 0.0
        tick_size = symbol_info.trade_tick_size or 0.0
        tick_value = symbol_info.trade_tick_value or 0.0
        digits = symbol_info.digits or 0

        if tick_size == 0 or tick_value == 0:
            print(f"  ⚠️ Ticket #{ticket}: tick_size/tick_value 0 dari MT5 utk {symbol}, skip.")
            total_skip += 1
            continue

        # Hitung worst floating (MAE)
        floating_pct = 0.0
        distance_price = abs(worst_price - op_price)
        current_profit = 0.0
        
        if op_price != 0:
            if mode == "BUY":
                floating_pct = (worst_price - op_price) / op_price * 100.0
                ticks = (worst_price - op_price) / tick_size if tick_size != 0 else 0
                current_profit = ticks * tick_value * volume
            else:
                floating_pct = (op_price - worst_price) / op_price * 100.0
                ticks = (op_price - worst_price) / tick_size if tick_size != 0 else 0
                current_profit = ticks * tick_value * volume
                
        # Hitung best floating (MFE)
        best_floating_pct = 0.0
        best_distance_price = abs(best_price - op_price)
        best_current_profit = 0.0
        
        if op_price != 0:
            if mode == "BUY":
                best_floating_pct = (best_price - op_price) / op_price * 100.0
                ticks = (best_price - op_price) / tick_size if tick_size != 0 else 0
                best_current_profit = ticks * tick_value * volume
            else:
                best_floating_pct = (op_price - best_price) / op_price * 100.0
                ticks = (op_price - best_price) / tick_size if tick_size != 0 else 0
                best_current_profit = ticks * tick_value * volume
                
        def make_payload(time_val, profit_val, pct_val, dist_val, curr_price_val):
            return {
                "ticket_id": ticket,
                "symbol": symbol,
                "timeframe": trade.get("timeframe", "M5"),
                "mode": mode,
                "trigger_type": trade.get("trigger_type", "Engulfing"),
                "tf_execute": trade.get("timeframe", "M5"),
                "tf_monitor": "M15",  # Default fallback
                "snapshot_time": time_val,
                "floating_profit_usd": profit_val,
                "floating_pct_from_entry": pct_val,
                "volume_lot": volume,
                "distance_price_units": dist_val,
                "trigger_tf_list": json.dumps([trade.get("timeframe", "M5")]),
                "entry_price": float(op_price),
                "current_price": float(curr_price_val),
                "sl_price": float(trade.get("sl_price") or 0.0),
                "tp_price": float(trade.get("tp_price") or 0.0),
                "phase": "BEFORE_PROFIT",
                "digits": int(digits),
                "point": float(point),
                "tick_size": float(tick_size),
                "tick_value": float(tick_value),
            }
            
        payloads = [make_payload(worst_time, current_profit, floating_pct, distance_price, worst_price)]
        if best_price != worst_price:
            payloads.append(make_payload(best_time, best_current_profit, best_floating_pct, best_distance_price, best_price))
            
        try:
            for p in payloads:
                supabase.table("trade_floating_snapshots").insert(p).execute()
            print(f"  ✅ Berhasil backfill MAE & MFE untuk #{ticket}")
            total_ok += 1
        except Exception as e:
            print(f"  ❌ Gagal insert untuk #{ticket}: {e}")
            total_skip += 1

    mt5.shutdown()
    print(f"\nBackfill selesai! Berhasil: {total_ok} | Dilewati: {total_skip}")

if __name__ == "__main__":
    backfill_floating()