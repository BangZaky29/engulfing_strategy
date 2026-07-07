import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config.mt5_config import MT5Config, EMAConfig
from config.execution_config import ExecutionConfig
from config.filter_c_config import FilterCConfig
from mt5_client import init_mt5, shutdown_mt5
from mt5_client.execution import execute_engulfing_order
from strategies.engulfing.filters_C import check_tf_monitor
import MetaTrader5 as mt5

def main():
    mt5_cfg = MT5Config()
    exec_cfg = ExecutionConfig()
    ema_cfg = EMAConfig()
    fc_cfg = FilterCConfig()
    
    if not init_mt5(mt5_cfg):
        print("Gagal init MT5")
        return

    symbol = "BTC" 
    
    # Ambil harga market saat ini supaya langsung eksekusi MARKET
    info = mt5.symbol_info(symbol)  # type: ignore
    if info is None:
        print(f"Gagal mendapat harga live untuk {symbol}")
        shutdown_mt5()
        return
    live_bid = info.bid
    
    # Matikan fixed money di test ini agar SL H1 tidak ditimpa

    print("Mengambil data live TF Monitor (H1, M15, M5) dari MT5...")
    tfm_result = check_tf_monitor(symbol, cfg=fc_cfg)
    print(f"Hasil TF Monitor: {tfm_result['snapshot']}")
    
    if not tfm_result.get("h1_trigger_candle"):
        print("❌ Tidak ada trigger H1 terdeteksi di MT5 saat ini. Tidak bisa test.")
        shutdown_mt5()
        return

    # Ambil data REAL candle H1 dari hasil TF Monitor
    h1_candle = tfm_result["h1_trigger_candle"]
    h1_trigger_high = h1_candle["high"]
    h1_trigger_close = h1_candle["close"]
    h1_trigger_low = h1_candle["low"]
    
    signal = {
        "symbol": symbol,
        "timeframe": "M5",
        "pattern_type": "bearish_engulfing", # Asumsi testing Sell
        "curr_open": live_bid + 10,
        "curr_high": live_bid + 20,
        "curr_low": live_bid - 20,
        "curr_close": live_bid, # Eksekusi di harga market
        "tfm_status": tfm_result["status"],
        "tfm_bias": tfm_result["bias_column"],
        "h1_trigger_open": h1_candle["open"],
        "h1_trigger_high": h1_trigger_high,
        "h1_trigger_low": h1_trigger_low,
        "h1_trigger_close": h1_trigger_close,
        "h1_trigger_source": tfm_result.get("h1_trigger_source", ""),
        "is_confirmed": True,
    }
    
    # --- LOGIC SL SAMA PERSIS SEPERTI DI DETECTOR.PY ---
    SL_H1_PCT = fc_cfg.sl_h1_pct
    op = signal["curr_close"]
    
    # KITA ANGGAP SELL
    range_ref = h1_trigger_high - h1_trigger_close
    new_sl = h1_trigger_high + (range_ref * SL_H1_PCT)
    sl_dist = abs(op - new_sl)
    new_tp = op - (sl_dist * 1.0) # rr_ratio = 1.0
    
    signal["op_price"] = op
    signal["sl_price"] = new_sl
    signal["tp_price"] = new_tp
    signal["rr_ratio"] = 1.0
    
    print("=========================================")
    print(f"Menguji Eksekusi Dinamis SL H1 (REAL DATA) -> {symbol}")
    print("=========================================")
    print(f"Harga OP (Live Bid) : {op}")
    print(f"Harga H1 High Asli  : {h1_trigger_high}")
    print(f"Harga H1 Close Asli : {h1_trigger_close}")
    print(f"Jarak Range H1 Asli : {range_ref}")
    print("-----------------------------------------")
    print(f"Dihitung SL (30%)   : {new_sl}")
    print(f"Dihitung TP (1:1)   : {new_tp}")
    print("=========================================")
    print("Mengeksekusi order ke MT5...")
    
    import mt5_client.execution
    ticket_id, skip_reason = mt5_client.execution.execute_engulfing_order(signal, mt5_cfg, exec_cfg, ema_cfg)
    
    if ticket_id:
        print(f"✅ SUKSES OP! Ticket ID: {ticket_id}")
    else:
        print(f"❌ Gagal OP. Alasan: {skip_reason}")
        
    shutdown_mt5()

if __name__ == '__main__':
    main()
