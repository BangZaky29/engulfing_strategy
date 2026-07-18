# =====================================================
# mt5_client/trade_monitor/__init__.py
# Re-export public API — supaya import path yang sudah ada
# di main.py dan execution.py TIDAK PERLU diubah.
# =====================================================

from .closed_trade_handler import check_closed_trades
from .tracker_store import (
    add_tracked_trade,
    load_tracked_trades,
    save_tracked_trades,
)
