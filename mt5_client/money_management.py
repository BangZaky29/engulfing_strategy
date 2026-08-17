# =====================================================
# mt5_client/money_management.py
# Modul Manajemen Risiko & Lot Dinamis Berdasar Dana MT5
# =====================================================

import os
import MetaTrader5 as mt5
from utils.colors import cprint, Colors

def get_dynamic_op1_lot(fallback_lot: float = 0.01) -> tuple[float, float, str]:
    """
    Kalkulasi Lot OP1 secara dinamis berdasarkan total dana (Balance/Equity) akun MT5.
    
    Aturan Dana:
    - Dana < $200  -> 0.01 lot (Batas minimum modal kecil)
    - Dana >= $200 -> (Dana // 100) * 0.01 lot
      Contoh:
      - $250    -> 0.02 lot
      - $1,250  -> 0.12 lot
      - $10,150 -> 1.01 lot
      - $20,000 -> 2.00 lot

    Returns:
        (lot_size, funds_amount, source_type)
    """
    enabled = os.getenv("DYNAMIC_LOT_ENABLED", "true").lower() == "true"
    if not enabled:
        return fallback_lot, 0.0, "FIXED"

    acc = mt5.account_info()
    if not acc:
        return fallback_lot, 0.0, "FALLBACK"

    source_type = os.getenv("DYNAMIC_LOT_SOURCE", "BALANCE").upper()
    funds = acc.equity if source_type == "EQUITY" else acc.balance

    if funds < 200.0:
        calculated_lot = 0.01
    else:
        calculated_lot = round(int(funds // 100) * 0.01, 2)

    final_lot = max(0.01, calculated_lot)
    return final_lot, funds, source_type

def get_account_funds_info(fallback_lot: float = 0.01) -> dict:
    """
    Mengambil rincian akun MT5 lengkap (Saldo, Equity, Tipe Akun REAL/DEMO, Login, Server)
    untuk logging & notifikasi startup.
    """
    enabled = os.getenv("DYNAMIC_LOT_ENABLED", "true").lower() == "true"
    source_type = os.getenv("DYNAMIC_LOT_SOURCE", "BALANCE").upper()
    acc = mt5.account_info()

    if not acc:
        return {
            "account_type": "UNKNOWN ⚪",
            "account_type_raw": "UNKNOWN",
            "account_number": 0,
            "server": "-",
            "balance": 0.0,
            "equity": 0.0,
            "funds_used": 0.0,
            "source_type": source_type,
            "dynamic_lot": fallback_lot,
            "is_dynamic": enabled
        }

    # Deteksi Tipe Akun (REAL / DEMO / CONTEST)
    trade_mode = getattr(acc, "trade_mode", None)
    if trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL:
        account_type = "REAL 🔴"
        account_type_raw = "REAL"
    elif trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO:
        account_type = "DEMO 🟡"
        account_type_raw = "DEMO"
    elif trade_mode == mt5.ACCOUNT_TRADE_MODE_CONTEST:
        account_type = "CONTEST 🔵"
        account_type_raw = "CONTEST"
    else:
        account_type = "UNKNOWN ⚪"
        account_type_raw = "UNKNOWN"

    account_number = acc.login
    server = acc.server
    balance = acc.balance
    equity = acc.equity
    funds = equity if source_type == "EQUITY" else balance

    margin_free = getattr(acc, "margin_free", 0.0)
    margin_used = getattr(acc, "margin", 0.0)
    margin_level = getattr(acc, "margin_level", 0.0)
    leverage = getattr(acc, "leverage", 0)

    if margin_used <= 0.0 or margin_level == 0.0 or margin_level is None:
        health_status = "SEHAT 🟢 (0 Margin)"
    elif margin_level > 1000.0:
        health_status = f"{margin_level:,.1f}% SEHAT 🟢"
    elif 300.0 <= margin_level <= 1000.0:
        health_status = f"{margin_level:,.1f}% WASPADA 🟡"
    else:
        health_status = f"{margin_level:,.1f}% BAHAYA 🔴"

    term = mt5.terminal_info()
    ping_us = getattr(term, "ping_last", 0) if term else 0
    ping_ms = round(ping_us / 1000.0, 1) if ping_us > 0 else 0.0

    if ping_ms <= 0.0:
        ping_str = "N/A"
    elif ping_ms < 50.0:
        ping_str = f"{ping_ms:.0f} ms ⚡ (Fast)"
    elif ping_ms < 150.0:
        ping_str = f"{ping_ms:.0f} ms 🟢 (Normal)"
    else:
        ping_str = f"{ping_ms:.0f} ms 🟡 (Slow)"

    trade_allowed = getattr(term, "trade_allowed", False) if term else False
    autotrading = "ALLOWED 🟢" if trade_allowed else "DISABLED 🔴"

    if not enabled:
        return {
            "account_type": account_type,
            "account_type_raw": account_type_raw,
            "account_number": account_number,
            "server": server,
            "balance": balance,
            "equity": equity,
            "funds_used": funds,
            "margin_free": margin_free,
            "margin_used": margin_used,
            "margin_level": margin_level,
            "health_status": health_status,
            "leverage": f"1:{leverage}" if leverage > 0 else "-",
            "ping_str": ping_str,
            "autotrading": autotrading,
            "source_type": "FIXED",
            "dynamic_lot": fallback_lot,
            "is_dynamic": False
        }

    if funds < 200.0:
        calculated_lot = 0.01
    else:
        calculated_lot = round(int(funds // 100) * 0.01, 2)

    final_lot = max(0.01, calculated_lot)
    return {
        "account_type": account_type,
        "account_type_raw": account_type_raw,
        "account_number": account_number,
        "server": server,
        "balance": balance,
        "equity": equity,
        "funds_used": funds,
        "margin_free": margin_free,
        "margin_used": margin_used,
        "margin_level": margin_level,
        "health_status": health_status,
        "leverage": f"1:{leverage}" if leverage > 0 else "-",
        "ping_str": ping_str,
        "autotrading": autotrading,
        "source_type": source_type,
        "dynamic_lot": final_lot,
        "is_dynamic": True
    }

def get_scaled_max_loss(base_max_loss: float = -15.0, op1_lot: float = 0.01) -> float:
    """
    Menghitung batas Emergency Cutloss secara dinamis proporsional dengan Lot OP1.
    Base default: -$15.00 untuk lot 0.01.
    Contoh:
    - op1_lot = 0.01 -> -$15.00
    - op1_lot = 0.10 -> -$150.00
    - op1_lot = 1.00 -> -$1,500.00
    """
    scaling_enabled = os.getenv("DYNAMIC_RISK_SCALING", "true").lower() == "true"
    if not scaling_enabled or op1_lot <= 0.0:
        if base_max_loss > 0:
            return -base_max_loss
        return base_max_loss

    negative_base = -abs(base_max_loss)
    multiplier = op1_lot / 0.01
    scaled_loss = round(negative_base * multiplier, 2)
    return scaled_loss
