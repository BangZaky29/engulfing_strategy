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
from strategies.strategy_rcs.trigger import skip_reasons as sr
from strategies.strategy_rcs.engine import place_op1_order, place_op2_order, place_op3_order
from strategies.strategy_rcs.rcs_order_manager import cancel_pending_order_rcs, close_position_by_ticket
from strategies.strategy_rcs.rcs_schedule import is_rcs_trading_active, get_rcs_trading_status_text
from strategies.strategy_rcs.rcs_daily_guard import check_rcs_daily_target, get_rcs_daily_guard_status_text
from strategies.strategy_rcs.freeze import enter_freeze, check_unfreeze, calculate_recovery, calculate_cycle_profit
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
        
    print(f"🚀 Memulai REVERSAL CANDLE SYSTEM (RCS) Bot...")
    print(f"🔹 Symbol       : {symbol}")
    print(f"🔹 Signal TF    : {rcs_cfg.signal_timeframe}")
    
    # Format OP1 Info
    op1_info = rcs_cfg.op1_entry_mode
    if rcs_cfg.op1_entry_mode == "PERCENT":
        op1_info += f" ({rcs_cfg.entry_percent}%)"
        
    print(f"🔹 OP1 Setup    : {op1_info} | Lot: {rcs_cfg.lot_size_op1} | TP: {rcs_cfg.tp_mode} ({rcs_cfg.tp_percent}%) | Mgc: {rcs_cfg.magic_op1}")
    print(f"🔹 OP2 Setup    : {rcs_cfg.op2_mode} ({rcs_cfg.op2_percent}%) | Lot: {rcs_cfg.lot_size_op2} | TP: {rcs_cfg.tp2_mode} ({rcs_cfg.tp2_percent}%) | Mgc: {rcs_cfg.magic_op2}")
    print(f"🔹 OP3 Setup    : {rcs_cfg.op3_mode} ({rcs_cfg.op3_percent}%) | Lot: OP1+OP2 | Mgc: {rcs_cfg.magic_op3}")
    print(f"🔹 Filters      : Range({rcs_cfg.min_trigger_range}-{rcs_cfg.max_trigger_range}) | Body({rcs_cfg.min_body_percent}-{rcs_cfg.max_body_percent}%) | EMA_Dist({rcs_cfg.min_ema_distance_pts}-{rcs_cfg.max_ema_distance_pts} pts)")
    print(f"⏰ Schedule     : {get_rcs_trading_status_text(rcs_cfg)}")
    print(f"🛡️ Daily Guard  : {get_rcs_daily_guard_status_text(rcs_cfg)}")
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
                # Format to remove seconds if it's a datetime object
                if hasattr(current_time, 'strftime'):
                    display_time = current_time.strftime("%Y.%m.%d %H:%M")
                else:
                    # if it's a string, just slice it if possible
                    display_time = str(current_time)[:16].replace('-', '.')
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
                                reason = sr.skip_not_engulfing_or_ict()
                                print(cprint(f"⏭️ SKIP Trigger {symbol} [{display_time}]: {reason}", Colors.GRAY))
                                continue
                                
                            # 2. Terapkan Filter
                            is_valid, skip_reason = apply_all_filters(candle_data, rcs_cfg, direction)
                            if not is_valid:
                                if rcs_cfg.notif_skip:
                                    print(cprint(f"⏭️ SKIP Trigger {symbol} [{display_time}] {pattern_name} {direction}: {skip_reason}", Colors.YELLOW))
                                    notify_skip(symbol, pattern_name, direction, skip_reason, rcs_cfg)
                                continue
                                
                            # 3. Valid! Hitung Level
                            # Risk range
                            c_close = candle_data["close_"]
                            c_high = candle_data["high_"]
                            c_low = candle_data["low_"]
                            c_open = candle_data["open_"]
                            spread = int(candle_data["spread"])
                            body_pct = candle_data["body_pct"]
                            ema = candle_data["ema_now"]
                            
                            risk_range = (c_close - c_low) if direction == "BUY" else (c_high - c_close)
                            levels = calculate_levels(c_close, risk_range, direction, rcs_cfg)
                            
                            dist_open_ema = int(round(abs(c_open - ema) / info.point)) if info.point > 0 else 0
                            risk_range_pts = int(round(risk_range / info.point)) if info.point > 0 else 0

                            print(cprint(f"🎯 VALID Trigger {symbol} {pattern_name} {direction}!", Colors.GREEN))
                            print(cprint(f"   ├── Jarak Open C1 - EMA 20 : {dist_open_ema} pts ({dist_open_ema/10:.1f} pips) [Syarat: {rcs_cfg.min_ema_distance_pts}-{rcs_cfg.max_ema_distance_pts} pts]", Colors.CYAN))
                            print(cprint(f"   ├── Risk Range C1           : {risk_range_pts} pts [Syarat: {rcs_cfg.min_trigger_range}-{rcs_cfg.max_trigger_range} pts]", Colors.CYAN))
                            print(cprint(f"   ├── Ketebalan Body C1       : {body_pct:.1f}% [Syarat: {rcs_cfg.min_body_percent}-{rcs_cfg.max_body_percent}%]", Colors.CYAN))
                            print(cprint(f"   ├── Spread Market           : {spread} pts [Syarat: <= {rcs_cfg.max_spread_points} pts]", Colors.CYAN))
                            print(cprint(f"   └── Konfirmasi Trend        : Close C1 ({c_close:.2f}) {'<' if direction == 'SELL' else '>'} EMA 20 ({ema:.2f})", Colors.CYAN))

                            # Set State ke OP1
                            state.phase = RCSPhase.OP1
                            state.trigger_direction = direction
                            state.trigger_risk_range = risk_range
                            if hasattr(candle_data["timestamp"], "timestamp"):
                                state.trigger_timestamp = int(candle_data["timestamp"].timestamp())
                            else:
                                state.trigger_timestamp = int(time.time())
                            state.op1_level = levels["op1_level"]
                            state.op2_level = levels["op2_level"]
                            state.op3_level = levels["op3_level"]
                            state.trigger_age = 0
                            
                            # Cek Jam Aktif Trading RCS (Scheduler)
                            if not is_rcs_trading_active(rcs_cfg):
                                print(cprint(f"⏸️ SKIP Execution: Di luar jam aktif trading RCS ({rcs_cfg.rcs_trading_active_start} - {rcs_cfg.rcs_trading_active_end} WIB)", Colors.YELLOW))
                                state.reset()
                                continue
                                
                            # Cek Daily Money Management Guard (Target Profit / Loss Harian)
                            daily_allowed, daily_reason = check_rcs_daily_target(rcs_cfg)
                            if not daily_allowed:
                                print(cprint(f"⏸️ SKIP Execution: {daily_reason}", Colors.YELLOW))
                                state.reset()
                                continue
                                
                            # Langsung tembak 3 Pending Order / Market Order!
                            current_price = tick.ask if direction == "BUY" else tick.bid
                            if place_op1_order(symbol, current_price, state, rcs_cfg):
                                place_op2_order(symbol, state, rcs_cfg)
                                place_op3_order(symbol, state, rcs_cfg)
                                
                                # Info ditaruh setelah place order agar TP dan SL sudah terhitung di state
                                print(f"   => OP1 Target: {state.op1_level:.5f} | TP: {state.tp1_price:.5f}")
                                print(f"   => OP2 Target: {state.op2_level:.5f} | TP: {state.tp2_price:.5f}")
                                print(f"   => OP3 Target: {state.op3_level:.5f} | Mode: {rcs_cfg.op3_mode}")
                                
                                if rcs_cfg.notif_trigger:
                                    notify_trigger(symbol, pattern_name, direction, state, rcs_cfg, candle_data=candle_data)
                                    
                                notify_open(symbol, "OP1", state.op1_ticket, state.op1_open_price, state.tp1_price, rcs_cfg)
                            else:
                                print(cprint("❌ Gagal memasang OP1. Reset state.", Colors.RED))
                                state.reset()
                            
                    elif state.phase == RCSPhase.OP1:
                        # Manage trigger age kalau pakai trigger lama
                        pass
                        
            # 3. Fast Tick Polling untuk Monitoring Pending Order & Posisi
            if state.phase == RCSPhase.OP1:
                if state.op1_ticket is not None:
                    # 0. Cek apakah OP1 lenyap dari peredaran (Posisi kosong DAN Order kosong)
                    pos1 = mt5.positions_get(ticket=state.op1_ticket)
                    ord1 = mt5.orders_get(ticket=state.op1_ticket)
                    
                    if not pos1 and not ord1:
                        print(cprint(f"👻 OP1 (Tkt:{state.op1_ticket}) hilang dari market (TP/SL Hit atau Cancel).", Colors.YELLOW))
                        print(cprint(f"🧹 Membersihkan sisa pending order OP2 dan OP3...", Colors.YELLOW))
                        if state.op2_ticket:
                            cancel_pending_order_rcs(state.op2_ticket)
                        if state.op3_ticket:
                            cancel_pending_order_rcs(state.op3_ticket)
                        
                        real_profit = calculate_cycle_profit(state)
                        notify_result(symbol, "Siklus Selesai (Posisi/Order Hilang)", real_profit, 0.0, rcs_cfg, state=state)
                        state.reset()
                        continue
                        
                    # 1. Cek transisi OP2 dari Order menjadi Position
                    if state.op2_ticket and not state.op2_notified:
                        pos2 = mt5.positions_get(ticket=state.op2_ticket)
                        ord2 = mt5.orders_get(ticket=state.op2_ticket)
                        
                        if pos2 and not ord2:
                            state.op2_notified = True
                            op2_open_price = pos2[0].price_open
                            
                            # OP2 baru saja tertrigger menjadi posisi!
                            if rcs_cfg.op2_mode == "HEDGE":
                                print(cprint(f"❄️ HEDGE (OP2) Terbuka di {op2_open_price:.5f}. Beralih ke PHASE_FREEZE.", Colors.CYAN))
                                state.phase = RCSPhase.FREEZE
                                state.freeze_is_hedge = True
                                enter_freeze(state, rcs_cfg)
                                notify_freeze(symbol, state.freeze_start_floating_usd, rcs_cfg)
                            else:
                                print(cprint(f"🎯 OP2 (Hedge Reentry Limit) tersentuh di {op2_open_price:.5f}! Posisi aktif. Target TP2: {state.tp2_price:.5f}", Colors.GREEN))
                                notify_open(symbol, "OP2 (Hedge Reentry)", state.op2_ticket, op2_open_price, state.tp2_price, rcs_cfg)
                                
                    # 1b. Cek jika OP2 pernah aktif (op2_notified == True) lalu OP2 menyentuh TP2 & ditutup oleh broker!
                    if state.op2_ticket and state.op2_notified and state.phase != RCSPhase.FREEZE:
                        pos2 = mt5.positions_get(ticket=state.op2_ticket)
                        if not pos2:
                            # OP2 posisi sudah hilang (tersentuh TP2)!
                            print(cprint(f"🎯 OP2 (Hedge Reentry) menyentuh TP2! Menutup sisa posisi OP1 (Tkt:{state.op1_ticket})...", Colors.GREEN))
                            
                            # Tutup OP1 aktif jika masih ada
                            if state.op1_ticket:
                                pos1_check = mt5.positions_get(ticket=state.op1_ticket)
                                if pos1_check:
                                    close_position_by_ticket(state.op1_ticket)
                                    print(cprint(f"✅ Posisi OP1 (Tkt:{state.op1_ticket}) berhasil ditutup otomatis.", Colors.GREEN))
                                    
                            # Batalkan sisa pending order (OP3 / SL)
                            print(cprint(f"🧹 Membersihkan sisa pending order OP3...", Colors.YELLOW))
                            if state.op3_ticket:
                                cancel_pending_order_rcs(state.op3_ticket)
                                
                            real_profit = calculate_cycle_profit(state)
                            notify_result(symbol, "Siklus Selesai (OP2 Menyentuh TP2)", real_profit, 0.0, rcs_cfg, state=state)
                            state.reset()
                            continue

                    # 2. Cek transisi OP3 dari Order menjadi Position
                    if state.op3_ticket and state.phase != RCSPhase.FREEZE:
                        pos3 = mt5.positions_get(ticket=state.op3_ticket)
                        ord3 = mt5.orders_get(ticket=state.op3_ticket)
                        if pos3 and not ord3:
                            print(cprint(f"❄️ HEDGE (OP3) Terbuka. Beralih ke PHASE_FREEZE.", Colors.CYAN))
                            state.phase = RCSPhase.FREEZE
                            state.freeze_is_hedge = True
                            enter_freeze(state, rcs_cfg)
                            notify_freeze(symbol, state.freeze_start_floating_usd, rcs_cfg)
                                # OP3 doesn't need else logic here since it's just a freeze trigger if it hits
                
            elif state.phase == RCSPhase.FREEZE:
                if check_unfreeze(symbol, state, rcs_cfg):
                    profit, recovery = calculate_recovery(symbol, state, rcs_cfg)
                    print(cprint(f"☀️ UNFREEZE! Posisi manual telah ditutup. Recovery: ${recovery:.2f}", Colors.GREEN))
                    notify_result(symbol, "Unfreeze Selesai", profit, recovery, rcs_cfg, state=state)
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
