# =====================================================
# strategies/strategy_rcs/rcs_core.py
# Object-Oriented Engine for RCS (Reversal Candle System)
# =====================================================

import time
import datetime
import traceback
import MetaTrader5 as mt5

from typing import Dict, List, Any, Optional

from config.mt5_config import MT5Config, EMAConfig
from config.rcs_config import RCSConfig
from mt5_client import init_mt5, shutdown_mt5, get_closed_candles
from mt5_client.position_tracker import PositionTracker, notify_system_paused_due_manual
from strategies.strategy_rcs.rcs_state import RCSState, RCSPhase

# -- Imports from existing modules --
from strategies.strategy_rcs.trigger import detect_engulfing, detect_ict, apply_all_filters, calculate_levels
from strategies.strategy_rcs.engine import place_op1_order, place_op2_order, place_op3_order
from strategies.strategy_rcs.rcs_order_manager import cancel_pending_order_rcs, close_position_by_ticket, remove_tp_from_position
from strategies.strategy_rcs.rcs_schedule import is_rcs_trading_active
from strategies.strategy_rcs.rcs_daily_guard import check_rcs_daily_target
from strategies.strategy_rcs.freeze import enter_freeze, check_unfreeze, calculate_recovery, calculate_cycle_profit
from config.company_daily_guard import check_company_daily_target, should_send_company_notif

# -- Notifiers --
from strategies.strategy_rcs.rcs_notifier import (
    notify_trigger, notify_skip, notify_open, notify_freeze, 
    notify_result, notify_system_status, notify_company_target_reached_rcs
)

# -- Sniper Recovery --
from strategies.strategy_rcs.sniper_trigger_reader import (
    read_sniper_trigger,
    mark_sniper_consumed,
    get_sniper_trigger_age_seconds,
)
from config.sniper_config import SniperConfig

from utils.colors import cprint, Colors


class RCSEngine:
    """
    State Machine Engine untuk Reversal Candle System (RCS).
    Menangani siklus tick, deteksi pola, dan manajemen order per symbol.
    """
    
    def __init__(self, symbols: List[str], rcs_configs: Dict[str, RCSConfig], tracker: PositionTracker) -> None:
        self.symbols: List[str] = symbols
        self.rcs_configs: Dict[str, RCSConfig] = rcs_configs
        self.tracker: PositionTracker = tracker
        self.mt5_cfg: MT5Config = MT5Config()
        
        # State machine per symbol
        self.states: Dict[str, RCSState] = {sym: RCSState() for sym in symbols}
        self.last_candle_times: Dict[str, Any] = {sym: None for sym in symbols}
        
    def get_state(self, symbol: str) -> RCSState:
        return self.states[symbol]
        
    def process_tick(self, symbol: str) -> None:
        """Dipanggil setiap loop tick untuk memproses logic per symbol."""
        state = self.states[symbol]
        rcs_cfg = self.rcs_configs[symbol]
        
        # 0. Poll Position Tracker (Interval 0.5s via main loop)
        snapshot = self.tracker.poll_positions(symbol)
        state.manual_positions_count = snapshot.manual_count
        state.manual_positions_profit = snapshot.total_manual_floating

        has_manual = self.tracker.has_manual_positions(symbol)
        has_hanging = (snapshot.total_count > 0)
        state.is_paused_by_manual = has_hanging

        # 1. Info dari MT5
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        
        if info is None or tick is None:
            now_t = time.time()
            if now_t - getattr(state, '_last_symbol_err_time', 0) > 30:
                state._last_symbol_err_time = now_t
                print(cprint(f"⚠️ [{symbol}] Gagal mendapatkan info/tick dari MT5.", Colors.RED))
            return

        # Cek jika ada OP Tergantung (Manual / System Orphan) saat IDLE: Tampilkan warning & block trigger baru
        if has_hanging and state.phase == RCSPhase.IDLE:
            notify_system_paused_due_manual(symbol, snapshot.total_count, snapshot.total_floating)
            return

        # 2. Polling Timeframe untuk trigger detection (setiap ada candle baru)
        candle_data = get_closed_candles(symbol, self.mt5_cfg, EMAConfig(), tf_label=rcs_cfg.signal_timeframe, verbose=False)
        if candle_data:
            current_time = candle_data["timestamp"]
            
            if self.last_candle_times[symbol] is None or current_time != self.last_candle_times[symbol]:
                self.last_candle_times[symbol] = current_time
                if state.phase == RCSPhase.IDLE:
                    self._handle_idle_phase(symbol, state, rcs_cfg, candle_data, current_time, info, tick, has_manual)
        
        # 3. Fast Tick Polling untuk Monitoring Pending Order & Posisi
        if state.phase == RCSPhase.OP1:
            self._handle_op1_phase(symbol, state, rcs_cfg)
        elif state.phase == RCSPhase.FREEZE:
            self._handle_freeze_phase(symbol, state, rcs_cfg)

    def _handle_idle_phase(self, symbol: str, state: RCSState, rcs_cfg: RCSConfig, candle_data: dict, current_time: Any, info: Any, tick: Any, has_manual: bool) -> None:
        if hasattr(current_time, 'strftime'):
            display_time = current_time.strftime("%Y.%m.%d %H:%M")
        else:
            display_time = str(current_time)[:16].replace('-', '.')

        if state.cooldown_until_candle > 0:
            state.cooldown_until_candle -= 1
            if state.cooldown_until_candle > 0:
                print(cprint(f"⏳ [{symbol}] Sedang Cooldown... Sisa {state.cooldown_until_candle} candle", Colors.GRAY))
                return
            else:
                print(cprint(f"✅ [{symbol}] Cooldown selesai. Mencari trigger baru...", Colors.GREEN))
        
        if has_manual:
            return

        # --- Cek Guards ---
        rcs_schedule_ok = is_rcs_trading_active(rcs_cfg)
        company_allowed, company_reason = check_company_daily_target()
        if not company_allowed and company_reason:
            if should_send_company_notif():
                print(cprint(f"\n🏁 [COMPANY TARGET] {company_reason}", Colors.MAGENTA))
                notify_company_target_reached_rcs(company_reason)

        rcs_allowed, rcs_reason = check_rcs_daily_target(rcs_cfg)
        if not rcs_allowed and rcs_reason:
            print(cprint(f"   🛡️ [COPET Guard] {rcs_reason}", Colors.YELLOW))

        execute_allowed = rcs_schedule_ok and company_allowed and rcs_allowed
        if not execute_allowed:
            if not rcs_schedule_ok:
                if getattr(state, '_last_sched_pause_time', None) != current_time:
                    state._last_sched_pause_time = current_time
                    print(cprint(f"⏸️ [{symbol}] Di luar jam kerja Copet ({rcs_cfg.rcs_trading_active_start}→{rcs_cfg.rcs_trading_active_end} WIB) - Sistem TIDAK AKAN melakukan eksekusi OP.", Colors.GRAY))
            return

        # --- Deteksi Pola ---
        direction = None
        pattern_name = ""
        
        if rcs_cfg.use_engulfing:
            dir_eng = detect_engulfing(candle_data, info.point)
            if dir_eng:
                direction, pattern_name = dir_eng, "Engulfing"
                
        if rcs_cfg.use_ict:
            dir_ict = detect_ict(symbol, rcs_cfg.signal_timeframe, self.mt5_cfg, rcs_cfg.ict_sweep_lookback, info.point)
            if dir_ict:
                if direction and direction == dir_ict:
                    pattern_name = "Multi (Engulfing+ICT)"
                else:
                    direction, pattern_name = dir_ict, "ICT"
                    
        if not direction:
            return
            
        # --- Filters & Execution ---
        is_valid, skip_reason = apply_all_filters(candle_data, rcs_cfg, direction)
        if not is_valid:
            if rcs_cfg.notif_skip:
                print(cprint(f"⏭️ SKIP Trigger {symbol} [{display_time}] {pattern_name} {direction}: {skip_reason}", Colors.YELLOW))
                notify_skip(symbol, pattern_name, direction, skip_reason, rcs_cfg)
            return

        self._execute_trigger(symbol, state, rcs_cfg, candle_data, direction, pattern_name, info, tick)

    def _execute_trigger(self, symbol: str, state: RCSState, rcs_cfg: RCSConfig, candle_data: dict, direction: str, pattern_name: str, info: Any, tick: Any) -> None:
        c_close, c_high, c_low, c_open = candle_data["close_"], candle_data["high_"], candle_data["low_"], candle_data["open_"]
        spread, body_pct, ema = int(candle_data["spread"]), candle_data["body_pct"], candle_data["ema_now"]
        
        risk_range = (c_close - c_low) if direction == "BUY" else (c_high - c_close)
        levels = calculate_levels(c_close, risk_range, direction, rcs_cfg)
        
        dist_open_ema = int(round(abs(c_open - ema) / info.point)) if info.point > 0 else 0
        risk_range_pts = int(round(risk_range / info.point)) if info.point > 0 else 0

        print(cprint(f"🎯 VALID Trigger {symbol} {pattern_name} {direction}!", Colors.GREEN))
        print(cprint(f"   ├── Jarak Open C1 - EMA 20 : {dist_open_ema} pts [Syarat: {rcs_cfg.min_ema_distance_pts}-{rcs_cfg.max_ema_distance_pts}]", Colors.CYAN))
        print(cprint(f"   ├── Risk Range C1           : {risk_range_pts} pts [Syarat: {rcs_cfg.min_trigger_range}-{rcs_cfg.max_trigger_range}]", Colors.CYAN))
        print(cprint(f"   └── Ketebalan Body C1       : {body_pct:.1f}% [Syarat: {rcs_cfg.min_body_percent}-{rcs_cfg.max_body_percent}%]", Colors.CYAN))

        state.phase = RCSPhase.OP1
        state.trigger_direction = direction
        state.trigger_risk_range = risk_range
        state.trigger_timestamp = int(candle_data["timestamp"].timestamp()) if hasattr(candle_data["timestamp"], "timestamp") else int(time.time())
        state.op1_level, state.op2_level, state.op3_level = levels["op1_level"], levels["op2_level"], levels["op3_level"]
        state.trigger_age = 0

        state.trigger_dist_ema_pts = dist_open_ema
        state.trigger_risk_range_pts = risk_range_pts
        state.trigger_body_pct = body_pct
        state.trigger_spread_pts = spread
        state.save_to_file(symbol)
        
        # REALTIME LOT UPDATE: Update dana dan lot secara realtime persis sebelum menembakkan trigger (OP1/OP2/OP3)
        rcs_cfg.update_dynamic_lots(symbol)
        
        current_price = tick.ask if direction == "BUY" else tick.bid
        if place_op1_order(symbol, current_price, state, rcs_cfg):
            state.op1_filled = True
            if state.op1_ticket:
                self.tracker.register_system_ticket(symbol, state.op1_ticket, "RCS", rcs_cfg.magic_op1, direction, rcs_cfg.lot_size_op1, state.op1_open_price)

            if place_op2_order(symbol, state, rcs_cfg) and state.op2_ticket:
                self.tracker.register_system_ticket(symbol, state.op2_ticket, "RCS", rcs_cfg.magic_op2, direction, rcs_cfg.lot_size_op2, state.op2_level)

            if place_op3_order(symbol, state, rcs_cfg) and state.op3_ticket:
                self.tracker.register_system_ticket(symbol, state.op3_ticket, "RCS", rcs_cfg.magic_op3, "SELL" if direction == "BUY" else "BUY", round(rcs_cfg.lot_size_op1 + rcs_cfg.lot_size_op2, 2), state.op3_level)
            
            if rcs_cfg.notif_trigger:
                notify_trigger(symbol, pattern_name, direction, state, rcs_cfg, candle_data=candle_data)

            if rcs_cfg.op1_entry_mode != "INSTANT_ZERO":
                notify_open(symbol, "OP1", state.op1_ticket, state.op1_open_price, state.tp1_price, rcs_cfg, direction=direction, is_op1=True)
        else:
            print(cprint(f"❌ Gagal memasang OP1 pada {symbol}. Reset state.", Colors.RED))
            state.reset(symbol)

    def _handle_op1_phase(self, symbol: str, state: RCSState, rcs_cfg: RCSConfig) -> None:
        if state.op1_ticket is None:
            return
            
        import os
        is_multi = os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true"

        def _get_price_open(item):
            if isinstance(item, dict):
                return item.get("price_open", 0.0)
            elif hasattr(item, "price_open"):
                return item.price_open
            return 0.0

        if is_multi:
            from mt5_client.multi_account_dispatcher import check_multi_account_tickets_active
            tickets_dict = dict(getattr(state, 'multi_account_tickets', {}))

            ma_status = check_multi_account_tickets_active("RCS", symbol, tickets_dict)
            all_pos_map = {}
            all_ord_map = {}
            for acc_k, acc_v in ma_status.get("accounts", {}).items():
                all_pos_map.update(acc_v.get("positions_map", {}))
                all_ord_map.update(acc_v.get("orders_map", {}))

            pos1 = [all_pos_map[state.op1_ticket]] if state.op1_ticket in all_pos_map else []
            ord1 = [all_ord_map[state.op1_ticket]] if state.op1_ticket in all_ord_map else []
            pos2 = [all_pos_map[state.op2_ticket]] if state.op2_ticket and state.op2_ticket in all_pos_map else []
            ord2 = [all_ord_map[state.op2_ticket]] if state.op2_ticket and state.op2_ticket in all_ord_map else []
            pos3 = [all_pos_map[state.op3_ticket]] if state.op3_ticket and state.op3_ticket in all_pos_map else []
            ord3 = [all_ord_map[state.op3_ticket]] if state.op3_ticket and state.op3_ticket in all_ord_map else []
        else:
            pos1 = mt5.positions_get(ticket=state.op1_ticket)
            ord1 = mt5.orders_get(ticket=state.op1_ticket)
            
            # Guard terhadap koneksi putus
            if pos1 is None or ord1 is None:
                err = mt5.last_error()
                if err and err[0] != 4753:
                    return # Error koneksi, jangan lakukan aksi apa-apa
            
            pos2 = mt5.positions_get(ticket=state.op2_ticket) if state.op2_ticket else []
            ord2 = mt5.orders_get(ticket=state.op2_ticket) if state.op2_ticket else []
            pos3 = mt5.positions_get(ticket=state.op3_ticket) if state.op3_ticket else []
            ord3 = mt5.orders_get(ticket=state.op3_ticket) if state.op3_ticket else []
        
        if not pos1 and not ord1:
            print(cprint(f"👻 OP1 (Tkt:{state.op1_ticket}) hilang dari market {symbol} (TP/SL Hit atau Cancel).", Colors.YELLOW))
            
            # 1. Batalkan seluruh pending order OP2 & OP3 di SEMUA akun target (ACC1, ACC2, ACC3)
            if is_multi:
                from mt5_client.multi_account_dispatcher import cancel_multi_account_pending_orders, get_multi_account_cycle_profit
                cancel_multi_account_pending_orders("RCS", symbol, [rcs_cfg.magic_op2, rcs_cfg.magic_op3])
                
                tickets_dict = dict(getattr(state, 'multi_account_tickets', {}))

                multi_pnl_data = get_multi_account_cycle_profit("RCS", symbol, tickets_dict)
                real_profit = multi_pnl_data.get("total_profit", 0.0)
            else:
                if state.op2_ticket: cancel_pending_order_rcs(state.op2_ticket)
                if state.op3_ticket: cancel_pending_order_rcs(state.op3_ticket)
                real_profit = calculate_cycle_profit(state, tracker=self.tracker, symbol=symbol)
                multi_pnl_data = None
            
            notify_result(symbol, "Siklus Selesai", real_profit, 0.0, rcs_cfg, state=state, multi_pnl_data=multi_pnl_data)
            state.reset(symbol)
            self.tracker.clear_closed_manual(symbol)
            return
            
        # Cek transisi OP2 dari Order menjadi Position
        if state.op2_ticket and not state.op2_notified:
            if pos2 and not ord2:
                state.op2_notified = True
                state.op2_filled = True
                op2_open_price = _get_price_open(pos2[0])
                
                if rcs_cfg.op2_mode == "HEDGE":
                    if is_multi:
                        from mt5_client.multi_account_dispatcher import remove_multi_account_tp
                        remove_multi_account_tp("RCS", symbol, magic_numbers=[rcs_cfg.magic_op1])
                    else:
                        if state.op1_ticket: remove_tp_from_position(state.op1_ticket)
                    print(cprint(f"❄️ HEDGE (OP2) Terbuka di {op2_open_price:.5f} ({symbol}). Beralih ke PHASE_FREEZE. TP OP1 telah dihapus!", Colors.CYAN))
                    state.phase = RCSPhase.FREEZE
                    state.freeze_is_hedge = True
                    enter_freeze(state, rcs_cfg, tracker=self.tracker, symbol=symbol)
                    notify_freeze(symbol, state.freeze_start_floating_usd, rcs_cfg)
                else:
                    print(cprint(f"🎯 OP2 (Hedge Reentry Limit) tersentuh di {op2_open_price:.5f} ({symbol})! Posisi aktif.", Colors.GREEN))
                    notify_open(symbol, "OP2", state.op2_ticket, op2_open_price, state.tp2_price, rcs_cfg)
                    
        # Cek jika OP2 pernah aktif lalu menyentuh TP2
        if state.op2_ticket and state.op2_notified and state.phase != RCSPhase.FREEZE:
            if not pos2:
                print(cprint(f"🎯 OP2 menyentuh TP2 ({symbol})! Menutup sisa posisi OP1...", Colors.GREEN))
                if state.op1_ticket:
                    if is_multi:
                        from mt5_client.multi_account_dispatcher import close_multi_account_all_positions
                        close_multi_account_all_positions("RCS", symbol, [rcs_cfg.magic_op1])
                    else:
                        pos1_check = mt5.positions_get(ticket=state.op1_ticket)
                        if pos1_check: close_position_by_ticket(state.op1_ticket)
                    
                if is_multi:
                    from mt5_client.multi_account_dispatcher import cancel_multi_account_pending_orders, get_multi_account_cycle_profit
                    cancel_multi_account_pending_orders("RCS", symbol, [rcs_cfg.magic_op3])
                    
                    tickets_dict = dict(getattr(state, 'multi_account_tickets', {}))

                    multi_pnl_data = get_multi_account_cycle_profit("RCS", symbol, tickets_dict)
                    real_profit = multi_pnl_data.get("total_profit", 0.0)
                else:
                    if state.op3_ticket: cancel_pending_order_rcs(state.op3_ticket)
                    real_profit = calculate_cycle_profit(state, tracker=self.tracker, symbol=symbol)
                    multi_pnl_data = None
                    
                notify_result(symbol, "Siklus Selesai (OP2 Menyentuh TP2)", real_profit, 0.0, rcs_cfg, state=state, multi_pnl_data=multi_pnl_data)
                state.reset(symbol)
                self.tracker.clear_closed_manual(symbol)
                return

        # Cek transisi OP3 dari Order menjadi Position
        if state.op3_ticket and state.phase != RCSPhase.FREEZE:
            if pos3 and not ord3:
                state.op3_filled = True
                if is_multi:
                    from mt5_client.multi_account_dispatcher import remove_multi_account_tp
                    remove_multi_account_tp("RCS", symbol, magic_numbers=[rcs_cfg.magic_op1, rcs_cfg.magic_op2])
                else:
                    if state.op1_ticket: remove_tp_from_position(state.op1_ticket)
                    if state.op2_ticket: remove_tp_from_position(state.op2_ticket)
                print(cprint(f"❄️ HEDGE (OP3) Terbuka ({symbol}). Beralih ke PHASE_FREEZE. TP1 & TP2 telah dihapus!", Colors.CYAN))
                state.phase = RCSPhase.FREEZE
                state.freeze_is_hedge = True
                enter_freeze(state, rcs_cfg, tracker=self.tracker, symbol=symbol)
                notify_freeze(symbol, state.freeze_start_floating_usd, rcs_cfg)

    def _handle_freeze_phase(self, symbol: str, state: RCSState, rcs_cfg: RCSConfig) -> None:
        if check_unfreeze(symbol, state, rcs_cfg, tracker=self.tracker):
            profit, recovery = calculate_recovery(symbol, state, rcs_cfg, tracker=self.tracker)
            print(cprint(f"☀️ UNFREEZE! Semua posisi telah ditutup ({symbol}). Recovery: ${recovery:.2f}", Colors.GREEN))
            
            import os
            if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
                from mt5_client.multi_account_dispatcher import get_multi_account_cycle_profit
                tickets_dict = dict(getattr(state, 'multi_account_tickets', {}))
                multi_pnl_data = get_multi_account_cycle_profit("RCS", symbol, tickets_dict)
                profit = multi_pnl_data.get("total_profit", profit)
            else:
                multi_pnl_data = None

            notify_result(symbol, "Unfreeze Selesai", profit, recovery, rcs_cfg, state=state, multi_pnl_data=multi_pnl_data)
            state.reset(symbol)
            self.tracker.clear_closed_manual(symbol)

