# =====================================================
# app/initializer.py
# Modul untuk inisialisasi bot, validasi config, dan print banner.
# =====================================================

from config.settings import validate_env
from config.mt5_config import MT5Config, EMAConfig
from config.execution_config import ExecutionConfig
from config.filter_c_config import FilterCConfig
from mt5_client import init_mt5
from utils.colors import Colors, cprint

def print_banner(mt5_cfg: MT5Config, ema_cfg: EMAConfig, exec_cfg: ExecutionConfig):
    print("=" * 60)
    print("🕯️  ENGULFING PATTERN SCANNER (MODULAR)")
    print(f"   Symbols   : {', '.join(mt5_cfg.symbols)}")
    
    # Tampilkan timeframe eksekusi spesifik per mata uang
    tf_str_list = [f"{sym}({mt5_cfg.get_symbol_timeframe(sym)})" for sym in mt5_cfg.symbols]
    print(f"   Execute TF: {', '.join(tf_str_list)}")
    print(f"   Info TFs  : {', '.join(mt5_cfg.info_timeframes)}")
    print(f"   EMA       : {ema_cfg.labels['fast']} / {ema_cfg.labels['slow']}")
    print(f"   Database  : Supabase (metaTrader5)")
    print("=" * 60)


def print_tfm_trigger_status(fc_cfg: FilterCConfig):
    for tf in ["M5", "M15", "H1"]:
        print(cprint(f"   TF {tf}", Colors.CYAN))
        
        db_val = fc_cfg.get_use_dominan_break(tf)
        eng_val = fc_cfg.get_use_engulfing(tf)
        mar_val = fc_cfg.get_use_marubozu(tf)
        pin_val = fc_cfg.get_use_pinbar(tf)
        ict_val = fc_cfg.get_use_ict(tf)
        
        print(cprint(f"   * DB = {'Aktif (True)' if db_val else 'Non-Aktif (False)'}", Colors.CYAN))
        print(cprint(f"   * Engulfing = {'Aktif (True)' if eng_val else 'Non-Aktif (False)'}", Colors.CYAN))
        print(cprint(f"   * Marobosho = {'Aktif (True)' if mar_val else 'Non-Aktif (False)'}", Colors.CYAN))
        print(cprint(f"   * Pinbar = {'Aktif (True)' if pin_val else 'Non-Aktif (False)'}", Colors.CYAN))
        print(cprint(f"   * ITC = {'Aktif (True)' if ict_val else 'Non-Aktif (False)'}", Colors.CYAN))


def startup_checks(
    mt5_cfg: MT5Config, 
    ema_cfg: EMAConfig, 
    exec_cfg: ExecutionConfig, 
    engulf_cfg, 
    fc_cfg: FilterCConfig | None
) -> bool:
    """
    Validasi env, cetak banner, dan inisialisasi MT5.
    Returns: bool (True jika sukses, False jika gagal)
    """
    try:
        validate_env()
    except EnvironmentError as e:
        print(e)
        return False

    print_banner(mt5_cfg, ema_cfg, exec_cfg)

    if engulf_cfg.filter_c_tfm_enabled and fc_cfg:
        print(cprint("📡 [TF Monitor] Filter C AKTIF — H1 Bias + M15 Confirm + M5 Trigger", Colors.CYAN))
        print(cprint(f"   EMA Filter: {'ON' if fc_cfg.use_ema_filter else 'OFF'} | Lookback: {fc_cfg.trigger_lookback_bars} bars", Colors.CYAN))
        print(cprint(f"   Blocking: {'ON (WAIT/LATE = skip)' if fc_cfg.filter_c_blocking else 'OFF (tag only)'}", Colors.CYAN))
        print_tfm_trigger_status(fc_cfg)

    # --- Execution Config Info ---
    op_mode_str  = "LIMIT (Pending Order)" if exec_cfg.use_limit_orders else "MARKET (Langsung Execute)"
    sl_mode_str  = f"Dinamis — {exec_cfg.sl_pct_b}% ekor candle H1 trigger (EXECUTION_SL_PCT_B)"
    tp_mode_str  = (
        f"Statis USD — Target dinamis per mata uang (default ${exec_cfg.tp_target_usd_b:.2f})"
        if getattr(exec_cfg, 'tp_mode_b', 'PCT') == "USD"
        else f"Dinamis PCT — {exec_cfg.tp_pct}% jarak OP→SL (EXECUTION_TP_PCT)"
    )
    lot_per_sym  = ", ".join(f"{sym}={exec_cfg.get_lot_size(sym)}" for sym in mt5_cfg.symbols)
    tp_per_sym   = ", ".join(f"{sym}=${exec_cfg.get_tp_target_usd_b(sym)}" for sym in mt5_cfg.symbols)
    
    print(cprint("⚙️  [Execution Config]", Colors.CYAN))
    print(cprint(f"   OP Mode : {op_mode_str}", Colors.CYAN))
    print(cprint(f"   SL Mode : {sl_mode_str}", Colors.CYAN))
    print(cprint(f"   TP Mode : {tp_mode_str}", Colors.CYAN))
    if getattr(exec_cfg, 'tp_mode_b', 'PCT') == "USD":
        print(cprint(f"   TP USD  : {tp_per_sym}", Colors.CYAN))
    print(cprint(f"   Lot     : {lot_per_sym}", Colors.CYAN))

    # Inisialisasi MT5
    if not init_mt5(mt5_cfg):
        return False

    return True
