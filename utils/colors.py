# =====================================================
# utils/colors.py
# ANSI Color constants & helpers untuk terminal output
# Tidak butuh library eksternal — pure Python built-in
# =====================================================

import os
import sys


def _supports_ansi() -> bool:
    """Deteksi apakah terminal support ANSI color codes."""
    # Disable via environment variable (NO_COLOR standard)
    if os.environ.get("NO_COLOR"):
        return False
    # Force enable via environment variable
    if os.environ.get("FORCE_COLOR"):
        return True
    # Windows: aktifkan Virtual Terminal Processing
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore
            # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    # Unix/Linux/Mac: cek isatty
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_ANSI_ENABLED = _supports_ansi()


class Colors:
    """Konstanta ANSI escape codes."""
    RESET   = "\033[0m"  if _ANSI_ENABLED else ""
    BOLD    = "\033[1m"  if _ANSI_ENABLED else ""
    DIM     = "\033[2m"  if _ANSI_ENABLED else ""

    # Foreground colors
    RED     = "\033[91m" if _ANSI_ENABLED else ""   # Merah terang
    GREEN   = "\033[92m" if _ANSI_ENABLED else ""   # Hijau terang
    YELLOW  = "\033[93m" if _ANSI_ENABLED else ""   # Kuning
    BLUE    = "\033[94m" if _ANSI_ENABLED else ""   # Biru
    MAGENTA = "\033[95m" if _ANSI_ENABLED else ""   # Magenta
    CYAN    = "\033[96m" if _ANSI_ENABLED else ""   # Cyan
    WHITE   = "\033[97m" if _ANSI_ENABLED else ""   # Putih terang
    GRAY    = "\033[90m" if _ANSI_ENABLED else ""   # Abu-abu (disabled)


def cprint(text: str, color: str, bold: bool = False) -> str:
    """
    Bungkus teks dengan warna ANSI.
    Kembalikan string berwarna agar bisa dipakai dalam f-string.
    """
    if not _ANSI_ENABLED:
        return text
    prefix = (Colors.BOLD if bold else "") + color
    return f"{prefix}{text}{Colors.RESET}"


def ok(suffix: str = "") -> str:
    """Return '[OK]' dalam hijau bold."""
    return cprint(f"[OK]{suffix}", Colors.GREEN, bold=True)


def no(suffix: str = "") -> str:
    """Return '[NO]' dalam merah."""
    return cprint(f"[NO]{suffix}", Colors.RED)


def reject(suffix: str = "") -> str:
    """Return '[REJECT]' dalam merah."""
    return cprint(f"[REJECT]{suffix}", Colors.RED)


def skip_msg(reason: str) -> str:
    """Return '>> SKIP: ...' dalam kuning."""
    return cprint(f">> SKIP: {reason}", Colors.YELLOW, bold=True)


def grade_color(grade: str) -> str:
    """Return teks grade dengan warna berdasarkan nilai."""
    grade_colors = {
        "A+": Colors.GREEN,
        "A":  Colors.GREEN,
        "B+": Colors.YELLOW,
        "B":  Colors.YELLOW,
        "C+": Colors.RED,
        "C":  Colors.RED,
        "D":  Colors.RED,
        "N/A": Colors.GRAY,
    }
    color = grade_colors.get(grade, Colors.WHITE)
    return cprint(grade, color, bold=(grade in ("A+", "A")))


def market_color(state: str) -> str:
    """Return teks market state dengan warna."""
    market_colors = {
        "TRENDING_UP":   Colors.GREEN,
        "TRENDING_DOWN": Colors.RED,
        "SIDEWAYS":      Colors.YELLOW,
        "NORMAL":        Colors.WHITE,
    }
    color = market_colors.get(state, Colors.WHITE)
    return cprint(state, color)


def candle_color(is_bullish: bool) -> str:
    """
    Return warna ANSI berdasarkan arah candle.
    Dipakai untuk mewarnai seluruh blok log candle.
    """
    return Colors.GREEN if is_bullish else Colors.RED
