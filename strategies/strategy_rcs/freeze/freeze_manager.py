# =====================================================
# strategies/strategy_rcs/freeze/freeze_manager.py
# Logika masuk dan keluar dari State Freeze
# Terintegrasi dengan PositionTracker untuk deteksi OP manual
# =====================================================

import datetime
import MetaTrader5 as mt5
from config.rcs_config import RCSConfig
from strategies.strategy_rcs.rcs_state import RCSState


def get_total_floating_rcs(state: RCSState, tracker=None, symbol: str = "") -> float:
    """
    Hitung total floating profit/loss dari semua posisi aktif RCS.
    Termasuk OP manual jika PositionTracker tersedia.
    
    Args:
        state: RCS state dengan ticket OP1/OP2/OP3
        tracker: PositionTracker instance (opsional, untuk include OP manual)
        symbol: Symbol pair (wajib jika tracker diberikan)
    """
    # 1. Hitung floating dari OP sistem (OP1, OP2, OP3)
    pos1 = mt5.positions_get(ticket=state.op1_ticket) if state.op1_ticket else None
    pos2 = mt5.positions_get(ticket=state.op2_ticket) if state.op2_ticket else None
    pos3 = mt5.positions_get(ticket=state.op3_ticket) if state.op3_ticket else None
    
    total = 0.0
    if pos1 and len(pos1) > 0:
        total += pos1[0].profit
    if pos2 and len(pos2) > 0:
        total += pos2[0].profit
    if pos3 and len(pos3) > 0:
        total += pos3[0].profit

    # 2. Tambahkan floating dari OP manual (jika tracker tersedia)
    if tracker and symbol:
        manual_floating = tracker.get_manual_floating(symbol)
        total += manual_floating

    return total


def enter_freeze(state: RCSState, config: RCSConfig, tracker=None, symbol: str = ""):
    """
    Jalankan snapshot sebelum masuk freeze.
    
    Args:
        state: RCS state
        config: RCS config
        tracker: PositionTracker (opsional, untuk include OP manual di snapshot)
        symbol: Symbol pair
    """
    state.freeze_start_floating_usd = get_total_floating_rcs(state, tracker, symbol)
    state.freeze_start_time = datetime.datetime.now()


def check_unfreeze(symbol: str, state: RCSState, config: RCSConfig, tracker=None) -> bool:
    """
    Cek apakah semua posisi sudah ditutup sehingga bisa unfreeze.
    
    PENTING: Sekarang juga memeriksa OP manual!
    Unfreeze baru terjadi jika:
    1. OP1, OP2, OP3 sudah tidak ada di posisi aktif (seperti sebelumnya)
    2. Semua OP manual di symbol ini juga sudah ditutup (BARU)
    
    Ini mencegah sistem melanjutkan siklus baru saat trader
    masih punya OP recovery manual yang terbuka.
    """
    # 1. Cek posisi sistem (OP1, OP2, OP3)
    pos1 = mt5.positions_get(ticket=state.op1_ticket) if state.op1_ticket else None
    pos2 = mt5.positions_get(ticket=state.op2_ticket) if state.op2_ticket else None
    pos3 = mt5.positions_get(ticket=state.op3_ticket) if state.op3_ticket else None
    
    system_clear = not pos1 and not pos2 and not pos3

    # 2. Cek posisi manual (dari PositionTracker)
    if tracker:
        manual_clear = not tracker.has_manual_positions(symbol)
    else:
        # Fallback: jika tracker tidak tersedia, anggap clear (backward compatible)
        manual_clear = True
    
    # Unfreeze hanya jika KEDUA-DUANYA clear
    return system_clear and manual_clear
