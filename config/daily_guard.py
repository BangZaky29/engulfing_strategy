# =====================================================
# config/daily_guard.py
# Pengaman Daily Money Management untuk Engulfing Strategy (TUYUL MALING)
# =====================================================

import os
from datetime import datetime, time
import MetaTrader5 as mt5
from mt5_client.money_management import get_scaled_max_loss

DAILY_TARGET_ENABLED: bool = os.getenv("DAILY_TARGET_ENABLED", "false").lower() == "true"
DAILY_PROFIT_TARGET_USD: float = float(os.getenv("DAILY_PROFIT_TARGET_USD", "5.0"))
DAILY_LOSS_TARGET_USD: float = float(os.getenv("DAILY_LOSS_TARGET_USD", "5.0"))

def get_engulfing_today_closed_pnl(magic_numbers: list[int] | None = None) -> float:
    """Hitung total PnL bersih dari transaksi Engulfing yang tertutup hari ini dari broker."""
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)
    
    deals = mt5.history_deals_get(today_start, now)
    if not deals:
        return 0.0
        
    total_pnl = 0.0
    for deal in deals:
        if magic_numbers is None or deal.magic in magic_numbers:
            total_pnl += deal.profit
            total_pnl += deal.swap
            total_pnl += deal.commission
            
    return total_pnl

def check_daily_target(magic_numbers: list[int] | None = None) -> tuple[bool, str]:
    """
    Cek apakah target profit/loss harian Engulfing sudah tersentuh.
    Return (is_allowed, reason).
    """
    if not DAILY_TARGET_ENABLED:
        return True, ""

    today_pnl = get_engulfing_today_closed_pnl(magic_numbers)
    scaled_loss_limit = abs(get_scaled_max_loss(-DAILY_LOSS_TARGET_USD, 0.01))

    profit_lock_enabled = os.getenv("DAILY_PROFIT_LOCK_ENABLED", "false").lower() == "true"
    if profit_lock_enabled and today_pnl >= DAILY_PROFIT_TARGET_USD:
        msg = f"🏆 TARGET PROFIT HARIAN ENGULFING TERCAPAI! PnL Hari ini (${today_pnl:.2f}) >= Target (+${DAILY_PROFIT_TARGET_USD:.2f})"
        return False, msg

    loss_lock_enabled = os.getenv("DAILY_LOSS_LOCK_ENABLED", "true").lower() == "true"
    if loss_lock_enabled and today_pnl <= -scaled_loss_limit:
        msg = f"🛑 LIMIT LOSS HARIAN ENGULFING TERSENTUH! PnL Hari ini (${today_pnl:.2f}) <= Limit (-${scaled_loss_limit:.2f})"
        return False, msg

    return True, ""

def get_daily_guard_status_text(magic_numbers: list[int] | None = None) -> str:
    """Return status teks untuk logging startup."""
    scaled_loss_limit = abs(get_scaled_max_loss(-DAILY_LOSS_TARGET_USD, 0.01))
    loss_lock = os.getenv("DAILY_LOSS_LOCK_ENABLED", "true").lower() == "true"
    profit_lock = os.getenv("DAILY_PROFIT_LOCK_ENABLED", "false").lower() == "true"

    if not DAILY_TARGET_ENABLED:
        return f"DISABLED (Loss Lock: {'ON 🔒' if loss_lock else 'OFF 🔓'} | Profit Lock: {'ON 🔒' if profit_lock else 'OFF 🔓'})"
    
    today_pnl = get_engulfing_today_closed_pnl(magic_numbers)
    loss_str = f"Loss Lock: -${scaled_loss_limit:.2f} ({'ON 🔒' if loss_lock else 'OFF 🔓'})"
    profit_str = f"Profit Lock: +${DAILY_PROFIT_TARGET_USD:.2f} ({'ON 🔒' if profit_lock else 'OFF 🔓'})"
    return f"ENABLED (PnL Hari ini: ${today_pnl:.2f} | {loss_str} | {profit_str})"
