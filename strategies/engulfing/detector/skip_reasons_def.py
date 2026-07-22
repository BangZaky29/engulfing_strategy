# =====================================================
# strategies/engulfing/detector/skip_reasons_def.py
# Definisi daftar alasan skip (Skip Reasons) agar mudah
# dipantau dan di-maintain di satu tempat.
# =====================================================

def skip_c1_doji() -> str:
    return "C1 is Doji, trigger candle too weak"

def skip_c2_doji_invalid() -> str:
    return "C2 is Doji, invalid engulfing (Hanya diizinkan di Filter B)"

def skip_pattern_size_invalid_b(pts: int) -> str:
    return f"Pattern size invalid ({pts} pts) untuk Filter B"

def skip_pattern_size_invalid(pts: int) -> str:
    return f"Pattern size invalid ({pts} pts)"

def skip_grade_below_min(grade: str, min_grade: str) -> str:
    return f"Grade {grade} di bawah batas {min_grade}"

def skip_ema_distance_too_close_m5(dist: int, min_pts: int) -> str:
    return f"EMA Distance terlalu dekat, H1 candle c1 trigger ({dist} pts < {min_pts} min) [INVALID]"

def skip_ema_distance_too_far_m5(dist: int, max_pts: int) -> str:
    return f"EMA Distance terlalu jauh, H1 candle c1 trigger ({dist} pts > {max_pts} max) [VALID-OVEREXTENDED]"

def skip_ema_distance_too_close_h1(dist: int, min_pts: int) -> str:
    return f"EMA Distance terlalu dekat, H1 C1 ({dist} pts < {min_pts} min) [INVALID]"

def skip_ema_distance_too_far_h1(dist: int, max_pts: int) -> str:
    return f"EMA Distance terlalu jauh, H1 C1 ({dist} pts > {max_pts} max) [VALID-OVEREXTENDED]"

def skip_tfm_not_strong(status: str, reason_detail: str) -> str:
    if reason_detail:
        return f"TF Monitor: status {status} bukan STRONG ({reason_detail})"
    return f"TF Monitor: status {status} bukan STRONG"

def skip_tfm_direction_mismatch(bias: str) -> str:
    return f"TF Monitor: Arah M5 berlawanan dengan Bias ({bias})"

'''
========================================================================================
PENJELASAN ALASAN SKIP OLEH SISTEM
========================================================================================

Berikut adalah rangkuman (dalam bahasa awam) mengenai hal-hal apa saja 
yang menyebabkan sebuah sinyal ditolak / di-skip oleh bot:

1. C1 / C2 Doji:
   - Sinyal ditolak jika Candle 1 (Trigger) bentuk tubuhnya terlalu tipis (Doji).
   - Sinyal juga ditolak jika Candle 2 (Candle sebelumnya) bentuk tubuhnya terlalu tipis,
     kecuali saat menggunakan mode eksekusi "Filter B".

2. Pattern Size (Ukuran Pola) Invalid:
   - Sinyal ditolak karena total tinggi pola Engulfing (High ke Low) 
     terlalu kecil (tidak memenuhi standar poin).

3. Grade / Kualitas Setup (Filter A):
   - Sinyal ditolak jika nilai rapor kualitas candle-nya (B+, C, D) berada 
     di bawah batas minimum yang diatur di dalam sistem (min_grade).

4. EMA Distance (Jarak ke Garis EMA 20):
   - Sinyal ditolak jika jarak open candle ke garis EMA terlalu dekat (< MIN batas .env).
   - Sinyal ditolak jika jarak open candle ke garis EMA terlalu jauh / overextended (> MAX batas .env).
   - Ini berlaku baik saat mencari trigger di M5 maupun di H1.

5. TF Monitor (Kondisi Multi-Timeframe):
   - Sinyal ditolak jika konfirmasi arah tren besar (TF H1 & M15) ternyata belum selaras ("bukan STRONG").
   - Sinyal ditolak jika arah trigger kecil (M5) nekat melawan bias/arah tren besar di H1 & M15.
========================================================================================
'''
