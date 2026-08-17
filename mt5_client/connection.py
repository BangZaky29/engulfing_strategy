# =====================================================
# mt5_client/connection.py
# MT5 initialize & shutdown
# =====================================================

import MetaTrader5 as mt5
from config.mt5_config import MT5Config
from mt5_client.error_helper import get_last_error


def init_mt5(cfg: MT5Config | None = None) -> bool:
    """
    Inisialisasi MT5 dan select symbol.
    Returns True jika berhasil.
    """
    if cfg is None:
        cfg = MT5Config()

    import os
    path = os.getenv("ACC1_PATH", "")
    if path and os.path.exists(path):
        init_ok = mt5.initialize(path=path, portable=True)
    else:
        init_ok = mt5.initialize()

    if not init_ok:
        print(f"❌ Gagal inisialisasi MT5: {get_last_error()}")
        return False
    print("✅ MT5 terhubung.")

    for sym in cfg.symbols:
        if not mt5.symbol_select(sym, True):  # type: ignore
            print(f"❌ Gagal memilih simbol {sym}: {get_last_error()}")
            mt5.shutdown()  # type: ignore
            return False
        print(f"✅ Symbol {sym} aktif.")

    return True


def shutdown_mt5():
    """Shutdown MT5 connection."""
    mt5.shutdown()  # type: ignore
    print("🛑 MT5 shutdown selesai.")
