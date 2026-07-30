# =====================================================
# itr_main.py
# Entry point untuk menjalankan Infinity Trailing Reversal
# =====================================================

from strategies.infinity_trailing.itr_engine import run_itr_bot

if __name__ == "__main__":
    run_itr_bot()

    
    # =====================================================
    # strategies/infinity_trailing/itr_engine.py
    # Logika utama untuk Infinity Trailing Reversal (Tick-by-tick)
    # =====================================================

    import time
    import MetaTrader5 as mt5
    from config.itr_config import ITRConfig
    from config.mt5_config import MT5Config
    from mt5_client import init_mt5, shutdown_mt5

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
        print(f"🔹 Pending Dist : {itr_cfg.pending_distance_pts} pts")
        print(f"🔹 Trailing Step: {itr_cfg.trailing_step_pts} pts")
        print(f"🔹 Magic Number : {itr_cfg.magic_number}")
        print("="*50)

        # MT5 Order Helpers
        def send_market_order(action_str: str, price: float):
            order_type = mt5.ORDER_TYPE_BUY if action_str == "BUY" else mt5.ORDER_TYPE_SELL
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(itr_cfg.lot_size),
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": itr_cfg.magic_number,
                "comment": "ITR_OP1",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ OP1 {action_str} Berhasil di harga {res.price}")
                return res
            else:
                print(f"❌ OP1 Gagal: {res.comment if res else 'Unknown'}")
                return None

        def send_stop_order(action_str: str, price: float):
            order_type = mt5.ORDER_TYPE_BUY_STOP if action_str == "BUY" else mt5.ORDER_TYPE_SELL_STOP
            req = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": float(itr_cfg.lot_size),
                "type": order_type,
                "price": price,
                "magic": itr_cfg.magic_number,
                "comment": "ITR_OP2",
                "type_time": mt5.ORDER_TIME_GTC,
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ OP2 {action_str} STOP Berhasil dipasang di harga {price}")
                return res
            else:
                print(f"❌ OP2 Gagal: {res.comment if res else 'Unknown'}")
                return None

        def modify_pending_order(ticket: int, new_price: float):
            req = {
                "action": mt5.TRADE_ACTION_MODIFY,
                "order": ticket,
                "price": new_price,
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"🔄 OP2 Trailed ke harga baru: {new_price}")
                return True
            return False

        def close_position(pos):
            action_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            price = tick.bid if action_type == mt5.ORDER_TYPE_SELL else tick.ask
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": symbol,
                "volume": pos.volume,
                "type": action_type,
                "price": price,
                "deviation": 20,
                "magic": itr_cfg.magic_number,
                "comment": "ITR_REVERSAL_CLOSE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"🚪 OP1 Lama (Ticket: {pos.ticket}) Berhasil ditutup.")
                return True
            else:
                print(f"❌ Gagal tutup OP1 Lama: {res.comment if res else 'Unknown'}")
                return False

        try:
            while True:
                # Dapatkan informasi symbol (point, tick)
                info = mt5.symbol_info(symbol)
                tick = mt5.symbol_info_tick(symbol)
                if info is None or tick is None:
                    time.sleep(1)
                    continue

                point = info.point

                # Ambil semua positions dan orders milik ITR
                all_pos = mt5.positions_get(symbol=symbol) or []
                all_ord = mt5.orders_get(symbol=symbol) or []
                
                my_pos = [p for p in all_pos if p.magic == itr_cfg.magic_number]
                my_ord = [o for o in all_ord if o.magic == itr_cfg.magic_number]

                # KASUS 1: Kosong (Awal mula atau kena SL / TP manual)
                if len(my_pos) == 0 and len(my_ord) == 0:
                    print("=======================================")
                    print(f"🚀 Memulai Cycle Baru: OP1 {itr_cfg.initial_direction}")
                    price = tick.ask if itr_cfg.initial_direction == "BUY" else tick.bid
                    res_op1 = send_market_order(itr_cfg.initial_direction, price)
                    if res_op1:
                        # Pasang OP2
                        op2_dir = "SELL" if itr_cfg.initial_direction == "BUY" else "BUY"
                        dist = itr_cfg.pending_distance_pts * point
                        op2_price = res_op1.price - dist if op2_dir == "SELL" else res_op1.price + dist
                        send_stop_order(op2_dir, op2_price)

                # KASUS 2: Reversal Terjadi (OP2 tersentuh sehingga menjadi Posisi Aktif)
                # Hasilnya: Ada 2 posisi aktif (karena OP1 lama belum di-close)
                elif len(my_pos) == 2:
                    print("=======================================")
                    print("🔄
