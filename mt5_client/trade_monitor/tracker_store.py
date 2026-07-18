# =====================================================
# mt5_client/trade_monitor/tracker_store.py
# Manage trade tracker JSON file: load, save, add entries.
# =====================================================

import json
import os
from datetime import datetime

TRACKER_FILE = "trade_tracker.json"
TEMP_DIR = "temp_screenshots"
BUCKET_NAME = "engulfing"

# =====================================================
# SCREENSHOT_TIMEFRAME: TF untuk chart screenshot hasil trade.
# Jika diset (misal "H1"), screenshot akan pakai TF tersebut
# terlepas dari TF eksekusi trade. Kosong = ikut TF trade.
# SCREENSHOT_CANDLES : jumlah candle yang ditampilkan di chart.
# =====================================================
_SS_TF_ENV    = os.getenv("SCREENSHOT_TIMEFRAME", "").strip()
_SS_CANDLES   = int(os.getenv("SCREENSHOT_CANDLES", "30"))


def load_tracked_trades() -> dict:
    if not os.path.exists(TRACKER_FILE):
        return {}
    with open(TRACKER_FILE, "r") as f:
        try:
            return json.load(f)
        except Exception:
            return {}


def save_tracked_trades(data: dict):
    with open(TRACKER_FILE, "w") as f:
        json.dump(data, f, indent=4)


def add_tracked_trade(
    ticket: int,
    symbol: str,
    mode: str,
    tf: str,
    op_price: float,
    sl_price: float,
    tp_price: float,
    status: str = "ACTIVE",
    trading_session: str = "Unknown",
    hedge_ticket: int | None = None,
    trigger_type: str | None = None,
    tf_list: list[str] | None = None,
    tf_monitor: str | None = None,       # ← TAMBAH
    h1_trigger_source: str = "",
    m15_trigger_source: str = "",
    m5_trigger_source: str = "",
    op_level_pts: int = 0,
    op_level_pct: float = 0.0,
):
    """
    Simpan tiket order ke file tracker untuk dimonitor.
    """
    data = load_tracked_trades()
    data[str(ticket)] = {
        "symbol": symbol,
        "mode": mode,  # BUY atau SELL
        "tf": tf,
        "tf_monitor": tf_monitor or "M15",   # ← TAMBAH
        "tf_list": tf_list or [tf],          # ← TAMBAH
        "op_price": op_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "status": status,
        "trading_session": trading_session,
        "hedge_ticket": hedge_ticket,
        "hedge_triggered": False,
        "trigger_type": trigger_type or "Engulfing",
        "entry_time": None,  # akan diisi saat posisi ACTIVE terlihat
        "latest_snapshot_time": None,  # agar sampling tidak terlalu rapat
        "tf_list": tf_list or [tf],  # simpan semua TF yang dipakai
        "h1_trigger_source": h1_trigger_source,
        "m15_trigger_source": m15_trigger_source,
        "m5_trigger_source": m5_trigger_source,
        "op_level_pts": op_level_pts,
        "op_level_pct": op_level_pct,
    }
    save_tracked_trades(data)
