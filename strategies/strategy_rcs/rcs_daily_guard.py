# =====================================================
# strategies/strategy_rcs/rcs_daily_guard.py
# Pengaman Daily Money Management untuk RCS (TUYUL COPET)
# =====================================================

from datetime import datetime, time
import MetaTrader5 as mt5
from config.rcs_config import RCSConfig

def get_rcs_today_closed_pnl(config: RCSConfig) -> float:
    """Hitung total PnL bersih dari transaksi yang tertutup hari ini dari broker."""
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)
    
    deals = mt5.history_deals_get(today_start, now)
    if not deals:
        return 0.0
        
    total_pnl = 0.0
    target_magics = (config.magic_op1, config.magic_op2, config.magic_op3)
    
    for deal in deals:
        if deal.symbol in config.symbols and deal.magic in target_magics:
            total_pnl += deal.profit
            total_pnl += deal.swap
            total_pnl += deal.commission
            
    return total_pnl

def check_rcs_daily_target(config: RCSConfig) -> tuple[bool, str]:
    """
    Cek apakah target profit/loss harian RCS sudah tersentuh.
    Return (is_allowed, reason).
    """
    if not config.rcs_daily_target_enabled:
        return True, ""

    today_pnl = get_rcs_today_closed_pnl(config)

    if today_pnl >= config.rcs_daily_profit_target_usd:
        msg = f"🏆 TARGET PROFIT HARIAN TERCAPAI! PnL Hari ini (${today_pnl:.2f}) >= Target (+${config.rcs_daily_profit_target_usd:.2f})"
        return False, msg

    if today_pnl <= -config.rcs_daily_loss_target_usd:
        msg = f"🛑 LIMIT LOSS HARIAN TERSENTUH! PnL Hari ini (${today_pnl:.2f}) <= Limit (-${config.rcs_daily_loss_target_usd:.2f})"
        return False, msg

    return True, ""

def get_rcs_daily_guard_status_text(config: RCSConfig) -> str:
    """Return status teks untuk logging startup."""
    if not config.rcs_daily_target_enabled:
        return f"DISABLED (Target: +${config.rcs_daily_profit_target_usd:.2f} / -${config.rcs_daily_loss_target_usd:.2f})"
    
    today_pnl = get_rcs_today_closed_pnl(config)
    return f"ENABLED (PnL Hari ini: ${today_pnl:.2f} | Profit Target: +${config.rcs_daily_profit_target_usd:.2f} | Loss Limit: -${config.rcs_daily_loss_target_usd:.2f})"
