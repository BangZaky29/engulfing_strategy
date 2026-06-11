# =====================================================
# mt5_client/__init__.py
# Package untuk koneksi dan data dari MetaTrader 5
# =====================================================

from mt5_client.connection import init_mt5, shutdown_mt5
from mt5_client.candle_fetcher import get_closed_candles
from mt5_client.indicators import get_ema
from mt5_client.execution import execute_engulfing_order
