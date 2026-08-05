# =====================================================
# config/company_daily_guard.py
# TARGET HARIAN PERUSAHAAN — Berlaku untuk SEMUA TUYUL
#
# Menghitung total PnL hari ini dari SEMUA deal yang sudah
# TERTUTUP (DEAL_ENTRY_OUT), difilter per magic number tiap Tuyul.
#
# Akumulasi berlaku untuk SEMUA pair mata uang per Tuyul:
#   - TUYUL MALING: semua pair yang pakai EXECUTION_MAGIC_NUMBER
#   - TUYUL COPET : semua pair per symbol (XAUUSD, NASDAQ-100, dll)
#                   masing-masing dengan magic number OP1/OP2/OP3-nya
#
# Cara kerja:
#   1. Ambil semua history deal hari ini dari MT5 via history_deals_get()
#   2. Filter hanya deal yang ENTRY = DEAL_ENTRY_OUT (posisi sudah closed)
#   3. Kelompokkan berdasarkan magic number → Maling atau Copet
#   4. Akumulasi profit + swap + commission per deal ticket
#
# Jika target tercapai → SEMUA Tuyul berhenti execute.
# Reset otomatis keesokan harinya pukul 00:00.
# =====================================================

import os
import re
from datetime import datetime, time, date
from typing import Optional
import MetaTrader5 as mt5

from utils.colors import cprint, Colors

# =====================================================
# Load dari .env
# =====================================================
COMPANY_DAILY_TARGET_ENABLED: bool = (
    os.getenv("COMPANY_DAILY_TARGET_ENABLED", "false").lower() == "true"
)
COMPANY_DAILY_PROFIT_TARGET_USD: float = float(
    os.getenv("COMPANY_DAILY_PROFIT_TARGET_USD", "10.0")
)
COMPANY_DAILY_LOSS_TARGET_USD: float = float(
    os.getenv("COMPANY_DAILY_LOSS_TARGET_USD", "10.0")
)

# =====================================================
# Helper
# =====================================================
def _safe_int(val: str | None) -> int | None:
    """Konversi string ke int, return None jika tidak valid."""
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _discover_copet_magic_numbers() -> tuple[set[int], dict[int, str]]:
    """
    Temukan SEMUA magic number TUYUL COPET secara dinamis dari .env.

    Cara kerja:
    - Scan semua env var yang polanya: RCS_MAGIC_OP*, *_RCS_MAGIC_OP*
    - Sehingga kalau ada simbol baru (misal BTC, GBPUSD) yang punya
      override magic number sendiri, otomatis ikut terhitung.

    Return:
        - set[int]: kumpulan semua magic number Copet
        - dict[int, str]: mapping magic → "COPET:{symbol}" untuk logging
    """
    magic_set: set[int] = set()
    magic_label: dict[int, str] = {}

    # 1. Global RCS magic (tanpa prefix symbol)
    for op in ("RCS_MAGIC_OP1", "RCS_MAGIC_OP2", "RCS_MAGIC_OP3"):
        val = _safe_int(os.getenv(op))
        if val is not None:
            magic_set.add(val)
            magic_label[val] = f"COPET:GLOBAL:{op}"

    # 2. Per-symbol RCS magic — scan semua env var dengan pattern *_RCS_MAGIC_OP*
    # Contoh yang dicari: NASDAQ-100_RCS_MAGIC_OP1, BTC_RCS_MAGIC_OP2, dsb.
    pattern = re.compile(r"^(.+)_RCS_MAGIC_(OP[123])$")
    for key, raw_val in os.environ.items():
        m = pattern.match(key)
        if m:
            symbol_name = m.group(1)   # e.g. "NASDAQ-100", "BTC"
            op_name     = m.group(2)   # e.g. "OP1"
            val = _safe_int(raw_val)
            if val is not None:
                magic_set.add(val)
                magic_label[val] = f"COPET:{symbol_name}:{op_name}"

    return magic_set, magic_label


# =====================================================
# Magic Numbers — Semua Tuyul (diinisialisasi saat module load)
# =====================================================

# TUYUL MALING (Engulfing Strategy) — semua pair pakai 1 magic number
MALING_MAGIC_NUMBERS: list[int] = [
    int(os.getenv("EXECUTION_MAGIC_NUMBER", "777777")),
]
MALING_MAGIC_SET: set[int] = set(MALING_MAGIC_NUMBERS)

# TUYUL COPET (RCS Strategy) — discovery dinamis dari semua env var
COPET_MAGIC_SET, COPET_MAGIC_LABEL = _discover_copet_magic_numbers()
COPET_MAGIC_NUMBERS: list[int] = sorted(COPET_MAGIC_SET)

# Gabungan semua magic number (untuk filter awal)
ALL_TUYUL_MAGIC_SET: set[int] = MALING_MAGIC_SET | COPET_MAGIC_SET
ALL_TUYUL_MAGIC_NUMBERS: list[int] = sorted(ALL_TUYUL_MAGIC_SET)

# =====================================================
# State — mencegah notif WA berulang dalam 1 hari
# =====================================================
_notif_sent_date: Optional[date] = None
_target_hit_cache: tuple[bool, str, date] = (False, "", date.min)


# =====================================================
# Core PnL Calculator
# =====================================================

def _fetch_closed_deals_today() -> list:
    """
    Ambil semua deal TERTUTUP (DEAL_ENTRY_OUT) hari ini dari MT5.

    DEAL_ENTRY_OUT adalah deal penutupan posisi — di sinilah profit/loss
    yang sudah terealisasi dicatat. Deal entry (DEAL_ENTRY_IN) tidak membawa
    profit nyata dan sengaja dikecualikan untuk menghindari double-count.
    """
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)

    all_deals = mt5.history_deals_get(today_start, now)
    if not all_deals:
        return []

    closed_deals = []
    for deal in all_deals:
        # Hanya ambil deal penutupan posisi (exit = profit/loss terealisasi)
        if deal.entry == mt5.DEAL_ENTRY_OUT:
            closed_deals.append(deal)

    return closed_deals


def get_company_today_pnl() -> float:
    """
    Hitung total PnL bersih hari ini dari SEMUA deal yang sudah closed (DEAL_ENTRY_OUT),
    difilter berdasarkan magic number seluruh Tuyul (Maling + Copet, semua pair).

    Mengakumulasi: deal.profit + deal.swap + deal.commission per ticket.
    """
    deals = _fetch_closed_deals_today()
    if not deals:
        return 0.0

    total_pnl = 0.0
    for deal in deals:
        if deal.magic not in ALL_TUYUL_MAGIC_SET:
            continue
        total_pnl += deal.profit + deal.swap + deal.commission

    return round(total_pnl, 2)


def get_company_today_pnl_breakdown() -> dict:
    """
    Rincian PnL hari ini per Tuyul dan per pair mata uang.

    Return dict:
    {
        'maling'      : float,            # Total PnL TUYUL MALING semua pair
        'copet'       : float,            # Total PnL TUYUL COPET semua pair
        'copet_detail': {symbol: float},  # Per-symbol breakdown COPET
        'maling_detail': {symbol: float}, # Per-symbol breakdown MALING
        'total'       : float,
        'deal_count'  : int               # Jumlah deal closed yang dihitung
    }
    """
    deals = _fetch_closed_deals_today()
    if not deals:
        return {
            "maling": 0.0, "copet": 0.0,
            "copet_detail": {}, "maling_detail": {},
            "total": 0.0, "deal_count": 0
        }

    maling_pnl = 0.0
    copet_pnl  = 0.0
    maling_detail: dict[str, float] = {}
    copet_detail:  dict[str, float] = {}
    deal_count = 0

    for deal in deals:
        magic = deal.magic
        if magic not in ALL_TUYUL_MAGIC_SET:
            continue

        pnl    = deal.profit + deal.swap + deal.commission
        symbol = deal.symbol
        deal_count += 1

        if magic in MALING_MAGIC_SET:
            maling_pnl += pnl
            maling_detail[symbol] = round(maling_detail.get(symbol, 0.0) + pnl, 2)

        elif magic in COPET_MAGIC_SET:
            copet_pnl += pnl
            copet_detail[symbol] = round(copet_detail.get(symbol, 0.0) + pnl, 2)

    total = round(maling_pnl + copet_pnl, 2)
    return {
        "maling":       round(maling_pnl, 2),
        "copet":        round(copet_pnl, 2),
        "maling_detail": maling_detail,
        "copet_detail":  copet_detail,
        "total":         total,
        "deal_count":    deal_count,
    }


def _format_breakdown_for_notif(breakdown: dict) -> str:
    """Format breakdown dict menjadi teks siap kirim WA/terminal."""
    lines = []

    if breakdown["maling_detail"]:
        pairs = ", ".join(
            f"{sym} ${pnl:+.2f}"
            for sym, pnl in sorted(breakdown["maling_detail"].items())
        )
        lines.append(f"   🥷 Maling  : ${breakdown['maling']:+.2f} ({pairs})")
    else:
        lines.append(f"   🥷 Maling  : $0.00")

    if breakdown["copet_detail"]:
        pairs = ", ".join(
            f"{sym} ${pnl:+.2f}"
            for sym, pnl in sorted(breakdown["copet_detail"].items())
        )
        lines.append(f"   🕵️ Copet   : ${breakdown['copet']:+.2f} ({pairs})")
    else:
        lines.append(f"   🕵️ Copet   : $0.00")

    lines.append(f"   📊 Total   : ${breakdown['total']:+.2f} dari {breakdown['deal_count']} deal closed")
    return "\n".join(lines)


# =====================================================
# Main Guard Function
# =====================================================

def check_company_daily_target() -> tuple[bool, str]:
    """
    Cek apakah target profit/loss harian perusahaan sudah tercapai.

    Return:
        (True, "")       → masih boleh execute order
        (False, reason)  → target sudah tercapai, stop execute

    Jika COMPANY_DAILY_TARGET_ENABLED=false → selalu return (True, "").
    """
    global _target_hit_cache

    if not COMPANY_DAILY_TARGET_ENABLED:
        return True, ""

    today = datetime.now().date()

    # Gunakan cache dalam tanggal yang sama agar tidak query MT5 setiap tick
    cached_blocked, cached_reason, cached_date = _target_hit_cache
    if cached_blocked and cached_date == today:
        return False, cached_reason

    today_pnl = get_company_today_pnl()

    if today_pnl >= COMPANY_DAILY_PROFIT_TARGET_USD:
        breakdown = get_company_today_pnl_breakdown()
        detail_text = _format_breakdown_for_notif(breakdown)
        reason = (
            f"🏆 COMPANY TARGET PROFIT TERCAPAI!\n"
            f"   Total PnL: ${today_pnl:+.2f} ≥ Target +${COMPANY_DAILY_PROFIT_TARGET_USD:.2f}\n"
            f"{detail_text}"
        )
        _target_hit_cache = (True, reason, today)
        return False, reason

    if today_pnl <= -COMPANY_DAILY_LOSS_TARGET_USD:
        breakdown = get_company_today_pnl_breakdown()
        detail_text = _format_breakdown_for_notif(breakdown)
        reason = (
            f"🛑 COMPANY LIMIT LOSS TERSENTUH!\n"
            f"   Total PnL: ${today_pnl:+.2f} ≤ Limit -${COMPANY_DAILY_LOSS_TARGET_USD:.2f}\n"
            f"{detail_text}"
        )
        _target_hit_cache = (True, reason, today)
        return False, reason

    return True, ""


def should_send_company_notif() -> bool:
    """
    Return True hanya jika notif WA belum pernah dikirim hari ini.
    Dipanggil setelah check_company_daily_target() return False.
    """
    global _notif_sent_date
    today = datetime.now().date()
    if _notif_sent_date != today:
        _notif_sent_date = today
        return True
    return False


def get_company_guard_status_text() -> str:
    """Return status teks untuk logging startup — tampilkan semua magic number yang dideteksi."""
    copet_labels = ", ".join(
        f"{magic}({label})" for magic, label in sorted(COPET_MAGIC_LABEL.items())
    )
    status_prefix = "ENABLED" if COMPANY_DAILY_TARGET_ENABLED else "DISABLED"

    if not COMPANY_DAILY_TARGET_ENABLED:
        return (
            f"{status_prefix} | "
            f"Maling: {MALING_MAGIC_NUMBERS} | "
            f"Copet: [{copet_labels}] | "
            f"Target: +${COMPANY_DAILY_PROFIT_TARGET_USD:.2f} / -${COMPANY_DAILY_LOSS_TARGET_USD:.2f}"
        )

    today_pnl = get_company_today_pnl()
    return (
        f"{status_prefix} | "
        f"PnL Hari ini: ${today_pnl:+.2f} | "
        f"Profit Target: +${COMPANY_DAILY_PROFIT_TARGET_USD:.2f} | "
        f"Loss Limit: -${COMPANY_DAILY_LOSS_TARGET_USD:.2f} | "
        f"Maling: {MALING_MAGIC_NUMBERS} | "
        f"Copet: {COPET_MAGIC_NUMBERS}"
    )
