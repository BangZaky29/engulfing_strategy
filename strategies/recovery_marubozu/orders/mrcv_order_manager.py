import time
import MetaTrader5 as mt5
from utils.colors import Colors, cprint
from strategies.strategy_rcs.rcs_order_manager import close_position_rcs, cancel_pending_order_rcs

def close_all_positions(symbol: str, magics: list[int]):
    """
    Eksekutor Utama (Master Commander) untuk Close ALL.
    Fungsi ini ditangani secara eksklusif oleh MRCV agar tidak terjadi bentrok
    dengan siklus harian RCS.
    """
    print(cprint(f"🧹 [MRCV] Memulai eksekusi CLOSE ALL untuk symbol {symbol}...", Colors.YELLOW))
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        positions = mt5.positions_get(symbol=symbol)
        active_pos_count = 0
        if positions:
            for p in positions:
                if p.magic in magics:
                    active_pos_count += 1
                    close_position_rcs(p.ticket)
                    
        # Hapus juga pending order
        orders = mt5.orders_get(symbol=symbol)
        active_order_count = 0
        if orders:
            for o in orders:
                if o.magic in magics:
                    active_order_count += 1
                    cancel_pending_order_rcs(o.ticket)
                    
        # Jika sejak awal loop tidak ada posisi sama sekali, berarti sudah bersih
        if active_pos_count == 0 and active_order_count == 0:
            if attempt > 1:
                print(cprint(f"✅ [MRCV] Eksekusi CLOSE ALL berhasil setelah retry {attempt}x.", Colors.GREEN))
            return
            
        # Beri jeda agar server MT5 selesai memproses
        time.sleep(0.5)
        
        # Cek ulang untuk verifikasi sisa posisi
        positions_now = mt5.positions_get(symbol=symbol)
        orders_now = mt5.orders_get(symbol=symbol)
        
        remaining_pos = [p for p in positions_now if p.magic in magics] if positions_now else []
        remaining_ord = [o for o in orders_now if o.magic in magics] if orders_now else []
        
        if len(remaining_pos) == 0 and len(remaining_ord) == 0:
            return
            
        if attempt < max_retries:
            print(cprint(f"⚠️ [MRCV] Requote / Slippage terdeteksi! Terdapat {len(remaining_pos)} posisi dan {len(remaining_ord)} pending order yang tersisa. Mencoba ulang (Retry {attempt}/{max_retries})...", Colors.YELLOW))
            
    print(cprint(f"❌ [CRITICAL WARNING] Gagal menutup semua posisi setelah {max_retries}x percobaan. Harap periksa terminal MT5 secara manual!", Colors.RED))
