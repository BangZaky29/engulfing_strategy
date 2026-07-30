# =====================================================
# strategies/infinity_trailing/itr_engine.py
# Logika utama untuk Infinity Trailing Reversal (Tick-by-tick)
# =====================================================

import time
import datetime
import uuid
import MetaTrader5 as mt5
from config.itr_config import ITRConfig
from config.mt5_config import MT5Config
from mt5_client import init_mt5, shutdown_mt5
from database.supabase_client import get_supabase
from strategies.infinity_trailing.itr_order_manager import (
    send_market_order, send_stop_order, modify_pending_order, close_position
)

def run_itr_bot():
    """
    Main loop khusus untuk bot Infinity Trailing Reversal.
    Ini harus berjalan di thread atau process terpisah karena butuh loop tick-by-tick (sangat cepat).
    """
    itr_cfg = ITRConfig()
    
    if not itr_cfg.enabled:
        print("❌ Infinity Trailing Reversal (ITR) dinonaktifkan di .env (ITR_ENABLED=false)")
        return

    # Initialize MT5
    mt5_cfg = MT5Config()
    if not init_mt5(mt5_cfg):
        return

    symbol = itr_cfg.symbol
    if not mt5.symbol_select(symbol, True):
        print(f"❌ Gagal select symbol {symbol}")
        shutdown_mt5()
        return

    print(f"\n🚀 Memulai INFINITY TRAILING REVERSAL (ITR) Bot...")
    print(f"🔹 Symbol       : {symbol}")
    print(f"🔹 Lot Size     : {itr_cfg.lot_size}")
    print(f"🔹 Init Dir     : {itr_cfg.initial_direction}")
    print(f"🔹 Pending Dist : ${itr_cfg.pending_distance_usd}")
    print(f"🔹 Trailing Step: ${itr_cfg.trailing_step_usd}")
    print(f"🔹 Magic Number : {itr_cfg.magic_number}")
    print("="*50)
    print("="*50)

    try:
        supabase = get_supabase()
        if itr_cfg.group_sar:
            try:
                supabase.table('wa_outbox').insert({
                    'source_table': 'itr_system',
                    'event_type': 'ITR_STARTUP',
                    'group_jid': itr_cfg.group_sar,
                    'message_type': 'TEXT',
                    'message': '🤖 Bot ITR baru saja dijalankan di terminal.\nStatus saat ini: *MENUNGGU PERINTAH*.\nSilakan ketik "Aktifkan" untuk mulai mengeksekusi market.',
                    'dedupe_key': f'itr_startup_{int(time.time())}'
                }).execute()
            except Exception as e:
                print(f"⚠️ Gagal mengirim WA startup: {e}")

        session_start_time = datetime.datetime.now()
        cooldown_until = None
        current_direction = itr_cfg.initial_direction

        last_state_check_time = 0
        cached_command_state = 'PAUSED'

        while True:
            # === POLL PERINTAH WHATSAPP ===
            now_ts = time.time()
            if now_ts - last_state_check_time > 3.0:
                last_state_check_time = now_ts
                try:
                    res = supabase.table('itr_command_state').select('status').eq('id', 'main_itr').execute()
                    if res.data and len(res.data) > 0:
                        cached_command_state = res.data[0]['status']
                except Exception as e:
                    pass
            
            if cached_command_state == 'PAUSED':
                time.sleep(1.0)
                continue
            # Pengecekan Cooldown (Opsi 2)
            if cooldown_until is not None:
                if datetime.datetime.now() < cooldown_until:
                    time.sleep(1)
                    continue
                else:
                    print(f"✅ Cooldown selesai! Memulai sesi baru...")
                    cooldown_until = None
                    session_start_time = datetime.datetime.now()
                    current_direction = itr_cfg.initial_direction # Reset direction

            # Dapatkan informasi symbol (point, tick)
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if info is None or tick is None:
                time.sleep(1)
                continue

            point = info.point

            # Kalkulasi USD ke Pts
            tick_size = info.trade_tick_size if info.trade_tick_size > 0 else point
            tick_value = info.trade_tick_value if info.trade_tick_value > 0 else 1.0
            usd_per_point = (point / tick_size) * tick_value * itr_cfg.lot_size
            if usd_per_point <= 0:
                usd_per_point = 0.1 # fallback aman
            
            dist_pts = itr_cfg.pending_distance_usd / usd_per_point
            step_pts = itr_cfg.trailing_step_usd / usd_per_point

            # Ambil semua positions dan orders milik ITR
            all_pos = mt5.positions_get(symbol=symbol) or []
            all_ord = mt5.orders_get(symbol=symbol) or []
            
            my_pos = [p for p in all_pos if p.magic == itr_cfg.magic_number]
            my_ord = [o for o in all_ord if o.magic == itr_cfg.magic_number]

            # KASUS 1: Kosong (Awal mula atau kena SL / TP manual)
            if len(my_pos) == 0 and len(my_ord) == 0:
                print("=======================================")
                print(f"🚀 Memulai Cycle Baru: OP1 {current_direction}")
                price = tick.ask if current_direction == "BUY" else tick.bid
                res_op1 = send_market_order(symbol, current_direction, price, itr_cfg.lot_size, itr_cfg.magic_number)
                if res_op1:
                    # Pasang OP2
                    op2_dir = "SELL" if current_direction == "BUY" else "BUY"
                    dist = dist_pts * point
                    op2_price = res_op1.price - dist if op2_dir == "SELL" else res_op1.price + dist
                    send_stop_order(symbol, op2_dir, op2_price, itr_cfg.lot_size, itr_cfg.magic_number)
                    time.sleep(1.0) # BUG FIX: Sinkronisasi server
                continue

            # KASUS 2: Reversal Terjadi (OP2 tersentuh sehingga menjadi Posisi Aktif)
            # Hasilnya: Ada 2 posisi aktif (karena OP1 lama belum di-close)
            elif len(my_pos) == 2:
                print("=======================================")
                print("🔄 Reversal Triggered! (OP2 Tersentuh)")
                # Urutkan berdasarkan waktu buka (yang tertua = OP1 lama)
                my_pos.sort(key=lambda x: x.time)
                old_pos = my_pos[0]
                new_pos = my_pos[1]

                # 1. Close OP1 lama
                if close_position(symbol, old_pos, itr_cfg.magic_number):
                    # 2. Pasang OP2 baru untuk new_pos
                    new_pos_dir = "BUY" if new_pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                    op2_dir = "SELL" if new_pos_dir == "BUY" else "BUY"
                    dist = dist_pts * point
                    op2_price = new_pos.price_open - dist if op2_dir == "SELL" else new_pos.price_open + dist
                    send_stop_order(symbol, op2_dir, op2_price, itr_cfg.lot_size, itr_cfg.magic_number)
                    time.sleep(1.0) # BUG FIX: Sinkronisasi server
                continue

            # KASUS 3: Normal Running (1 OP1 aktif)
            elif len(my_pos) == 1 and len(my_ord) == 1:
                pos = my_pos[0]
                ord = my_ord[0]
                
                pos_dir = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                dist = dist_pts * point
                step = step_pts * point

                if pos_dir == "BUY":
                    # OP2 adalah SELL STOP, max_price = harga OP2 + dist
                    max_reached = ord.price_open + dist
                    if tick.bid > max_reached:
                        diff = tick.bid - max_reached
                        if diff >= step:
                            steps_to_move = int(diff // step)
                            new_max = max_reached + (steps_to_move * step)
                            new_ord_price = new_max - dist
                            modify_pending_order(ord.ticket, new_ord_price)

                elif pos_dir == "SELL":
                    # OP2 adalah BUY STOP, min_price = harga OP2 - dist
                    min_reached = ord.price_open - dist
                    if tick.ask < min_reached:
                        diff = min_reached - tick.ask
                        if diff >= step:
                            steps_to_move = int(diff // step)
                            new_min = min_reached - (steps_to_move * step)
                            new_ord_price = new_min + dist
                            modify_pending_order(ord.ticket, new_ord_price)

            # KASUS 4: Ada OP1 tapi OP2 (Pending) hilang (mungkin dihapus manual)
            elif len(my_pos) == 1 and len(my_ord) == 0:
                print("⚠️ Peringatan: OP2 Pending Order tidak ditemukan! Memasang ulang...")
                pos = my_pos[0]
                pos_dir = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                op2_dir = "SELL" if pos_dir == "BUY" else "BUY"
                dist = dist_pts * point
                # Kita pasang berdasar current price agar aman
                base_price = tick.bid if pos_dir == "BUY" else tick.ask
                op2_price = base_price - dist if op2_dir == "SELL" else base_price + dist
                send_stop_order(symbol, op2_dir, op2_price, itr_cfg.lot_size, itr_cfg.magic_number)
                time.sleep(1.0) # BUG FIX: Sinkronisasi server
                continue

            # KASUS 5: Ada Pending Order tapi Posisi kosong (OP1 mungkin ditutup manual)
            elif len(my_pos) == 0 and len(my_ord) > 0:
                print("🧹 OP1 tidak ada, membersihkan Pending Order sisa...")
                for o in my_ord:
                    req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                    mt5.order_send(req)
                time.sleep(1.0) # BUG FIX: Sinkronisasi server
                continue

            # ==========================================
            # EVALUASI OPSI 1 & 2 (Jika sedang running 1 OP1 aktif)
            # ==========================================
            if len(my_pos) == 1:
                pos = my_pos[0]
                
                # OPSI 1: Cycle Target (Berdasarkan Profit OP1 berjalan)
                if itr_cfg.opsi1_enabled and pos.profit >= itr_cfg.opsi1_target_usd:
                    print("=======================================")
                    print(f"🎯 OPSI 1: Cycle Target ${itr_cfg.opsi1_target_usd} TERCAPAI! Profit saat ini: ${pos.profit}")
                    close_position(symbol, pos, itr_cfg.magic_number)
                    for o in my_ord:
                        mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                    
                    # Set arah OP baru mengikuti posisi yang profit ini!
                    current_direction = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                    print(f"➡️ Melanjutkan tren: Arah OP berikutnya diset menjadi {current_direction}")
                    
                    if itr_cfg.group_sar:
                        try:
                            supabase.table('wa_outbox').insert({
                                'source_table': 'itr_system',
                                'event_type': 'ITR_OPSI1',
                                'group_jid': itr_cfg.group_sar,
                                'message_type': 'TEXT',
                                'message': f'🎯 [OPSI 1] Cycle Target ${itr_cfg.opsi1_target_usd} TERCAPAI!\nProfit diamankan: ${pos.profit:.2f}\n➡️ Lanjut arah tren berikutnya: {current_direction}',
                                'dedupe_key': f'itr_opsi1_{int(time.time())}_{uuid.uuid4().hex[:8]}'
                            }).execute()
                        except:
                            pass

                    time.sleep(1.0)
                    continue
                
                # OPSI 2: Session Target (Berdasarkan PnL Tertutup sejak awal Sesi)
                if itr_cfg.opsi2_enabled:
                    # Ambil data deals (transaksi yang sudah diclose)
                    from_time = session_start_time
                    to_time = datetime.datetime.now()
                    deals = mt5.history_deals_get(from_time, to_time)
                    
                    session_pnl = 0.0
                    if deals:
                        session_pnl = sum([d.profit for d in deals if d.magic == itr_cfg.magic_number])
                    
                    # Tambahkan dengan floating saat ini juga?
                    # Tidak, "perhitungan profit dan loss yang terjadi akan dikalkulasikan". 
                    # Kita asumsikan total session_pnl = tertutup + floating.
                    total_pnl = session_pnl + pos.profit

                    if total_pnl >= itr_cfg.opsi2_profit_target_usd or total_pnl <= itr_cfg.opsi2_loss_target_usd:
                        status = 'PROFIT_TARGET_HIT' if total_pnl >= itr_cfg.opsi2_profit_target_usd else 'LOSS_TARGET_HIT'
                        print("=======================================")
                        print(f"🛑 OPSI 2: Session Limit Tercapai! PnL Sesi: ${total_pnl:.2f} | Status: {status}")
                        
                        # Close semuanya
                        close_position(symbol, pos, itr_cfg.magic_number)
                        for o in my_ord:
                            mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
                        
                        # Simpan log ke Supabase
                        try:
                            supabase = get_supabase()
                            supabase.table('itr_session_history').insert({
                                'symbol': symbol,
                                'session_start_time': session_start_time.astimezone(datetime.timezone.utc).isoformat(),
                                'total_profit_usd': total_pnl,
                                'status': status,
                                'cooldown_minutes': itr_cfg.opsi2_cooldown_minutes
                            }).execute()
                            print(f"✅ Riwayat Opsi 2 berhasil disimpan ke Supabase.")
                            
                            if itr_cfg.group_sar:
                                session_end_time = datetime.datetime.now()
                                session_end_str = session_end_time.strftime('%Y-%m-%d_%H-%M-%S')
                                resume_time = session_end_time + datetime.timedelta(minutes=itr_cfg.opsi2_cooldown_minutes)
                                resume_str = resume_time.strftime('%H:%M:%S')
                                
                                msg_text = (
                                    f"🛑 [OPSI 2] SESSION LIMIT TERCAPAI!\n\n"
                                    f"Trading session_{session_end_str} sudah berakhir karena telah mencapai batas target/loss sesi harian.\n\n"
                                    f"📊 *PnL Sesi:* ${total_pnl:.2f}\n"
                                    f"🔖 *Status:* {status}\n\n"
                                    f"⏳ Mesin ITR akan istirahat dan mendinginkan suhu selama {itr_cfg.opsi2_cooldown_minutes} menit.\n"
                                    f"Sistem akan otomatis melanjutkan pertempuran kembali pada pukul *{resume_str}*."
                                )
                                
                                supabase.table('wa_outbox').insert({
                                    'source_table': 'itr_system',
                                    'event_type': 'ITR_OPSI2',
                                    'group_jid': itr_cfg.group_sar,
                                    'message_type': 'TEXT',
                                    'message': msg_text,
                                    'dedupe_key': f'itr_opsi2_{int(time.time())}_{uuid.uuid4().hex[:8]}'
                                }).execute()
                        except Exception as e:
                            print(f"⚠️ Gagal menyimpan riwayat/kirim WA: {e}")

                        # Trigger Cooldown
                        cooldown_until = datetime.datetime.now() + datetime.timedelta(minutes=itr_cfg.opsi2_cooldown_minutes)
                        print(f"⏳ Bot akan istirahat selama {itr_cfg.opsi2_cooldown_minutes} menit. Aktif kembali pada {cooldown_until.strftime('%H:%M:%S')}")
                        time.sleep(1.0)
                        continue

            # Tidur sebentar agar tidak makan CPU (100ms)
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n⏹️ ITR Bot dimatikan oleh user (Ctrl+C).")
    except Exception as e:
        print(f"\n❌ Error di ITR Bot: {e}")
        import traceback
        traceback.print_exc()
    finally:
        shutdown_mt5()
