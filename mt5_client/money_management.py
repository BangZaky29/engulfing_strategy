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
    Mengambil rincian akun MT5 lengkap untuk logging & notifikasi startup.
    Returns:
        dict dengan kunci: balance, equity, funds_used, source_type, dynamic_lot, is_dynamic
    """
    enabled = os.getenv("DYNAMIC_LOT_ENABLED", "true").lower() == "true"
    source_type = os.getenv("DYNAMIC_LOT_SOURCE", "BALANCE").upper()
    acc = mt5.account_info()

    if not acc:
        return {
            "balance": 0.0,
            "equity": 0.0,
            "funds_used": 0.0,
            "source_type": source_type,
            "dynamic_lot": fallback_lot,
            "is_dynamic": enabled
        }

    balance = acc.balance
    equity = acc.equity
    funds = equity if source_type == "EQUITY" else balance

    if not enabled:
        return {
            "balance": balance,
            "equity": equity,
            "funds_used": funds,
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
        "balance": balance,
        "equity": equity,
        "funds_used": funds,
        "source_type": source_type,
        "dynamic_lot": final_lot,
        "is_dynamic": True
    }
