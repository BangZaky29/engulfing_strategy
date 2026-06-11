# =====================================================
# mt5_client/connection.py
# MT5 initialize & shutdown
# =====================================================

import MetaTrader5 as mt5
from config.mt5_config import MT5Config


def init_mt5(cfg: MT5Config = None) -> bool:
    """
    Inisialisasi MT5 dan select symbol.
    Returns True jika berhasil.
    """
    if cfg is None:
        cfg = MT5Config()

    if not mt5.initialize():
        print(f"❌ Gagal inisialisasi MT5: {mt5.last_error()}")
        return False
    print("✅ MT5 terhubung.")

    if not mt5.symbol_select(cfg.symbol, True):
        print(f"❌ Gagal memilih simbol {cfg.symbol}: {mt5.last_error()}")
        mt5.shutdown()
        return False
    print(f"✅ Symbol {cfg.symbol} aktif.")

    return True


def shutdown_mt5():
    """Shutdown MT5 connection."""
    mt5.shutdown()
    print("🛑 MT5 shutdown selesai.")
