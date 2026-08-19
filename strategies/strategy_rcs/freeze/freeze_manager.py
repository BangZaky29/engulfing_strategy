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
    Mendukung Multi-Account MT5 (ACC1, ACC2, ACC3).
    """
    import os
    if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
        from mt5_client.multi_account_dispatcher import get_multi_account_positions_profit
        rcs_magics = [901001, 901002, 901003, 221160935, 221160936, 221160937]
        total = get_multi_account_positions_profit("RCS", symbol, rcs_magics)
        if tracker and symbol:
            manual_floating = tracker.get_manual_floating(symbol)
            total += manual_floating
        return total

    def get_pos(ticket):
        if not ticket: return None
        pos = mt5.positions_get(ticket=ticket)
        if pos is None:
            err = mt5.last_error()
            if err and err[0] == 4753: return ()
            # Jika error koneksi, jangan return () agar tidak dikira 0
            return None 
        return pos

    pos1 = get_pos(state.op1_ticket)
    pos2 = get_pos(state.op2_ticket)
    pos3 = get_pos(state.op3_ticket)
    
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
    Mendukung Multi-Account MT5 (ACC1, ACC2, ACC3).
    """
    import os
    if os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true":
        from mt5_client.multi_account_dispatcher import check_multi_account_tickets_active
        tickets_dict = dict(getattr(state, 'multi_account_tickets', {}))
        ma_status = check_multi_account_tickets_active("RCS", symbol, tickets_dict)
        
        # Cek apakah ada posisi sistem yang masih aktif di akun target
        active_pos_count = 0
        for acc_k, acc_v in ma_status.get("accounts", {}).items():
            active_pos_count += len(acc_v.get("positions_map", {}))
            
        system_clear = (active_pos_count == 0)
    else:
        def check_pos(ticket):
            if not ticket: return True # Clear
            pos = mt5.positions_get(ticket=ticket)
            if pos is None:
                err = mt5.last_error()
                if err and err[0] == 4753: return True # Benar-benar clear
                print(f"⚠️ FreezeManager: Gagal baca posisi MT5 untuk tiket {ticket}. Error: {err}")
                return False # Error, jangan anggap clear
            return len(pos) == 0

        system_clear = check_pos(state.op1_ticket) and check_pos(state.op2_ticket) and check_pos(state.op3_ticket)

    # 2. Cek posisi manual (dari PositionTracker)
    if tracker:
        manual_clear = not tracker.has_manual_positions(symbol)
    else:
        # Fallback: jika tracker tidak tersedia, anggap clear (backward compatible)
        manual_clear = True
    
    # Unfreeze hanya jika KEDUA-DUANYA clear
    return system_clear and manual_clear
