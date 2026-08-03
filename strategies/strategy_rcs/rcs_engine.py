# =====================================================
# strategies/strategy_rcs/rcs_engine.py
# Main Engine Loop for RCS (Reversal Candle System)
# =====================================================

import time
import datetime
import MetaTrader5 as mt5

from config.mt5_config import MT5Config, EMAConfig
from config.rcs_config import RCSConfig
from mt5_client import init_mt5, shutdown_mt5, get_closed_candles
from strategies.strategy_rcs.rcs_state import RCSState, RCSPhase
from strategies.strategy_rcs.trigger import detect_engulfing, detect_ict, apply_all_filters, calculate_levels
from strategies.strategy_rcs.engine import try_execute_op1, check_tp, check_op2, check_op3, check_sl
from strategies.strategy_rcs.freeze import enter_freeze, check_unfreeze, calculate_recovery
from strategies.strategy_rcs.rcs_notifier import notify_trigger, notify_skip, notify_open, notify_freeze, notify_result
from utils.colors import cprint, Colors

def run_rcs_bot():
    rcs_cfg = RCSConfig()
    
    if not rcs_cfg.enabled:
        print("❌ Reversal Candle System (RCS) dinonaktifkan di .env (RCS_ENABLED=false)")
        return
        
    mt5_cfg = MT5Config()
    if not init_mt5(mt5_cfg):
        return
        
    symbol = rcs_cfg.symbol
    if not mt5.symbol_select(symbol, True):
        print(f"❌ Gagal select symbol {symbol}")
        shutdown_mt5()
        return
        
    print(f"\n🚀 Memulai REVERSAL CANDLE SYSTEM (RCS) Bot...")
    print(f"🔹 Symbol       : {symbol}")
    print(f"🔹 Signal TF    : {rcs_cfg.signal_timeframe}")
    print(f"🔹 Magic OP1    : {rcs_cfg.magic_op1}")
    print(f"🔹 OP1 Entry    : {rcs_cfg.op1_entry_mode} ({rcs_cfg.entry_percent}%)")
    print(f"🔹 OP2 Mode     : {rcs_cfg.op2_mode} ({rcs_cfg.op2_percent}%)")
    print("==================================================")
    
    state = RCSState()
    last_candle_time = None
    
    try:
        while True:
            # 1. Info dari MT5
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if info is None or tick is None:
                time.sleep(1)
                continue
                
            # 2. Polling Timeframe untuk trigger detection (setiap ada candle baru)
            # Fetch TF M5 (atau timeframe RCS_SIGNAL_TIMEFRAME)
            candle_data = get_closed_candles(symbol, mt5_cfg, EMAConfig(), tf_label=rcs_cfg.signal_timeframe, verbose=False)
            if candle_data:
                current_time = candle_data["timestamp"]
                if last_candle_time is None or current_time != last_candle_time:
                    # New candle detected!
                    last_candle_time = current_time
                    
                    if state.phase == RCSPhase.IDLE:
                        if state.cooldown_until_candle > 0:
                            state.cooldown_until_candle -= 1
                            if state.cooldown_until_candle > 0:
                                print(cprint(f"⏳ Sedang Cooldown... Sisa {state.cooldown_until_candle} candle", Colors.GRAY))
                            else:
                                print(cprint(f"✅ Cooldown selesai. Mencari trigger baru...", Colors.GREEN))
                        
                        if state.cooldown_until_candle == 0:
                            # 1. Cek Pattern (Engulfing / ICT)
                            direction = None
                            pattern_name = ""
                            
                            # Coba Engulfing
                            if rcs_cfg.use_engulfing:
                                dir_eng = detect_engulfing(candle_data, info.point)
                                if dir_eng:
                                    direction = dir_eng
                                    pattern_name = "Engulfing"
                                    
                            # Coba ICT (jika belum ketemu atau untuk 'Multi' trigger)
                            if rcs_cfg.use_ict:
                                dir_ict = detect_ict(symbol, rcs_cfg.signal_timeframe, mt5_cfg, rcs_cfg.ict_sweep_lookback, info.point)
                                if dir_ict:
                                    if direction and direction == dir_ict:
                                        pattern_name = "Multi (Engulfing+ICT)"
                                    else:
                                        direction = dir_ict
                                        pattern_name = "ICT"
                                        
                            if direction is None:
                                # Jika config log ON, bisa print(skip_not_engulfing_or_ict)
                                continue
                                
                            # 2. Terapkan Filter
                            is_valid, skip_reason = apply_all_filters(candle_data, rcs_cfg, direction)
                            if not is_valid:
                                if rcs_cfg.notif_skip:
                                    print(cprint(f"⏭️ SKIP Trigger {symbol} {pattern_name} {direction}: {skip_reason}", Colors.YELLOW))
                                    notify_skip(symbol, pattern_name, direction, skip_reason, rcs_cfg)
                                continue
                                
                            # 3. Valid! Hitung Level
                            print(cprint(f"🎯 VALID Trigger {symbol} {pattern_name} {direction}!", Colors.GREEN))
                            
                            # Risk range
                            c_close = candle_data["close_"]
                            c_high = candle_data["high_"]
                            c_low = candle_data["low_"]
                            
                            risk_range = (c_close - c_low) if direction == "BUY" else (c_high - c_close)
                            
                            levels = calculate_levels(c_close, risk_range, direction, rcs_cfg)
                            
                            # Set State ke OP1
                            state.phase = RCSPhase.OP1
                            state.trigger_direction = direction
                            state.trigger_risk_range = risk_range
                            state.op1_level = levels["op1_level"]
                            state.op2_level = levels["op2_level"]
                            state.op3_level = levels["op3_level"]
                            state.trigger_age = 0
                            
                            print(f"   => OP1 Target: {state.op1_level:.5f}")
                            print(f"   => OP2 Target: {state.op2_level:.5f}")
                            print(f"   => OP3 Target: {state.op3_level:.5f}")
                            
                            if rcs_cfg.notif_trigger:
                                notify_trigger(symbol, pattern_name, direction, state, rcs_cfg)
                            
                    elif state.phase == RCSPhase.OP1:
                        # Manage trigger age kalau pakai trigger lama
                        pass
                        
            # 3. Fast Tick Polling untuk Eksekusi dan Monitoring
            if state.phase == RCSPhase.OP1:
                # Jika belum ada OP1, coba eksekusi OP1
                if state.op1_ticket is None:
                    if try_execute_op1(symbol, tick, info, state, rcs_cfg):
                        notify_open(symbol, "OP1", state.op1_ticket, state.op1_open_price, state.tp1_price, rcs_cfg)
                
                # Jika OP1 sudah ada, pantau TP, SL, dan OP2/OP3
                if state.op1_ticket is not None:
                    # 0. Cek perubahan phase karena intervensi luar (Vanished position)
                    pos1 = mt5.positions_get(ticket=state.op1_ticket)
                    if not pos1:
                        print(cprint(f"👻 Posisi OP1 hilang dari market. Reset state.", Colors.YELLOW))
                        notify_result(symbol, "Posisi tertutup (SL/Manual)", 0.0, 0.0, rcs_cfg)
                        state.reset()
                        continue

                    # 1. Cek Stop Loss terlebih dahulu
                    if check_sl(symbol, tick, state, rcs_cfg):
                        continue
                        
                    # 2. Cek Take Profit
                    if check_tp(symbol, tick, state, rcs_cfg):
                        notify_result(symbol, "Take Profit Hit", 0.0, 0.0, rcs_cfg)
                        state.reset()
                        continue
                        
                    # 3. Cek OP2
                    was_frozen_by_op2 = False
                    if check_op2(symbol, tick, info, state, rcs_cfg):
                        if state.phase == RCSPhase.FREEZE:
                            enter_freeze(state, rcs_cfg)
                            notify_freeze(symbol, state.freeze_start_floating_usd, rcs_cfg)
                            was_frozen_by_op2 = True
                        else:
                            notify_open(symbol, "OP2 (Hedge Reentry)", state.op2_ticket, state.tp2_price, state.tp2_price, rcs_cfg)
                        
                    if was_frozen_by_op2:
                        continue
                        
                    # 4. Cek OP3 (hanya jika OP2 sudah ada dan kita belum freeze)
                    if state.op2_ticket is not None and state.phase != RCSPhase.FREEZE:
                        if check_op3(symbol, tick, info, state, rcs_cfg):
                            if state.phase == RCSPhase.FREEZE:
                                enter_freeze(state, rcs_cfg)
                                notify_freeze(symbol, state.freeze_start_floating_usd, rcs_cfg)
                
            elif state.phase == RCSPhase.FREEZE:
                if check_unfreeze(symbol, state, rcs_cfg):
                    profit, recovery = calculate_recovery(symbol, state, rcs_cfg)
                    print(cprint(f"☀️ UNFREEZE! Posisi manual telah ditutup. Recovery: ${recovery:.2f}", Colors.GREEN))
                    notify_result(symbol, "Unfreeze Selesai", profit, recovery, rcs_cfg)
                    state.reset()
                
            time.sleep(0.5) # Fast loop tapi jangan spam CPU
            
    except KeyboardInterrupt:
        print("\n⏹️ RCS Bot dimatikan oleh user (Ctrl+C).")
    except Exception as e:
        print(f"\n❌ Error di RCS Bot: {e}")
        import traceback
        traceback.print_exc()
    finally:
        shutdown_mt5()
