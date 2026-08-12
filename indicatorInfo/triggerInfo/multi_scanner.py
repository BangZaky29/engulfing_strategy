"""
MultiPatternScanner - Entry Point
==================================
File ini hanya entry point. Semua logika ada di:
  scanner/engine.py     → MultiPatternScanner (scan loop & state)
  scanner/notifier.py   → ScannerNotifier (format & kirim WA)
  scanner/patterns/     → Pattern detectors (Engulfing, Marubozu, SameCandle)
"""

import os
import sys

# Add root directory and current directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from dotenv import load_dotenv
from mt5_client import init_mt5, shutdown_mt5
from scanner import MultiPatternScanner


def main():
    # Load .env from root directory
    load_dotenv(os.path.join(root_dir, ".env"))

    if not init_mt5():
        print("Gagal init MT5.")
        exit(1)

    # Read config from .env
    symbols_str = os.getenv("SCANNER_SYMBOLS", "XAUUSD,NASDAQ-100,BTC")
    timeframes_str = os.getenv("SCANNER_TIMEFRAMES", "M5,M15,M30,H1,H4,D1")

    symbols_list = [s.strip() for s in symbols_str.split(",") if s.strip()]
    timeframes_list = [t.strip() for t in timeframes_str.split(",") if t.strip()]

    scanner = MultiPatternScanner(
        symbols=symbols_list,
        timeframes=timeframes_list
    )

    try:
        scanner.run_forever()
    except KeyboardInterrupt:
        print("Scanner dihentikan.")
    finally:
        shutdown_mt5()


if __name__ == "__main__":
    main()
