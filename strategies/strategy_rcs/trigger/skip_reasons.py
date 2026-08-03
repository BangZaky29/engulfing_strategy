# =====================================================
# strategies/strategy_rcs/trigger/skip_reasons.py
# Kumpulan definisi skip reasons untuk log dan notifikasi
# =====================================================

def skip_not_engulfing_or_ict() -> str:
    return "Candle bukan Engulfing dan bukan ICT pattern"

def skip_range_too_small(pts: int, min_pts: int) -> str:
    return f"Range candle ({pts} pts) terlalu kecil (< {min_pts} pts)"

def skip_range_too_large(pts: int, max_pts: int) -> str:
    return f"Range candle ({pts} pts) terlalu besar (> {max_pts} pts)"

def skip_body_too_small(pct: float, min_pct: float) -> str:
    return f"Body candle ({pct:.1f}%) terlalu kecil (< {min_pct:.1f}%)"

def skip_body_too_large(pct: float, max_pct: float) -> str:
    return f"Body candle ({pct:.1f}%) terlalu besar (> {max_pct:.1f}%)"

def skip_spread_too_high(spread: int, max_spread: int) -> str:
    return f"Spread saat ini ({spread} pts) terlalu tinggi (> {max_spread} pts)"

def skip_ema_distance_too_far(dist: int, max_dist: int) -> str:
    return f"Jarak Open ke EMA ({dist} pts) terlalu jauh (> {max_dist} pts)"

def skip_ema_wrong_side(direction: str) -> str:
    return f"Open candle berada di sisi EMA yang salah untuk setup {direction}"

def skip_ema_not_crossed(direction: str) -> str:
    return f"Close candle gagal menembus EMA ke arah setup {direction}"
