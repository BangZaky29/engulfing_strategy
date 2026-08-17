import os
import time
import MetaTrader5 as mt5

from utils.colors import Colors, cprint
from mt5_client import init_mt5, get_closed_candles
from config.mt5_config import MT5Config
from indicatorInfo.triggerInfo.scanner.patterns.marubozu import MarubozuPattern

from strategies.strategy_rcs.rcs_state import RCSState
from strategies.strategy_rcs.rcs_order_manager import (
    close_position_rcs, 
    close_position_by_ticket,
    cancel_pending_order_rcs, 
    remove_tp_from_position
)
from strategies.recovery_marubozu.state.mrcv_state import MRCVState, MRCVPhase
from strategies.recovery_marubozu.mrcv_core import process_marubozu_trigger, cleanup_pending_orders

from strategies.recovery_marubozu.orders.mrcv_order_manager import close_all_positions
from strategies.recovery_marubozu.orders.mrcv_profit_calc import get_positions_profit, calculate_mrcv_cycle_profit

from strategies.recovery_marubozu.notifications.wa_base_sender import send_mrcv_wa_notif, generate_and_upload_mrcv_screenshot
from strategies.recovery_marubozu.notifications.wa_events import (
    notify_mrcv_op2_filled,
    notify_mrcv_op3_freeze,
    notify_mrcv_cycle_done,
    notify_mrcv_hanging_positions,
    notify_mrcv_positions_cleared,
    notify_mrcv_max_loss_close_all
)

class MRCVEngine:
    def __init__(self):
        self.symbol = os.getenv("MRCV_SYMBOL", "BTC")
        self.tf_str = os.getenv("MRCV_TIMEFRAME", "M5")
        
        self.mrcv_magic = int(os.getenv("MRCV_MAGIC_NUMBER", "999000"))
        self.mrcv_magics = [self.mrcv_magic]
        
        self.rcs_magics = [901001, 901002, 901003]
        if self.symbol == "NASDAQ-100":
            self.rcs_magics = [221160935, 221160936, 221160937]
            
        self.all_magics = self.mrcv_magics + self.rcs_magics
        
        self.mrcv_state = MRCVState()
        self.rcs_state = RCSState()
        self.pattern_detector = MarubozuPattern()
        
        self.last_hedge_status = False
        self.is_paused_by_hanging = False
        self.is_cutloss_locked = False
        self.mrcv_group_jid = os.getenv("MRCV_GROUP_JID", "120363430592783067@g.us")
        
    def setup(self):
        mt5_cfg = MT5Config()
        if not init_mt5(mt5_cfg):
            print(cprint("❌ Gagal terhubung ke MT5", Colors.RED))
            return False
            
        if not mt5.symbol_select(self.symbol, True):
            print(cprint(f"❌ Gagal memilih symbol {self.symbol}", Colors.RED))
            return False
            
        self.mrcv_state.load_from_file(self.symbol)
        print(cprint(f"📊 [MRCV] Status Kumulatif Profit Awal [{self.symbol}]: ${self.mrcv_state.cumulative_profit:+.2f}", Colors.CYAN))
        
        from mt5_client.money_management import get_account_funds_info
        funds_info = get_account_funds_info()

        print("==================================================")
        multi_enabled = os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true"
        if multi_enabled:
            from mt5_client.multi_account_dispatcher import get_multi_account_funds_info
            print(cprint(f"💰 INFORMASI DANA & KESEHATAN MULTI-AKUN MT5 (MRCV):", Colors.CYAN))
            multi_funds = get_multi_account_funds_info("MRCV")
            acc_lines = []
            for acc_f in multi_funds:
                if acc_f.get("connected"):
                    print(cprint(f"🔹 [{acc_f['key']}] {acc_f['name']} (Login: {acc_f['login']} | Server: {acc_f['server']})", Colors.CYAN))
                    print(cprint(f"   • Tipe Akun      : {acc_f['account_type']}", Colors.CYAN))
                    print(cprint(f"   • Balance / Eq   : ${acc_f['balance']:.2f} / ${acc_f['equity']:.2f}", Colors.CYAN))
                    print(cprint(f"   • Free Margin    : ${acc_f['margin_free']:.2f} (Margin Level: {acc_f['health_status']})", Colors.CYAN))
                    print(cprint(f"   • Leverage Akun  : {acc_f['leverage']} | Ping: {acc_f['ping_str']} | AutoTrading: {acc_f['autotrading']}", Colors.CYAN))
                    print(cprint(f"   • Dynamic Lot OP1: {acc_f['dynamic_lot']} Lot | Dynamic Cutloss: ${acc_f['scaled_max_loss']:.2f} (Base: ${acc_f['base_max_loss']:.2f})", Colors.GREEN))
                    acc_lines.append(
                        f"🔹 *{acc_f['key']}:* {acc_f['name']} (Login: {acc_f['login']})\n"
                        f"  • Balance / Equity: *${acc_f['balance']:.2f}* / *${acc_f['equity']:.2f}*\n"
                        f"  • Margin Level: *{acc_f['health_status']}* | Leverage: *{acc_f['leverage']}*\n"
                        f"  • Lot OP1: *{acc_f['dynamic_lot']} Lot* | Cutloss: *${acc_f['scaled_max_loss']:.2f}*"
                    )
                else:
                    print(cprint(f"🔹 [{acc_f['key']}] {acc_f['name']} (Login: {acc_f['login']}) -> Gagal Terhubung: {acc_f.get('error')}", Colors.RED))
                    acc_lines.append(f"🔹 *{acc_f['key']}:* {acc_f['name']} -> *Offline / Disconnected*")
            multi_block = "\n\n".join(acc_lines)
            acc_wa_section = f"💰 *DANA & KESEHATAN MULTI-AKUN MT5 (MRCV):*\n\n{multi_block}\n"
        else:
            print(cprint(f"💰 DANA & KESEHATAN AKUN MT5 REALTIME:", Colors.CYAN))
            print(cprint(f"   • Tipe Akun      : {funds_info['account_type']} (Login: {funds_info['account_number']} | Server: {funds_info['server']})", Colors.CYAN))
            print(cprint(f"   • Balance / Eq   : ${funds_info['balance']:.2f} / ${funds_info['equity']:.2f}", Colors.CYAN))
            print(cprint(f"   • Free Margin    : ${funds_info['margin_free']:.2f} (Margin Terpakai: ${funds_info['margin_used']:.2f})", Colors.CYAN))
            print(cprint(f"   • Margin Level   : {funds_info['health_status']}", Colors.GREEN if "SEHAT" in funds_info['health_status'] else Colors.YELLOW))
            print(cprint(f"   • Leverage Akun  : {funds_info['leverage']}", Colors.CYAN))
            print(cprint(f"📡 PERFORMA JARINAN BROKER:", Colors.CYAN))
            print(cprint(f"   • Ping Server    : {funds_info['ping_str']}", Colors.CYAN))
            print(cprint(f"   • AutoTrading    : {funds_info['autotrading']}", Colors.CYAN))
            print(cprint(f"   • Acuan Modal    : {funds_info['source_type']} (${funds_info['funds_used']:.2f})", Colors.CYAN))
            print(cprint(f"   • Dynamic Lot OP1: {funds_info['dynamic_lot']} Lot", Colors.GREEN))
            print(cprint(f"   • Dynamic Cutloss: ${funds_info.get('scaled_max_loss', -15.0):.2f} (Base: ${funds_info.get('base_max_loss', -15.0):.2f} / 0.01 Lot)", Colors.RED))
            acc_wa_section = (
                f"💰 *DANA & KESEHATAN AKUN MT5:*\n"
                f"• Tipe Akun: *{funds_info['account_type']}* (Login: {funds_info['account_number']} | Server: {funds_info['server']})\n"
                f"• Balance / Equity: *${funds_info['balance']:.2f}* / *${funds_info['equity']:.2f}*\n"
                f"• Free Margin: *${funds_info['margin_free']:.2f}* (Margin Level: *{funds_info['health_status']}*)\n"
                f"• Leverage: *{funds_info['leverage']}*\n"
                f"📡 *KONEKSI BROKER:* Ping *{funds_info['ping_str']}* | AutoTrading *{funds_info['autotrading']}*\n"
                f"• Dynamic Lot OP1: *{funds_info['dynamic_lot']} Lot* (Acuan: {funds_info['source_type']})\n"
                f"• Dynamic Cutloss: *${funds_info.get('scaled_max_loss', -15.0):.2f}* (Base: ${funds_info.get('base_max_loss', -15.0):.2f} / 0.01 Lot)\n"
            )

        mrcv_loss_lock = os.getenv("MRCV_LOSS_LOCK_ENABLED", "true").lower() == "true"
        print(cprint(f"🛡️ GUARD EXECUTION LOCK : Loss Lock: {'ON 🔒' if mrcv_loss_lock else 'OFF 🔓'}", Colors.CYAN))
        print("==================================================")

        print(cprint(f"🤖 Memulai Marubozu Recovery Machine (MRCV) [{self.symbol}]", Colors.MAGENTA))
        wait_mode = os.getenv("MRCV_WAIT_FOR_RCS_HEDGE", "true").lower() == "true"
        mode_text = "Menunggu RCS Hedging (Standby)" if wait_mode else "Selalu Aktif (Mandiri)"
        start_msg = (
            f"🟢 SISTEM DIAKTIFKAN 🟢\n\n"
            f"{acc_wa_section}"
            f"🛡️ *GUARD EXECUTION:* Loss Lock: *{'ON 🔒' if mrcv_loss_lock else 'OFF 🔓'}*\n\n"
            f"📊 Symbol: {self.symbol}\n"
            f"⚙️ Mode: {mode_text}"
        )
        send_mrcv_wa_notif(start_msg, "MRCV_START", target_jid=self.mrcv_group_jid, include_header=False)
        
        # Audit Posisi Awal saat Startup
        startup_positions = mt5.positions_get(symbol=self.symbol)
        if startup_positions and len(startup_positions) > 0:
            print(cprint(f"⚠️ [MRCV] Terdeteksi {len(startup_positions)} posisi aktif di MT5 saat startup [{self.symbol}].", Colors.YELLOW))
            notify_mrcv_hanging_positions(self.symbol, list(startup_positions))
            self.is_paused_by_hanging = True
        else:
            print(cprint(f"✅ [MRCV] Audit Posisi: CLEAN (0 posisi pada {self.symbol}).", Colors.GREEN))
            
        from mt5_client.autotrading_guard import init_autotrading_state
        init_autotrading_state()
        return True

    def run(self):
        if not self.setup():
            return
            
        from mt5_client.autotrading_guard import check_and_notify_autotrading_change
        while True:
            try:
                check_and_notify_autotrading_change("MRCV")
                self.process_tick()
                time.sleep(1)
            except KeyboardInterrupt:
                stop_msg = (
                    f"🛑 SISTEM DIMATIKAN 🛑\n\n"
                    f"📊 Symbol: {self.symbol}\n"
                    f"Status: Mesin telah dihentikan secara manual."
                )
                send_mrcv_wa_notif(stop_msg, "MRCV_STOP", target_jid=self.mrcv_group_jid, include_header=False)
                time.sleep(2)
                print(cprint("\n🛑 MRCV Bot dihentikan oleh user.", Colors.YELLOW))
                break
            except Exception as e:
                print(cprint(f"⚠️ Error di MRCV loop: {e}", Colors.RED))
                time.sleep(5)

    def process_tick(self):
        is_enabled = os.getenv("MRCV_ENABLED", "true").lower() == "true"
        wait_for_hedge = os.getenv("MRCV_WAIT_FOR_RCS_HEDGE", "true").lower() == "true"
        
        if not is_enabled:
            if self.last_hedge_status:
                self.last_hedge_status = False
            time.sleep(4)
            return
            
        self.rcs_state.load_from_file(self.symbol)
        rcs_positions = mt5.positions_get(symbol=self.symbol)
        is_rcs_hedge = False
        rcs_floating = 0.0
        rcs_total_positions = 0
        
        if rcs_positions:
            rcs_buy = 0
            rcs_sell = 0
            for p in rcs_positions:
                if p.magic in self.rcs_magics:
                    rcs_floating += p.profit
                    rcs_total_positions += 1
                    if p.type == mt5.ORDER_TYPE_BUY:
                        rcs_buy += 1
                    elif p.type == mt5.ORDER_TYPE_SELL:
                        rcs_sell += 1
            if rcs_buy > 0 and rcs_sell > 0:
                is_rcs_hedge = True
                
        if wait_for_hedge:
            if not self.last_hedge_status and is_rcs_hedge:
                self.last_hedge_status = True
                msg = f"Tuyul RCS mengalami kondisi hedging pada symbol {self.symbol} dengan floating saat ini: ${rcs_floating:.2f}.\n🟢 Mesin *Marubozu Recovery (MRCV)* telah diaktifkan untuk memulai proses *recovery*!"
                send_mrcv_wa_notif(msg, "MRCV_HEDGE_DETECT", target_jid=self.mrcv_group_jid, include_header=False)
            
            if self.last_hedge_status and rcs_total_positions == 0:
                self.last_hedge_status = False
                print(cprint(f"✅ [MRCV] Posisi RCS pada {self.symbol} telah tuntas (0 posisi). Reset akumulasi recovery MRCV ke $0.0.", Colors.GREEN))
                self.mrcv_state.reset_all(self.symbol)
                return
            
            if not self.last_hedge_status:
                return
                
        # CEK CLOSE ALL
        if not wait_for_hedge or (wait_for_hedge and self.last_hedge_status):
            mrcv_floating = get_positions_profit(self.symbol, self.mrcv_magics)
            total_net = self.mrcv_state.cumulative_profit + mrcv_floating + rcs_floating
            
            target_profit = float(os.getenv("MRCV_TARGET_NET_PROFIT", "0.0"))
            base_max_loss = float(os.getenv("MRCV_MAX_NET_LOSS", "-15.0"))
            from mt5_client.money_management import get_dynamic_op1_lot, get_scaled_max_loss
            op1_lot, _, _ = get_dynamic_op1_lot(fallback_lot=float(os.getenv("MRCV_LOT_OP1", "0.01")))
            max_loss = get_scaled_max_loss(base_max_loss, op1_lot)

            if total_net >= target_profit:
                print(cprint(f"🎉 [MRCV] Target Profit Tercapai! Total Net: {total_net:+.2f} >= {target_profit:+.2f}. Melakukan Close All.", Colors.GREEN))
                success_msg = (
                    f"🎉 *[RECOVERY SUCCESS - CLOSE ALL]*\n"
                    f"Misi pemulihan berhasil! Total net profit telah mencapai target pemulihan.\n\n"
                    f"📊 *Rincian Keuangan:*\n"
                    f"• Total Net PnL: *${total_net:+.2f}*\n"
                    f"• Target Profit: ${target_profit:+.2f}\n"
                    f"• Floating MRCV: ${mrcv_floating:+.2f}\n"
                    f"• Floating RCS: ${rcs_floating:+.2f}\n"
                    f"• Kumulatif Profit MRCV: ${self.mrcv_state.cumulative_profit:+.2f}\n\n"
                    f"🧹 Seluruh posisi (RCS & MRCV) telah disapu bersih (Close ALL).\n"
                    f"🟢 Sistem di-reset dan kembali siaga normal."
                )
                send_mrcv_wa_notif(success_msg, "MRCV_SUCCESS", target_jid=self.mrcv_group_jid, include_header=False)
                profit_jid = os.getenv("PROFIT_SIGNAL")
                if profit_jid:
                    send_mrcv_wa_notif(success_msg, "MRCV_SUCCESS", target_jid=profit_jid, include_header=False)

                close_all_positions(self.symbol, self.all_magics)
                self.mrcv_state.reset_all(self.symbol)
                self.rcs_state.reset(self.symbol)
                time.sleep(1)
                return

            if total_net <= max_loss:
                print(cprint(f"🛑 [MRCV EMERGENCY CUTLOSS] Batas Max Loss Tercapai! Total Net: {total_net:+.2f} <= {max_loss:.2f}. Melakukan Close ALL.", Colors.RED))
                notify_mrcv_max_loss_close_all(
                    symbol=self.symbol,
                    total_net=total_net,
                    max_loss=max_loss,
                    mrcv_floating=mrcv_floating,
                    rcs_floating=rcs_floating,
                    cumulative_profit=self.mrcv_state.cumulative_profit
                )

                close_all_positions(self.symbol, self.all_magics)
                self.mrcv_state.reset_all(self.symbol)
                self.rcs_state.reset(self.symbol)

                mrcv_loss_lock = os.getenv("MRCV_LOSS_LOCK_ENABLED", "true").lower() == "true"
                if mrcv_loss_lock:
                    self.is_cutloss_locked = True
                    print(cprint(f"🔒 [MRCV LOCKOUT] Eksekusi OP dikunci (Standby monitoring).", Colors.YELLOW))
                time.sleep(1)
                return

        if self.is_cutloss_locked:
            # Info & monitoring tetap jalan, namun eksekusi OP baru diblokir
            return

        # CEK SIKLUS MRCV
        if self.mrcv_state.phase == MRCVPhase.ACTIVE:
            self.handle_active_phase(rcs_floating, wait_for_hedge)
        elif self.mrcv_state.phase == MRCVPhase.FREEZE:
            self.handle_freeze_phase()
        elif self.mrcv_state.phase == MRCVPhase.IDLE:
            self.handle_idle_phase(wait_for_hedge)

    def handle_active_phase(self, rcs_floating: float, wait_for_hedge: bool):
        positions = mt5.positions_get(symbol=self.symbol)
        op1_active = False
        op2_active = False
        op3_active = False
        op2_pos = None
        op3_pos = None
        
        if positions:
            for p in positions:
                if p.ticket == self.mrcv_state.op1_ticket:
                    op1_active = True
                if p.ticket == self.mrcv_state.op2_ticket:
                    op2_active = True
                    op2_pos = p
                if p.ticket == self.mrcv_state.op3_ticket:
                    op3_active = True
                    op3_pos = p
                    
        # OP2 Limit Terbuka
        if op2_active and not self.mrcv_state.op2_filled and op2_pos:
            self.mrcv_state.op2_filled = True
            self.mrcv_state.save_to_file(self.symbol)
            print(cprint(f"📉 [MRCV] OP2 LIMIT TERBUKA! Ticket #{op2_pos.ticket} di {op2_pos.price_open:.5f}", Colors.CYAN))
            notify_mrcv_op2_filled(
                symbol=self.symbol,
                direction=self.mrcv_state.trigger_direction or "BUY",
                ticket=op2_pos.ticket,
                price=op2_pos.price_open,
                tp_price=self.mrcv_state.tp2_price,
                volume=op2_pos.volume
            )

        # OP3 Stop Terbuka (Hedge)
        if op3_active and not self.mrcv_state.op3_filled and op3_pos:
            self.mrcv_state.op3_filled = True
            self.mrcv_state.phase = MRCVPhase.FREEZE
            self.mrcv_state.save_to_file(self.symbol)
            
            if self.mrcv_state.op1_ticket:
                remove_tp_from_position(self.mrcv_state.op1_ticket)
            
            if op2_active and self.mrcv_state.op2_ticket:
                remove_tp_from_position(self.mrcv_state.op2_ticket)
            elif self.mrcv_state.op2_ticket:
                cancel_pending_order_rcs(self.mrcv_state.op2_ticket)
            
            total_freeze_floating = get_positions_profit(self.symbol, self.mrcv_magics)
            op3_direction = "SELL" if self.mrcv_state.trigger_direction == "BUY" else "BUY"
            print(cprint(f"❄️ [MRCV] OP3 HEDGE AKTIF! Beralih ke PHASE_FREEZE. TP1 & TP2 telah dihapus! Floating: ${total_freeze_floating:.2f}", Colors.YELLOW))
            notify_mrcv_op3_freeze(
                symbol=self.symbol,
                op3_direction=op3_direction,
                ticket=op3_pos.ticket,
                price=op3_pos.price_open,
                volume=op3_pos.volume,
                floating_freeze=total_freeze_floating
            )
            return

        # OP2 menyentuh TP2
        if self.mrcv_state.op2_ticket and self.mrcv_state.op2_filled and not op2_active:
            print(cprint(f"🎯 [MRCV] OP2 menyentuh TP2 ({self.symbol})! Menutup sisa posisi OP1 & membatalkan OP3...", Colors.GREEN))
            if op1_active and self.mrcv_state.op1_ticket:
                close_position_by_ticket(self.mrcv_state.op1_ticket)
            if self.mrcv_state.op3_ticket:
                cancel_pending_order_rcs(self.mrcv_state.op3_ticket)
                
            total_prof, prof1, prof2 = calculate_mrcv_cycle_profit(self.mrcv_state)
            self.mrcv_state.cumulative_profit += total_prof
            self.mrcv_state.save_to_file(self.symbol)
            
            print(cprint(f"💰 [MRCV] Siklus Selesai (OP2 Hit TP2)! Profit siklus: {total_prof:+.2f} (OP1: {prof1:+.2f}, OP2: {prof2:+.2f}) | Kumulatif: {self.mrcv_state.cumulative_profit:+.2f}", Colors.CYAN))
            
            img_url = generate_and_upload_mrcv_screenshot(self.symbol, self.mrcv_state)
            notify_mrcv_cycle_done(
                symbol=self.symbol,
                cycle_profit=total_prof,
                cumulative_profit=self.mrcv_state.cumulative_profit,
                rcs_floating=rcs_floating,
                is_wait_rcs=wait_for_hedge,
                screenshot_url=img_url
            )
            
            cleanup_pending_orders(self.mrcv_state)
            self.mrcv_state.reset_cycle()
            return

        # OP1 menyentuh TP1
        if not op1_active and self.mrcv_state.op1_ticket:
            print(cprint(f"🎯 [MRCV] OP1 menyentuh TP1 ({self.symbol})! Menutup sisa posisi/pending order...", Colors.GREEN))
            if op2_active and self.mrcv_state.op2_ticket:
                close_position_by_ticket(self.mrcv_state.op2_ticket)
                
            cleanup_pending_orders(self.mrcv_state)
            
            total_prof, prof1, prof2 = calculate_mrcv_cycle_profit(self.mrcv_state)
            self.mrcv_state.cumulative_profit += total_prof
            self.mrcv_state.save_to_file(self.symbol)
            
            print(cprint(f"💰 [MRCV] Siklus Selesai (OP1 Hit TP1)! Profit siklus: {total_prof:+.2f} (OP1: {prof1:+.2f}, OP2: {prof2:+.2f}) | Kumulatif: {self.mrcv_state.cumulative_profit:+.2f}", Colors.CYAN))
            
            img_url = generate_and_upload_mrcv_screenshot(self.symbol, self.mrcv_state)
            notify_mrcv_cycle_done(
                symbol=self.symbol,
                cycle_profit=total_prof,
                cumulative_profit=self.mrcv_state.cumulative_profit,
                rcs_floating=rcs_floating,
                is_wait_rcs=wait_for_hedge,
                screenshot_url=img_url
            )
            
            self.mrcv_state.reset_cycle()

    def handle_freeze_phase(self):
        positions = mt5.positions_get(symbol=self.symbol)
        mrcv_pos_count = 0
        if positions:
            for p in positions:
                if p.magic in self.mrcv_magics:
                    mrcv_pos_count += 1
        
        if mrcv_pos_count == 0:
            print(cprint(f"☀️ [MRCV] UNFREEZE! Seluruh posisi MRCV telah ditutup ({self.symbol}). Kembali ke IDLE.", Colors.GREEN))
            self.mrcv_state.reset_cycle()

    def handle_idle_phase(self, wait_for_hedge: bool):
        all_current_positions = mt5.positions_get(symbol=self.symbol)
        hanging_positions = []
        
        if all_current_positions:
            if not wait_for_hedge:
                hanging_positions = list(all_current_positions)
            else:
                for p in all_current_positions:
                    if p.magic not in self.all_magics:
                        hanging_positions.append(p)
                        
        if hanging_positions:
            if not self.is_paused_by_hanging:
                self.is_paused_by_hanging = True
                print(cprint(f"⚠️ [MRCV] Terdeteksi {len(hanging_positions)} posisi aktif pada {self.symbol}. Siklus Marubozu di-pause sampai posisi ditutup manual.", Colors.YELLOW))
                notify_mrcv_hanging_positions(self.symbol, hanging_positions)
            return
        else:
            if self.is_paused_by_hanging:
                self.is_paused_by_hanging = False
                print(cprint(f"✅ [MRCV] Semua posisi pada {self.symbol} telah bersih (0 posisi). Siklus Marubozu aktif kembali.", Colors.GREEN))
                notify_mrcv_positions_cleared(self.symbol)

        candle = get_closed_candles(self.symbol, tf_label=self.tf_str)
        if candle is None:
            return

        current_candle_time = str(candle.get("timestamp"))

        if self.mrcv_state.last_processed_candle_time == current_candle_time:
            return
            
        point = mt5.symbol_info(self.symbol).point
        trigger = self.pattern_detector.detect(candle, None, point)
        
        if trigger:
            self.mrcv_state.last_processed_candle_time = current_candle_time
            self.mrcv_state.save_to_file(self.symbol)
            process_marubozu_trigger(self.symbol, candle, self.mrcv_state)
