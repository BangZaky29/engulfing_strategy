# =====================================================
# strategies/strategy_rcs/trigger/level_calculator.py
# Logika kalkulasi level OP1, OP2, OP3
# =====================================================

from config.rcs_config import RCSConfig

def calculate_levels(c_close: float, risk_range: float, direction: str, config: RCSConfig) -> dict:
    """
    Hitung level harga untuk OP1, OP2, dan OP3 berdasarkan risk_range.
    """
    if direction == "BUY":
        # Untuk BUY, target entry (OP1) ada di bawah close, 
        # OP2 ada di bawahnya lagi, dst (pullback entry).
        # Jika INSTANT_ZERO, op1_level tetap dihitung (untuk acuan TP dll), 
        # meski aktualnya dieksekusi market.
        
        op1_dist = risk_range * (config.entry_percent / 100.0)
        op2_dist = risk_range * (config.op2_percent / 100.0)
        op3_dist = risk_range * (config.op3_percent / 100.0)
        
        op1_level = c_close - op1_dist
        op2_level = c_close - op2_dist
        op3_level = c_close - op3_dist
        
    else:
        # Untuk SELL, target entry (OP1) ada di atas close
        op1_dist = risk_range * (config.entry_percent / 100.0)
        op2_dist = risk_range * (config.op2_percent / 100.0)
        op3_dist = risk_range * (config.op3_percent / 100.0)
        
        op1_level = c_close + op1_dist
        op2_level = c_close + op2_dist
        op3_level = c_close + op3_dist
        
    return {
        "op1_level": op1_level,
        "op2_level": op2_level,
        "op3_level": op3_level
    }
