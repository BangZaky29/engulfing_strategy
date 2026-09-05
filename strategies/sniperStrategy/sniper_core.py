import MetaTrader5 as mt5
from typing import Dict, List, Any
import os

from config.sniper_config import SniperConfig
from indicatorInfo.sniperInfo.sniper_state import read_sniper_trigger, get_sniper_trigger_age_seconds, mark_sniper_consumed
from strategies.strategy_rcs.position_tracker import PositionTracker
from strategies.strategy_rcs.rcs_order_manager import send_market_order_rcs, send_pending_order_rcs, close_position_by_ticket, cancel_pending_order_rcs
from strategies.sniperStrategy.sniper_state import SniperStrategyState
from utils.colors import cprint, Colors

class SniperEngine:
    def __init__(self, symbols: List[str], tracker: PositionTracker):
        self.symbols = symbols
        self.tracker = tracker
        self.config: SniperConfig = SniperConfig.from_env()
        self.states: Dict[str, SniperStrategyState] = {sym: SniperStrategyState.load(sym) for sym in symbols}
        self.last_m5_times: Dict[str, int] = {sym: 0 for sym in symbols}

    def process_tick(self, symbol: str) -> None:
        if not self.config.strategy_enabled:
            return

        state = self.states[symbol]
        
        # Cek Cutloss SL / Close All
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
                else:
                    # Mungkin masih pending limit
                    cancel_pending_order_rcs(state.active_ticket)

                print(cprint(f"✅ [{symbol}] SNIPER ORDER/POS {state.active_ticket} DITUTUP.", Colors.GREEN))
                state.reset()

            self.last_m5_times[symbol] = current_m5_time

        # Validasi manual apakah posisi sudah diclose oleh TP/SL MT5 asli
        pos = mt5.positions_get(ticket=state.active_ticket)
        ord = mt5.orders_get(ticket=state.active_ticket)
        if (not pos or len(pos) == 0) and (not ord or len(ord) == 0):
            # Sudah closed (TP kena)
            state.reset()

    def _check_and_execute_trigger(self, symbol: str, state: SniperStrategyState) -> None:
        # Mesin Sniper mandiri tidak mengeksekusi jika ADA OP APAPUN di sistem.
        snapshot = self.tracker.poll_positions(symbol)
        if snapshot.system_count > 0 or snapshot.manual_count > 0:
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
            state.save()

            print(cprint(f"✅ [{symbol}] SNIPER STRATEGY Berhasil! Ticket: {state.active_ticket}", Colors.GREEN))
            mark_sniper_consumed("SNIPER_STRATEGY")
