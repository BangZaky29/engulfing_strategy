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
    from utils.colors import cprint, Colors
    
    path = os.getenv("ACC1_PATH", "")
    is_portable = True

    # --- Dynamic Single-Account Optimization ---
    is_multi = os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true"
    if is_multi:
        accounts_str = os.getenv("ACCOUNTS_LIST", "ACC1")
        rcs_targets = os.getenv("RCS_TARGET_ACCOUNTS", accounts_str)
        mrcv_targets = os.getenv("MRCV_TARGET_ACCOUNTS", accounts_str)
        
        rcs_list = [x.strip() for x in rcs_targets.split(",") if x.strip()]
        mrcv_list = [x.strip() for x in mrcv_targets.split(",") if x.strip()]
        
        unique_targets = set(rcs_list + mrcv_list)
        
        if len(unique_targets) == 1:
            target_acc = list(unique_targets)[0]
            target_path = os.getenv(f"{target_acc}_PATH", "")
            if target_path and os.path.exists(target_path):
                path = target_path
                print(cprint(f"⚡ [OPTIMASI] Deteksi single-account target ({target_acc}). Dispatcher dimatikan, koneksi beralih langsung (Zero-Delay Mode)!", Colors.GREEN))
                os.environ["MULTI_ACCOUNT_ENABLED"] = "false"
    # -------------------------------------------

    if path and os.path.exists(path):
        init_ok = mt5.initialize(path=path, portable=is_portable)
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
