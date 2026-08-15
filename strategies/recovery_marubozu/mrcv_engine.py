import os
import time
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from utils.colors import Colors, cprint

from mt5_client.connection import init_mt5
from mt5_client.candle_fetcher import get_closed_candles
from indicatorInfo.triggerInfo.scanner.patterns.marubozu import MarubozuPattern

from strategies.strategy_rcs.rcs_state import RCSState
from strategies.strategy_rcs.rcs_order_manager import close_position_rcs, cancel_pending_order_rcs
from strategies.recovery_marubozu.mrcv_state import MRCVState, MRCVPhase
from strategies.recovery_marubozu.mrcv_core import process_marubozu_trigger, cleanup_pending_orders
from strategies.recovery_marubozu.mrcv_notifier import send_mrcv_wa_notif, generate_and_upload_mrcv_screenshot

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
    send_mrcv_wa_notif(
        f"Mesin Marubozu Recovery telah dihidupkan.\n📊 Symbol: {symbol}\n⚙️ Mode: {mode_text}",
        "MRCV_START"
    )
    
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
                
            # --- CEK CLOSE ALL ---
            mrcv_floating = get_positions_profit(symbol, mrcv_magics)
            total_net = mrcv_state.cumulative_profit + mrcv_floating + rcs_floating
            
            if is_rcs_hedge and total_net >= 0.0:
                print(cprint(f"🎉 [MRCV] Target Tercapai! Total Net: {total_net:.2f}. Melakukan Close All.", Colors.GREEN))
                send_mrcv_wa_notif(
                    f"Misi penyelamatan berhasil! Total profit dari Marubozu Recovery telah menutupi kerugian / floating minus dari Tuyul RCS.\n\nSeluruh posisi (RCS & MRCV) telah dibersihkan secara paksa (Sapu Bersih).\n🟢 Tuyul RCS kini di-reset dan kembali berjalan normal.\nTotal Net Profit: ${total_net:.2f}",
                    "MRCV_SUCCESS"
                )
                close_all_positions(symbol, all_magics)
                # Reset MRCV State
                mrcv_state.reset_all(symbol)
                # Reset RCS State (rcs_core akan otomatis baca posisi kosong dan reset)
                rcs_state.reset(symbol)
                time.sleep(2)
                continue
            
            # --- CEK SIKLUS MRCV ---
            if mrcv_state.phase == MRCVPhase.ACTIVE:
                # Periksa apakah posisi OP1 sudah close (kena TP/SL)
                positions = mt5.positions_get(symbol=symbol)
                op1_active = False
                op2_active = False
                op3_active = False
                
                if positions:
                    for p in positions:
                        if p.ticket == mrcv_state.op1_ticket:
                            op1_active = True
                        if p.ticket == mrcv_state.op2_ticket:
                            op2_active = True
                        if p.ticket == mrcv_state.op3_ticket:
                            op3_active = True
                            
                # Jika OP1 sudah tidak aktif, berarti sudah kena TP1
                if not op1_active and mrcv_state.op1_ticket:
                    prof1 = get_closed_profit(mrcv_state.op1_ticket)
                    # Jika OP2 atau OP3 tadinya aktif tapi sekarang mati, ambil juga profitnya
                    prof2 = get_closed_profit(mrcv_state.op2_ticket) if mrcv_state.op2_ticket and not op2_active else 0.0
                    prof3 = get_closed_profit(mrcv_state.op3_ticket) if mrcv_state.op3_ticket and not op3_active else 0.0
                    
                    total_prof = prof1 + prof2 + prof3
                    mrcv_state.cumulative_profit += total_prof
                    mrcv_state.save_to_file(symbol)
                    
                    print(cprint(f"💰 [MRCV] Siklus Selesai! Profit siklus: {total_prof:.2f} | Kumulatif: {mrcv_state.cumulative_profit:.2f}", Colors.CYAN))
                    
                    img_url = generate_and_upload_mrcv_screenshot(symbol, mrcv_state)
                    profit_jid = os.getenv("PROFIT_SIGNAL") if total_prof >= 0 else os.getenv("LOSS_SIGNAL")
                    msg = f"Putaran recovery Marubozu sukses tertutup.\nProfit putaran ini: ${total_prof:.2f}.\n\n📊 *Status Recovery:*\nTotal Kumulatif MRCV: ${mrcv_state.cumulative_profit:.2f}\nFloating RCS saat ini: ${rcs_floating:.2f}\n⏳ *Mesin akan terus mencari trigger sampai kumulatif profit melebihi floating RCS.*"
                    
                    # Send to profit group with image
                    send_mrcv_wa_notif(msg, "MRCV_CYCLE_DONE", target_jid=profit_jid, media_url=img_url)
                    
                    # Send text only to MRCV group
                    send_mrcv_wa_notif(msg, "MRCV_CYCLE_DONE")
                    
                    # Hapus pending order sisa
                    cleanup_pending_orders(mrcv_state)
                    # Tutup jika ada OP2/OP3 yang terlanjur aktif tapi belum TP/SL
                    close_all_positions(symbol, mrcv_magics)
                    
                    mrcv_state.reset_cycle()
                    time.sleep(1)
                    continue

            # --- CARI TRIGGER MARUBOZU ---
            if mrcv_state.phase == MRCVPhase.IDLE:
                candle = get_closed_candles(symbol, tf_label=tf_str)
                if candle is None:
                    time.sleep(1)
                    continue
                    
                point = mt5.symbol_info(symbol).point
                
                trigger = pattern_detector.detect(candle, None, point)
                if trigger:
                    # Valid Marubozu
                    process_marubozu_trigger(symbol, candle, mrcv_state)
                    
            time.sleep(1)
            
        except KeyboardInterrupt:
            send_mrcv_wa_notif("🛑 Mesin Marubozu Recovery telah DIMATIKAN secara manual.", "MRCV_STOP")
            time.sleep(2) # Beri waktu untuk thread mengirim notifikasi WA sebelum terminal mati
            print(cprint("\n🛑 MRCV Bot dihentikan oleh user.", Colors.YELLOW))
            break
        except Exception as e:
            print(cprint(f"⚠️ Error di MRCV loop: {e}", Colors.RED))
            time.sleep(5)
