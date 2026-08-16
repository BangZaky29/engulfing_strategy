import os
import time
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from utils.colors import Colors, cprint

from mt5_client.connection import init_mt5
from mt5_client.candle_fetcher import get_closed_candles
from indicatorInfo.triggerInfo.scanner.patterns.marubozu import MarubozuPattern

from strategies.strategy_rcs.rcs_state import RCSState
from strategies.strategy_rcs.rcs_order_manager import close_position_rcs, cancel_pending_order_rcs, remove_tp_from_position
from strategies.recovery_marubozu.mrcv_state import MRCVState, MRCVPhase
from strategies.recovery_marubozu.mrcv_core import process_marubozu_trigger, cleanup_pending_orders
from strategies.recovery_marubozu.mrcv_notifier import (
    send_mrcv_wa_notif, 
    generate_and_upload_mrcv_screenshot,
    notify_mrcv_op2_filled,
    notify_mrcv_op3_freeze,
    notify_mrcv_cycle_done,
    notify_mrcv_hanging_positions,
    notify_mrcv_positions_cleared,
    notify_mrcv_max_loss_close_all
)

def get_positions_profit(symbol: str, magics: list[int]) -> float:
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return 0.0
    profit = 0.0
    for p in positions:
        if p.magic in magics:
            profit += p.profit
    return profit

def close_all_positions(symbol: str, magics: list[int]):
    positions = mt5.positions_get(symbol=symbol)
    if positions:
        for p in positions:
            if p.magic in magics:
                close_position_rcs(symbol, p, p.magic, "MRCV Close All")
    
    orders = mt5.orders_get(symbol=symbol)
    if orders:
        for o in orders:
            if o.magic in magics:
                cancel_pending_order_rcs(o.ticket)

def get_closed_profit(ticket: int) -> float:
    """Ambil profit dari ticket order yang sudah di-close dari history."""
    # Ambil deal history untuk posisi yang dibuka oleh ticket ini
    # MT5 menghubungkan deals menggunakan POSITION_ID
    deals = mt5.history_deals_get(position=ticket)
    if not deals:
        return 0.0
    
    profit = 0.0
    for d in deals:
        profit += d.profit
    return profit

def run_mrcv_bot():
    if not init_mt5():
        print(cprint("❌ Gagal inisialisasi MT5 untuk MRCV.", Colors.RED))
        return

    symbol = os.getenv("MRCV_SYMBOL", "XAUUSD")
    tf_str = os.getenv("MRCV_TIMEFRAME", "M5")
    
    # Mapping TF string ke MT5
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
    }
    tf = tf_map.get(tf_str, mt5.TIMEFRAME_M5)
    
    mrcv_magic = int(os.getenv("MRCV_MAGIC_NUMBER", "999000"))
    mrcv_magics = [mrcv_magic, mrcv_magic+1, mrcv_magic+2]
    
    # RCS Magics: OP1, OP2, OP3
    rcs_magics = [901001, 901002, 901003] # Default XAUUSD
    if symbol == "NASDAQ-100":
        rcs_magics = [221160935, 221160936, 221160937]
        
    all_magics = mrcv_magics + rcs_magics
    
    mrcv_state = MRCVState()
    mrcv_state.load_from_file(symbol)
    
    rcs_state = RCSState()
    
    pattern_detector = MarubozuPattern()
    
    print(cprint(f"🤖 Memulai Marubozu Recovery Machine (MRCV) [{symbol}]", Colors.MAGENTA))
    wait_mode = os.getenv("MRCV_WAIT_FOR_RCS_HEDGE", "true").lower() == "true"
    mode_text = "Menunggu RCS Hedging (Standby)" if wait_mode else "Selalu Aktif (Mandiri)"
    start_msg = (
        f"🟢 SISTEM DIAKTIFKAN 🟢\n\n"
        f"🟢 [STRATEGI: MARUBOZU CANDLE SYSTEM (RECOVERY SYSTEM | MRCV)]\n\n"
        f"📊 Symbol: {symbol}\n"
        f"⚙️ Mode: {mode_text}"
    )
    send_mrcv_wa_notif(start_msg, "MRCV_START", include_header=False)
    
    # Audit Posisi Awal saat Startup
    startup_positions = mt5.positions_get(symbol=symbol)
    is_paused_by_hanging = False
    if startup_positions and len(startup_positions) > 0:
        print(cprint(f"⚠️ [MRCV] Terdeteksi {len(startup_positions)} posisi aktif di MT5 saat startup [{symbol}].", Colors.YELLOW))
        notify_mrcv_hanging_positions(symbol, list(startup_positions))
        is_paused_by_hanging = True
    else:
        print(cprint(f"✅ [MRCV] Audit Posisi: CLEAN (0 posisi pada {symbol}).", Colors.GREEN))
    
    last_hedge_status = False
    
    while True:
        try:
            is_enabled = os.getenv("MRCV_ENABLED", "true").lower() == "true"
            wait_for_hedge = os.getenv("MRCV_WAIT_FOR_RCS_HEDGE", "true").lower() == "true"
            
            if not is_enabled:
                if last_hedge_status:
                    last_hedge_status = False
                time.sleep(5)
                continue
            
            # Load RCS State (untuk tahu apakah sedang hedge)
            rcs_state.load_from_file(symbol)
            # Sayangnya RCS freeze_is_hedge cuma ada di runtime jika tidak di-save ke JSON.
            # Kita harus cek dari order/posisi MT5 jika file tidak update.
            # Alternatif: Cek apakah ada 2 posisi RCS berlawanan (Hedge)
            rcs_positions = mt5.positions_get(symbol=symbol)
            is_rcs_hedge = False
            rcs_floating = 0.0
            
            if rcs_positions:
                rcs_buy = 0
                rcs_sell = 0
                for p in rcs_positions:
                    if p.magic in rcs_magics:
                        rcs_floating += p.profit
                        if p.type == mt5.ORDER_TYPE_BUY:
                            rcs_buy += 1
                        elif p.type == mt5.ORDER_TYPE_SELL:
                            rcs_sell += 1
                if rcs_buy > 0 and rcs_sell > 0:
                    is_rcs_hedge = True
            
            if wait_for_hedge and not is_rcs_hedge:
                # Jika tidak ada hedge, MRCV idle
                if last_hedge_status:
                    last_hedge_status = False
                time.sleep(1)
                continue
                
            if is_rcs_hedge and not last_hedge_status:
                last_hedge_status = True
                msg = f"Tuyul RCS mengalami kondisi hedging pada symbol {symbol} dengan floating saat ini: ${rcs_floating:.2f}.\n🟢 Mesin *Marubozu Recovery (MRCV)* telah diaktifkan untuk memulai proses *recovery*!"
                send_mrcv_wa_notif(msg, "MRCV_HEDGE_DETECT")
                
            # --- CEK CLOSE ALL (TARGET PROFIT & EMERGENCY MAX LOSS) ---
            mrcv_floating = get_positions_profit(symbol, mrcv_magics)
            total_net = mrcv_state.cumulative_profit + mrcv_floating + rcs_floating
            
            target_profit = float(os.getenv("MRCV_TARGET_NET_PROFIT", "0.0"))
            max_loss = float(os.getenv("MRCV_MAX_NET_LOSS", "-15.0"))
            if max_loss > 0:
                max_loss = -max_loss

            # Cek apakah ada posisi aktif yang relevan untuk evaluasi Close ALL
            has_active_trades = is_rcs_hedge or (mrcv_state.phase in [MRCVPhase.ACTIVE, MRCVPhase.FREEZE]) or (mrcv_floating != 0.0 or rcs_floating != 0.0)

            # 1. KONDISI SUKSES: TARGET PROFIT TERCAPAI
            if has_active_trades and total_net >= target_profit:
                print(cprint(f"🎉 [MRCV] Target Profit Tercapai! Total Net: {total_net:+.2f} >= {target_profit:+.2f}. Melakukan Close All.", Colors.GREEN))
                success_msg = (
                    f"🎉 *[RECOVERY SUCCESS - CLOSE ALL]*\n"
                    f"Misi pemulihan berhasil! Total net profit telah mencapai target pemulihan.\n\n"
                    f"📊 *Rincian Keuangan:*\n"
                    f"• Total Net PnL: *${total_net:+.2f}*\n"
                    f"• Target Profit: ${target_profit:+.2f}\n"
                    f"• Floating MRCV: ${mrcv_floating:+.2f}\n"
                    f"• Floating RCS: ${rcs_floating:+.2f}\n"
                    f"• Kumulatif Profit MRCV: ${mrcv_state.cumulative_profit:+.2f}\n\n"
                    f"🧹 Seluruh posisi (RCS & MRCV) telah disapu bersih (Close ALL).\n"
                    f"🟢 Sistem di-reset dan kembali siaga normal."
                )
                send_mrcv_wa_notif(success_msg, "MRCV_SUCCESS", include_header=False)
                profit_jid = os.getenv("PROFIT_SIGNAL")
                if profit_jid:
                    send_mrcv_wa_notif(success_msg, "MRCV_SUCCESS", target_jid=profit_jid, include_header=False)

                close_all_positions(symbol, all_magics)
                # Reset MRCV State
                mrcv_state.reset_all(symbol)
                # Reset RCS State
                rcs_state.reset(symbol)
                time.sleep(2)
                continue

            # 2. KONDISI DARURAT: BATAS MAX LOSS TERCAPAI (EMERGENCY CUTLOSS REALTIME)
            if has_active_trades and total_net <= max_loss:
                print(cprint(f"🛑 [MRCV EMERGENCY CUTLOSS] Batas Max Loss Tercapai! Total Net: {total_net:+.2f} <= {max_loss:.2f}. Melakukan Close ALL.", Colors.RED))
                notify_mrcv_max_loss_close_all(
                    symbol=symbol,
                    total_net=total_net,
                    max_loss=max_loss,
                    mrcv_floating=mrcv_floating,
                    rcs_floating=rcs_floating,
                    cumulative_profit=mrcv_state.cumulative_profit
                )

                close_all_positions(symbol, all_magics)
                # Reset MRCV State
                mrcv_state.reset_all(symbol)
                # Reset RCS State
                rcs_state.reset(symbol)
                time.sleep(2)
                continue
            
            # --- CEK SIKLUS MRCV ---
            if mrcv_state.phase == MRCVPhase.ACTIVE:
                positions = mt5.positions_get(symbol=symbol)
                op1_active = False
                op2_active = False
                op3_active = False
                op2_pos = None
                op3_pos = None
                
                if positions:
                    for p in positions:
                        if p.ticket == mrcv_state.op1_ticket:
                            op1_active = True
                        if p.ticket == mrcv_state.op2_ticket:
                            op2_active = True
                            op2_pos = p
                        if p.ticket == mrcv_state.op3_ticket:
                            op3_active = True
                            op3_pos = p
                            
                # Deteksi OP2 Limit Terbuka / Aktif
                if op2_active and not mrcv_state.op2_filled and op2_pos:
                    mrcv_state.op2_filled = True
                    mrcv_state.save_to_file(symbol)
                    print(cprint(f"📉 [MRCV] OP2 LIMIT TERBUKA! Ticket #{op2_pos.ticket} di {op2_pos.price_open:.5f}", Colors.CYAN))
                    notify_mrcv_op2_filled(
                        symbol=symbol,
                        direction=mrcv_state.trigger_direction or "BUY",
                        ticket=op2_pos.ticket,
                        price=op2_pos.price_open,
                        tp_price=mrcv_state.tp2_price,
                        volume=op2_pos.volume
                    )

                # Deteksi OP3 Stop (Hedge) Terbuka -> Beralih ke PHASE_FREEZE & Hapus TP1 + TP2
                if op3_active and not mrcv_state.op3_filled and op3_pos:
                    mrcv_state.op3_filled = True
                    mrcv_state.phase = MRCVPhase.FREEZE
                    mrcv_state.save_to_file(symbol)
                    
                    # 1. Hapus TP pada OP1
                    if mrcv_state.op1_ticket:
                        remove_tp_from_position(mrcv_state.op1_ticket)
                    
                    # 2. Hapus TP pada OP2 (jika sudah aktif) atau Batalkan jika masih Pending Limit
                    if op2_active and mrcv_state.op2_ticket:
                        remove_tp_from_position(mrcv_state.op2_ticket)
                    elif mrcv_state.op2_ticket:
                        cancel_pending_order_rcs(mrcv_state.op2_ticket)
                    
                    total_freeze_floating = get_positions_profit(symbol, mrcv_magics)
                    op3_direction = "SELL" if mrcv_state.trigger_direction == "BUY" else "BUY"
                    print(cprint(f"❄️ [MRCV] OP3 HEDGE AKTIF! Beralih ke PHASE_FREEZE. TP1 & TP2 telah dihapus! Floating: ${total_freeze_floating:.2f}", Colors.YELLOW))
                    notify_mrcv_op3_freeze(
                        symbol=symbol,
                        op3_direction=op3_direction,
                        ticket=op3_pos.ticket,
                        price=op3_pos.price_open,
                        volume=op3_pos.volume,
                        floating_freeze=total_freeze_floating
                    )
                    time.sleep(1)
                    continue

                # Jika OP1 sudah tidak aktif (hanya saat belum masuk FREEZE), berarti kena TP1 normal
                if not op1_active and mrcv_state.op1_ticket:
                    prof1 = get_closed_profit(mrcv_state.op1_ticket)
                    # Jika OP2 tadinya aktif tapi sekarang mati, ambil juga profitnya
                    prof2 = get_closed_profit(mrcv_state.op2_ticket) if mrcv_state.op2_ticket and not op2_active else 0.0
                    
                    total_prof = prof1 + prof2
                    mrcv_state.cumulative_profit += total_prof
                    mrcv_state.save_to_file(symbol)
                    
                    print(cprint(f"💰 [MRCV] Siklus Selesai! Profit siklus: {total_prof:+.2f} | Kumulatif: {mrcv_state.cumulative_profit:+.2f}", Colors.CYAN))
                    
                    img_url = generate_and_upload_mrcv_screenshot(symbol, mrcv_state)
                    
                    # Kirim notifikasi siklus selesai ke grup PROFIT/LOSS + screenshot
                    notify_mrcv_cycle_done(
                        symbol=symbol,
                        cycle_profit=total_prof,
                        cumulative_profit=mrcv_state.cumulative_profit,
                        rcs_floating=rcs_floating,
                        is_wait_rcs=wait_for_hedge,
                        screenshot_url=img_url
                    )
                    
                    # Hapus pending order sisa (OP2 & OP3 stop yang belum tersentuh)
                    cleanup_pending_orders(mrcv_state)
                    
                    mrcv_state.reset_cycle()
                    time.sleep(1)
                    continue

            # --- MONITORING KONDISI FREEZE MRCV ---
            if mrcv_state.phase == MRCVPhase.FREEZE:
                # Periksa apakah posisi MRCV telah ditutup manual oleh trader di MT5
                positions = mt5.positions_get(symbol=symbol)
                mrcv_pos_count = 0
                if positions:
                    for p in positions:
                        if p.magic in mrcv_magics:
                            mrcv_pos_count += 1
                
                # Jika seluruh posisi MRCV telah ditutup (0 posisi tersisa), unfreeze kembali ke IDLE
                if mrcv_pos_count == 0:
                    print(cprint(f"☀️ [MRCV] UNFREEZE! Seluruh posisi MRCV telah ditutup ({symbol}). Kembali ke IDLE.", Colors.GREEN))
                    mrcv_state.reset_cycle()
                    time.sleep(1)
                    continue

            # --- CARI TRIGGER MARUBOZU (HANYA JIKA IDLE & TIDAK ADA POSISI TERGANTUNG) ---
            if mrcv_state.phase == MRCVPhase.IDLE:
                all_current_positions = mt5.positions_get(symbol=symbol)
                hanging_positions = []
                
                if all_current_positions:
                    if not wait_for_hedge:
                        # Mode Mandiri: Setiap posisi aktif di broker memblokir siklus baru saat IDLE
                        hanging_positions = list(all_current_positions)
                    else:
                        # Mode Recovery: Posisi manual / non-RCS memblokir siklus
                        hanging_positions = [p for p in all_current_positions if p.magic not in rcs_magics and p.magic not in mrcv_magics]
                
                if len(hanging_positions) > 0:
                    if not is_paused_by_hanging:
                        is_paused_by_hanging = True
                        print(cprint(f"⚠️ [MRCV] Terdeteksi {len(hanging_positions)} posisi aktif pada {symbol}. Siklus Marubozu di-pause sampai posisi ditutup manual.", Colors.YELLOW))
                        notify_mrcv_hanging_positions(symbol, hanging_positions)
                    time.sleep(1)
                    continue
                else:
                    if is_paused_by_hanging:
                        is_paused_by_hanging = False
                        print(cprint(f"✅ [MRCV] Semua posisi pada {symbol} telah bersih (0 posisi). Siklus Marubozu aktif kembali.", Colors.GREEN))
                        notify_mrcv_positions_cleared(symbol)

                candle = get_closed_candles(symbol, tf_label=tf_str)
                if candle is None:
                    time.sleep(1)
                    continue

                current_candle_time = str(candle.get("timestamp"))

                # Proteksi Anti-Duplicate: Jangan eksekusi candle yang sama jika siklus sebelumnya selesai lebih cepat
                if mrcv_state.last_processed_candle_time == current_candle_time:
                    time.sleep(1)
                    continue
                    
                point = mt5.symbol_info(symbol).point
                
                trigger = pattern_detector.detect(candle, None, point)
                if trigger:
                    # Valid Marubozu baru ditemukan pada candle baru
                    mrcv_state.last_processed_candle_time = current_candle_time
                    mrcv_state.save_to_file(symbol)
                    process_marubozu_trigger(symbol, candle, mrcv_state)
                    
            time.sleep(1)
            
        except KeyboardInterrupt:
            stop_msg = (
                f"🛑 SISTEM DIMATIKAN 🛑\n\n"
                f"🛑 [STRATEGI: MARUBOZU CANDLE SYSTEM (RECOVERY SYSTEM | MRCV)]\n\n"
                f"📊 Symbol: {symbol}\n"
                f"Status: Mesin telah dihentikan secara manual."
            )
            send_mrcv_wa_notif(stop_msg, "MRCV_STOP", include_header=False)
            time.sleep(2) # Beri waktu untuk thread mengirim notifikasi WA sebelum terminal mati
            print(cprint("\n🛑 MRCV Bot dihentikan oleh user.", Colors.YELLOW))
            break
        except Exception as e:
            print(cprint(f"⚠️ Error di MRCV loop: {e}", Colors.RED))
            time.sleep(5)
