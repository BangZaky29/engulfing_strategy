import MetaTrader5 as mt5
from typing import Dict, List, Any
import os

from config.sniper_config import SniperConfig
from strategies.strategy_rcs.sniper_trigger_reader import read_sniper_trigger, get_sniper_trigger_age_seconds, mark_sniper_consumed
from mt5_client.position_tracker.tracker import PositionTracker
from strategies.strategy_rcs.rcs_order_manager import send_market_order_rcs, send_pending_order_rcs, close_position_by_ticket, cancel_pending_order_rcs
from strategies.sniperStrategy.sniper_state import SniperStrategyState
from config.rcs_config import RCSConfig
from mt5_client.position_tracker.models import PositionSnapshot
from utils.colors import cprint, Colors

from indicatorInfo.sniperInfo.sniper_notifier import SniperNotifier

class SniperEngine:
    def __init__(self, symbols: List[str], tracker: PositionTracker):
        self.symbols = symbols
        self.tracker = tracker
        self.config: SniperConfig = SniperConfig.from_env()
        self.states: Dict[str, SniperStrategyState] = {sym: SniperStrategyState.load(sym) for sym in symbols}
        self.last_m5_times: Dict[str, int] = {sym: 0 for sym in symbols}
        self.notifier = SniperNotifier(self.config)

    def process_tick(self, symbol: str) -> None:
        if not self.config.strategy_enabled:
            return

        state = self.states[symbol]
        
        # Basket Recovery Check
        if self.config.help_rcs_recovery:
            snapshot = self.tracker.poll_positions(symbol)
            rcs_cfg = RCSConfig.from_env()
            is_rcs_hedging = any(p.magic_number == rcs_cfg.magic_op3 for p in snapshot.system_positions)
            if is_rcs_hedging:
                self._check_basket_recovery(symbol, snapshot, state)

        # Cek Cutloss SL / Close All / Expiration
        if state.active_ticket is not None:
            self._check_cutloss_sl(symbol, state)
            return  # Tunggu sampai clear sebelum proses trigger baru

        # Jika tidak ada aktif OP Sniper, cek trigger baru
        self._check_and_execute_trigger(symbol, state)

    def _check_cutloss_sl(self, symbol: str, state: SniperStrategyState) -> None:
        """
        Cek apakah M5 candle baru saja close melebihi batas C1 trigger
        (High untuk SELL, Low untuk BUY).
        Jika ya, close all orders / cancel pending.
        """
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 2)
        if rates is None or len(rates) < 2:
            return

        current_m5_time = int(rates[0]['time'])
        if current_m5_time > self.last_m5_times.get(symbol, 0):
            # Candle M5 baru bergeser (candle index 1 baru saja selesai / diclose)
            closed_candle = rates[1]
            close_price = closed_candle['close']
            
            is_sl_hit = False
            if state.trigger_direction == "BUY":
                if close_price < state.c1_low:
                    is_sl_hit = True
            elif state.trigger_direction == "SELL":
                if close_price > state.c1_high:
                    is_sl_hit = True

            if is_sl_hit:
                print(cprint(f"🛑 [{symbol}] SNIPER SL CUTLOSS TERKENA! Close M5 melebihi batas trigger C1.", Colors.YELLOW))
                
                # Check apakah ini posisi aktif atau pending
                pos = mt5.positions_get(ticket=state.active_ticket)
                if pos and len(pos) > 0:
                    close_position_by_ticket(state.active_ticket, "SNIPER_CUTLOSS")
                    self._handle_closed_trade(symbol, state)
                else:
                    # Mungkin masih pending limit
                    cancel_pending_order_rcs(state.active_ticket)

                print(cprint(f"✅ [{symbol}] SNIPER ORDER/POS {state.active_ticket} DITUTUP.", Colors.GREEN))
                state.reset()

            # Cek Expiration Max Pending Candles
            if state.trigger_time > 0:
                candles_passed = (current_m5_time - state.trigger_time) / 300
                if candles_passed > self.config.max_pending_candles:
                    ord = mt5.orders_get(ticket=state.active_ticket)
                    if ord and len(ord) > 0: # Masih berupa pending order
                        print(cprint(f"⌛ [{symbol}] SNIPER LIMIT EXPIRED! > {self.config.max_pending_candles} Candle M5 berlalu.", Colors.YELLOW))
                        cancel_pending_order_rcs(state.active_ticket)
                        print(cprint(f"✅ [{symbol}] SNIPER PENDING ORDER {state.active_ticket} DIBATALKAN.", Colors.GREEN))
                        state.reset()
                        return

            self.last_m5_times[symbol] = current_m5_time

        # Validasi manual apakah posisi sudah diclose oleh TP/SL MT5 asli
        pos = mt5.positions_get(ticket=state.active_ticket)
        ord = mt5.orders_get(ticket=state.active_ticket)
        if (not pos or len(pos) == 0) and (not ord or len(ord) == 0):
            # Sudah closed (TP kena atau manual)
            self._handle_closed_trade(symbol, state)
            state.reset()

    def _handle_closed_trade(self, symbol: str, state: SniperStrategyState):
        """Ambil screenshot dan profit saat posisi tertutup, lalu kirim ke WA."""
        ticket = state.active_ticket
        deals = mt5.history_deals_get(position=ticket)
        if not deals:
            return
            
        profit = sum(d.profit + d.commission + d.swap for d in deals)
        
        info = mt5.symbol_info(symbol)
        pips = 0
        if info and info.point > 0:
            open_price = state.trigger_price
            close_price = deals[-1].price if deals else open_price
            diff = close_price - open_price
            if state.trigger_direction == "SELL":
                diff = open_price - close_price
            pips = int(round(diff / info.point))
            
        img_url = ""
        # Screenshot
        from mt5_client.visualizer import generate_screenshot
        from config.mt5_config import EMAConfig, MT5Config
        from database.supabase_storage import upload_screenshot
        from mt5_client.trade_monitor.session_utils import get_indonesian_date_str
        import os
        
        try:
            mt5_cfg = MT5Config()
            tf_const = mt5_cfg.get_mt5_timeframe(self.config.tf_confirm)
            rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, 30)
            if rates is not None and len(rates) > 0:
                TEMP_DIR = "temp_screenshots"
                new_filename = f"{state.trigger_direction}_SNIPER_{symbol}_{ticket}.png"
                new_path = os.path.join(TEMP_DIR, new_filename)
                
                img_path = generate_screenshot(
                    rates=rates,
                    ticket_id=ticket,
                    op_price=state.trigger_price,
                    sl_price=0.0,
                    tp_price=0.0,
                    ema_cfg=EMAConfig(),
                    mode=state.trigger_direction,
                    tf_label=self.config.tf_confirm,
                    output_dir=TEMP_DIR,
                    num_candles=30
                )
                if img_path and os.path.exists(img_path):
                    os.rename(img_path, new_path)
                    folder_date = get_indonesian_date_str().replace('/', '-')
                    success, uploaded_url = upload_screenshot(new_path, "sniper_trades", folder_date, new_filename)
                    if success:
                        img_url = uploaded_url
                    try:
                        os.remove(new_path)
                    except Exception:
                        pass
        except Exception as e:
            print(cprint(f"⚠️ Gagal generate SS Sniper: {e}", Colors.YELLOW))
            
        self.notifier.notify_profit_loss(symbol, ticket, profit, pips, img_url)

    def _check_basket_recovery(self, symbol: str, snapshot: PositionSnapshot, sniper_state: SniperStrategyState) -> None:
        """Cek apakah kombinasi floating RCS Hedging + Sniper sudah mencapai +$2"""
        total_pnl = 0.0
        tickets_to_close = []
        rcs_cfg = RCSConfig.from_env()

        # PnL RCS & Sniper dari PositionSnapshot
        for pos in snapshot.system_positions:
            if pos.magic_number in [rcs_cfg.magic_op1, rcs_cfg.magic_op2, rcs_cfg.magic_op3, self.config.magic_number]:
                total_pnl += pos.net_profit
                tickets_to_close.append(pos.ticket)

        if len(tickets_to_close) > 0 and total_pnl >= 2.0:
            print(cprint(f"🏆 [{symbol}] BASKET RECOVERY TERCAPAI! Total PnL: ${total_pnl:.2f} >= $2.00", Colors.GREEN))
            for tkt in tickets_to_close:
                close_position_by_ticket(tkt, "BASKET_RECOVERY_SNIPER")
            
            # Reset Sniper
            sniper_state.reset()
            self.tracker.clear_closed_manual(symbol)
            # Catatan: RCS State tidak perlu direset manual di sini. Watchdog RCS 
            # akan melihat OP3 (dan OP lainnya) sudah tertutup sehingga melakukan Unfreeze otomatis.
            print(cprint(f"✅ [{symbol}] Semua posisi Hedging RCS & Sniper telah dibersihkan.", Colors.GREEN))

    def _check_and_execute_trigger(self, symbol: str, state: SniperStrategyState) -> None:
        snapshot = self.tracker.poll_positions(symbol)
        
        # Cek status RCS
        rcs_cfg = RCSConfig.from_env()
        is_rcs_hedging = any(p.magic_number == rcs_cfg.magic_op3 for p in snapshot.system_positions)

        # Mesin Sniper mandiri tidak mengeksekusi jika ADA OP APAPUN di sistem.
        # Pengecualian: Jika saklar SNIPER_HELP_RCS_RECOVERY nyala dan RCS sedang Hedging, boleh mengeksekusi.
        if snapshot.system_count > 0 or snapshot.manual_count > 0:
            if not (self.config.help_rcs_recovery and is_rcs_hedging and snapshot.manual_count == 0):
                return

        sniper_trigger = read_sniper_trigger(symbol)
        if not sniper_trigger:
            return
            
        # Cek apakah trigger sudah dieksekusi / consumed
        if sniper_trigger.get("consumed_by"):
            return

        direction = sniper_trigger.get("direction")
        if not direction:
            return

        age_sec = get_sniper_trigger_age_seconds(sniper_trigger)
        if age_sec > 300:
            return

        # Eksekusi Sniper Mandiri
        sniper_lot = self.config.lot_size
        sniper_magic = self.config.magic_number
        tp_percent = self.config.tp_percent
        entry_percent = self.config.entry_percent

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return

        current_price = tick.ask if direction == "BUY" else tick.bid
        emoji = "🟢" if direction == "BUY" else "🔴"

        tp_price = 0.0
        tp_dist = 0.0
        op_level = current_price
        c1_high = sniper_trigger.get("m5_high", 0.0)
        c1_low = sniper_trigger.get("m5_low", 0.0)
        c1_close = sniper_trigger.get("m5_close", 0.0)

        if c1_high > 0 and c1_low > 0:
            risk_range = (c1_close - c1_low) if direction == "BUY" else (c1_high - c1_close)
            tp_dist = risk_range * (tp_percent / 100.0)
            op_dist_entry = risk_range * (entry_percent / 100.0)
            
            if direction == "BUY":
                op_level = c1_close - op_dist_entry
                tp_price = op_level + tp_dist
            else:
                op_level = c1_close + op_dist_entry
                tp_price = op_level - tp_dist

        use_market = False
        if direction == "BUY" and current_price <= op_level:
            use_market = True
        elif direction == "SELL" and current_price >= op_level:
            use_market = True

        print(cprint(
            f"\n🎯 [{symbol}] SNIPER STRATEGY ENGINE OP!\n"
            f"   ├── Direction: {emoji} {direction}\n"
            f"   ├── Lot      : {sniper_lot}\n"
            f"   ├── Price/Lim: {current_price:.5f} / {op_level:.5f}\n"
            f"   ├── TP ({tp_percent}%) : {tp_price:.5f}\n"
            f"   ├── C1 Low/Hi: {c1_low:.5f} / {c1_high:.5f}\n"
            f"   └── Magic    : {sniper_magic}",
            Colors.CYAN,
        ))

        res = None
        if use_market:
            res = send_market_order_rcs(
                symbol=symbol,
                action_str=direction,
                price=current_price,
                lot_size=sniper_lot,
                magic_number=sniper_magic,
                comment="SNIPER_STRATEGY",
                tp=tp_price,
                tp_dist=tp_dist
            )
        else:
            order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
            res = send_pending_order_rcs(
                symbol=symbol,
                order_type=order_type,
                price=op_level,
                lot_size=sniper_lot,
                magic_number=sniper_magic,
                comment="SNIPER_STRATEGY",
                sl=0.0,
                tp=tp_price
            )

        if res:
            state.active_ticket = res.order
            state.trigger_direction = direction
            state.trigger_price = res.price if (use_market and res.price) else op_level
            state.c1_low = c1_low
            state.c1_high = c1_high
            
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1)
            state.trigger_time = int(rates[0]['time']) if rates else int(tick.time)
            
            state.save()

            print(cprint(f"✅ [{symbol}] SNIPER STRATEGY Berhasil! Ticket: {state.active_ticket}", Colors.GREEN))
            self.notifier.notify_op_signal(symbol, direction, state.active_ticket, state.trigger_price, 0.0, tp_price)
            mark_sniper_consumed("SNIPER_STRATEGY")
