# =====================================================
# strategies/strategy_rcs/rcs_engine.py
# Main Engine Loop for RCS (Reversal Candle System)
# Terintegrasi dengan PositionTracker untuk membedakan OP Sistem vs Manual
# =====================================================

import time
import datetime
import MetaTrader5 as mt5

from config.mt5_config import MT5Config, EMAConfig
from config.rcs_config import RCSConfig
from mt5_client import init_mt5, shutdown_mt5, get_closed_candles
from mt5_client.position_tracker import (
    PositionTracker,
    log_manual_open,
    log_manual_close,
    log_system_paused,
    notify_manual_position_detected,
    notify_manual_position_closed,
    notify_all_manual_cleared,
    notify_system_paused_due_manual,
)
from strategies.strategy_rcs.rcs_state import RCSState, RCSPhase
from strategies.strategy_rcs.trigger import detect_engulfing, detect_ict, apply_all_filters, calculate_levels
from strategies.strategy_rcs.trigger import skip_reasons as sr
from strategies.strategy_rcs.engine import place_op1_order, place_op2_order, place_op3_order
from strategies.strategy_rcs.rcs_order_manager import cancel_pending_order_rcs, close_position_by_ticket, remove_tp_from_position
from strategies.strategy_rcs.rcs_schedule import is_rcs_trading_active, get_rcs_trading_status_text
from strategies.strategy_rcs.rcs_daily_guard import check_rcs_daily_target, get_rcs_daily_guard_status_text
from strategies.strategy_rcs.freeze import enter_freeze, check_unfreeze, calculate_recovery, calculate_cycle_profit
from strategies.strategy_rcs.rcs_notifier import (
    notify_trigger,
    notify_skip,
    notify_open,
    notify_freeze,
    notify_result,
    notify_system_status,
    notify_company_target_reached_rcs,
    notify_startup_hanging_positions,
    notify_startup_clean_positions,
)
from config.company_daily_guard import (
    check_company_daily_target,
    get_company_guard_status_text,
    should_send_company_notif,
)
from utils.colors import cprint, Colors

from strategies.strategy_rcs.rcs_core import RCSEngine

def perform_startup_position_audit(symbols: list, rcs_configs: dict, states: dict, tracker: PositionTracker):
    """
    Melakukan audit posisi awal saat bot pertama kali di-running.
    Mendeteksi apakah ada OP Manual atau OP Sistem tertinggal dari sesi sebelumnya.
    Jika ada: Infokan ke RCS_GROUP_JID (GRUP COPET SKIPPED) dan pause pair tersebut.
    Jika bersih (0 OP): Infokan ke terminal & RCS_GROUP_JID bahwa siklus berjalan NORMAL.
    """
    clean_symbols = []

    for symbol in symbols:
        rcs_cfg = rcs_configs[symbol]
        state = states[symbol]

        snapshot = tracker.poll_positions(symbol)
        if snapshot.total_count == 0:
            clean_symbols.append(symbol)
            print(cprint(f"✅ [{symbol}] AUDIT STARTUP: Tidak ada OP manual atau sistem tertinggal. Siklus trading dijalankan NORMAL.", Colors.GREEN))
            continue

        # Ada posisi tertinggal!
        print(cprint(f"\n⚠️ [{symbol}] AUDIT STARTUP: Ditemukan {snapshot.total_count} posisi tertinggal di broker MT5!", Colors.YELLOW))
        print(cprint(f"   • Manual: {snapshot.manual_count} posisi | Sistem: {snapshot.system_count} posisi | Floating: ${snapshot.total_floating:.2f}", Colors.YELLOW))
        
        # Load context indicator yang tersimpan (jika ada) sebelum bot mati
        state.load_from_file(symbol)

        # Cek apakah tiket sistem cocok dengan magic RCS
        for pos in snapshot.system_positions:
            if pos.magic_number == rcs_cfg.magic_op1:
                state.op1_ticket = pos.ticket
                state.op1_open_price = pos.open_price
                if state.phase == RCSPhase.IDLE:
                    state.phase = RCSPhase.OP1
            elif pos.magic_number == rcs_cfg.magic_op2:
                state.op2_ticket = pos.ticket
                state.op2_notified = True
                if rcs_cfg.op2_mode == "HEDGE":
                    state.phase = RCSPhase.FREEZE
                    state.freeze_is_hedge = True
            elif pos.magic_number == rcs_cfg.magic_op3:
                state.op3_ticket = pos.ticket
                state.phase = RCSPhase.FREEZE
                state.freeze_is_hedge = True

        state.manual_positions_count = snapshot.manual_count
        state.manual_positions_profit = snapshot.total_manual_floating
        state.is_paused_by_manual = True

        # Kirim notifikasi WA ke RCS_GROUP_JID (GRUP COPET SKIPPED)
        try:
            notify_startup_hanging_positions(symbol, snapshot, rcs_cfg)
        except Exception as e:
            print(f"⚠️ Gagal kirim notifikasi startup hanging positions ({symbol}): {e}")

    # Kirim notifikasi audit clean ke RCS_GROUP_JID jika ada symbol yang 0 posisi tertinggal
    if clean_symbols:
        try:
            first_cfg = rcs_configs[clean_symbols[0]]
            notify_startup_clean_positions(clean_symbols, first_cfg)
        except Exception as e:
            print(f"⚠️ Gagal kirim notifikasi startup clean positions: {e}")

def run_rcs_bot():
    rcs_global_cfg = RCSConfig()
    
    if not rcs_global_cfg.enabled:
        print("❌ Reversal Candle System (RCS) dinonaktifkan di .env (RCS_ENABLED=false)")
        return
        
    mt5_cfg = MT5Config()
    if not init_mt5(mt5_cfg):
        return
        
    symbols = rcs_global_cfg.symbols
    if not symbols:
        print("❌ RCS_SYMBOL kosong di .env")
        shutdown_mt5()
        return

    rcs_configs = {sym: RCSConfig.from_env(sym) for sym in symbols}

    for sym in symbols:
        if not mt5.symbol_select(sym, True):
            print(f"❌ Gagal select symbol {sym}")
        
    tracker = PositionTracker()
    engine = RCSEngine(symbols, rcs_configs, tracker)

    def _on_manual_open(sym: str, positions: list, total_count: int = 0):
        is_frz = (engine.get_state(sym).phase == RCSPhase.FREEZE)
        notify_manual_position_detected(sym, positions, total_count=total_count, is_freeze=is_frz)
        log_manual_open(sym, positions)

    def _on_manual_close(sym: str, closed_positions: list):
        rem = tracker.get_manual_count(sym)
        notify_manual_position_closed(sym, closed_positions, remaining=rem)
        log_manual_close(sym, closed_positions)

    def _on_all_manual_cleared(sym: str):
        notify_all_manual_cleared(sym)

    tracker.on_manual_open(_on_manual_open)
    tracker.on_manual_close(_on_manual_close)
    tracker.on_all_manual_cleared(_on_all_manual_cleared)

    print(f"🚀 Memulai REVERSAL CANDLE SYSTEM (RCS) Bot (OOP Mode)...")
    print(f"🔹 Symbols      : {', '.join(symbols)}")
    print(f"🔹 Known Magics : {tracker.get_known_magics_text()}")
    print("==================================================")
    
    for sym in symbols:
        c = rcs_configs[sym]
        op1_info = c.op1_entry_mode
        if c.op1_entry_mode == "PERCENT":
            op1_info += f" ({c.entry_percent}%)"
            
        print(f"[{sym}] Configuration:")
        print(f"🔹 Signal TF    : {c.signal_timeframe}")
        print(f"🔹 OP1 Setup    : {op1_info} | Lot: {c.lot_size_op1} | TP: {c.tp_mode} ({c.tp_percent}%) | Mgc: {c.magic_op1}")
        print(f"🔹 OP2 Setup    : {c.op2_mode} ({c.op2_percent}%) | Lot: {c.lot_size_op2} | TP: {c.tp2_mode} ({c.tp2_percent}%) | Mgc: {c.magic_op2}")
        print(f"🔹 OP3 Setup    : {c.op3_mode} ({c.op3_percent}%) | Lot: OP1+OP2 | Mgc: {c.magic_op3}")
        print(f"🔹 Filters      : Range({c.min_trigger_range}-{c.max_trigger_range}) | Body({c.min_body_percent}-{c.max_body_percent}%) | EMA_Dist({c.min_ema_distance_pts}-{c.max_ema_distance_pts} pts)")
        print(f"⏰ Schedule     : {get_rcs_trading_status_text(c)}")
        print(f"🛡️ Daily Guard  : {get_rcs_daily_guard_status_text(c)}")
        print(f"🏂 Company Guard: {get_company_guard_status_text()}")
        print("--------------------------------------------------")
    
    notify_system_status('START', rcs_configs)
    perform_startup_position_audit(symbols, rcs_configs, engine.states, tracker)
    
    try:
        while True:
            for symbol in symbols:
                try:
                    engine.process_tick(symbol)
                except Exception as sym_err:
                    print(cprint(f"❌ Exception terisolasi pada symbol {symbol}: {sym_err}", Colors.RED))
                    import traceback
                    traceback.print_exc()

            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n⏹️ RCS Bot dimatikan oleh user (Ctrl+C).")
    except Exception as e:
        print(f"\n❌ Error di RCS Bot: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'rcs_configs' in locals():
            notify_system_status('STOP', rcs_configs)
        shutdown_mt5()
