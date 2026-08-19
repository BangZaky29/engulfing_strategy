# =====================================================
# mt5_client/connection.py
# MT5 initialize & shutdown
# =====================================================

import MetaTrader5 as mt5
from config.mt5_config import MT5Config
from mt5_client.error_helper import get_last_error


def init_mt5(cfg: MT5Config | None = None, strategy_name: str | None = None) -> bool:
    """
    Inisialisasi MT5 dan select symbol.
    Returns True jika berhasil.
    """
    if cfg is None:
        cfg = MT5Config()

    import os
    import sys
    from utils.colors import cprint, Colors
    
    # Auto-detect strategy_name jika tidak diberikan
    if not strategy_name:
        cmd_line = " ".join(sys.argv).lower()
        if "rcs" in cmd_line:
            strategy_name = "RCS"
        elif "mrcv" in cmd_line:
            strategy_name = "MRCV"
        elif "itr" in cmd_line:
            strategy_name = "ITR"
        elif "scanner" in cmd_line:
            strategy_name = "SCANNER"
        elif "main.py" in cmd_line:
            strategy_name = "MALING"
        else:
            strategy_name = "RCS"

    path = ""
    is_multi = os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true"
    accounts_str = os.getenv("ACCOUNTS_LIST", "ACC1,ACC2,ACC3")
    
    # Ambil target account untuk strategi spesifik ini
    target_env_key = f"{strategy_name.upper()}_TARGET_ACCOUNTS"
    target_str = os.getenv(target_env_key, accounts_str)
    target_keys = [a.strip() for a in target_str.split(",") if a.strip()]

    if target_keys:
        primary_acc = target_keys[0]
        target_path = os.getenv(f"{primary_acc}_PATH", "")
        if target_path and os.path.exists(target_path):
            path = target_path
            print(cprint(f"🎯 Connection target [{strategy_name}]: {primary_acc} ({path})", Colors.CYAN))
        
        # Jika strategi ini hanya menargetkan 1 akun, aktifkan Zero-Delay Mode
        if len(target_keys) == 1 and is_multi:
            print(cprint(f"⚡ [OPTIMASI] Deteksi single-account target ({primary_acc}) untuk {strategy_name}. Dispatcher dimatikan, koneksi beralih langsung (Zero-Delay Mode)!", Colors.GREEN))
            os.environ["MULTI_ACCOUNT_ENABLED"] = "false"

    if not path:
        path = os.getenv("ACC1_PATH", "")

    # Inisialisasi MT5 dengan fallback bertahap untuk mencegah IPC Error (-10001)
    init_ok = False
    if path and os.path.exists(path):
        # Attempt 1: dengan path dan portable=True
        init_ok = mt5.initialize(path=path, portable=True, timeout=15000)
        # Attempt 2: dengan path tanpa portable
        if not init_ok:
            init_ok = mt5.initialize(path=path, timeout=15000)

    # Attempt 3: initialize tanpa path (connect ke terminal MT5 aktif)
    if not init_ok:
        init_ok = mt5.initialize(timeout=15000)

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
