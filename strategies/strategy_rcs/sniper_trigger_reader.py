# =====================================================
# strategies/strategy_rcs/sniper_trigger_reader.py
# Helper untuk RCS membaca dan consume Sniper trigger
# Berjalan di sisi RCS Engine (run_rcs_watchdog.py)
# =====================================================

import os
import json
import datetime


# Path ke shared trigger file yang ditulis oleh Scanner/SniperMonitor
_SNIPER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "indicatorInfo", "sniperInfo")
)
SNIPER_TRIGGER_FILE = os.path.join(_SNIPER_DIR, "sniper_trigger.json")


def read_sniper_trigger(symbol: str) -> dict | None:
    """
    Baca sniper_trigger.json yang ditulis oleh SniperMonitor.

    Returns:
        dict trigger data jika ada trigger valid untuk symbol ini yang belum consumed.
        None jika file tidak ada, sudah consumed, atau symbol tidak cocok.
    """
    if not os.path.exists(SNIPER_TRIGGER_FILE):
        return None

    try:
        with open(SNIPER_TRIGGER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return None

    # Validasi: symbol harus cocok
    if data.get("symbol") != symbol:
        return None

    # Validasi: belum consumed
    if data.get("consumed", True):
        return None

    return data


def mark_sniper_consumed(consumed_by: str = "RCS"):
    """
    Tandai trigger sniper sebagai consumed setelah RCS menembak recovery.
    Update file secara atomic.
    """
    if not os.path.exists(SNIPER_TRIGGER_FILE):
        return

    try:
        with open(SNIPER_TRIGGER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["consumed"] = True
        data["consumed_by"] = consumed_by
        data["consumed_at"] = datetime.datetime.now().isoformat()

        temp_file = f"{SNIPER_TRIGGER_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(temp_file, SNIPER_TRIGGER_FILE)
    except Exception as e:
        print(f"⚠️ [SNIPER] Gagal mark consumed: {e}")


def get_sniper_trigger_age_seconds(trigger_data: dict) -> float:
    """Hitung berapa detik sejak trigger confirmed."""
    confirmed_at = trigger_data.get("confirmed_at")
    if not confirmed_at:
        return 999999.0

    try:
        dt = datetime.datetime.fromisoformat(confirmed_at)
        return (datetime.datetime.now() - dt).total_seconds()
    except (ValueError, TypeError):
        return 999999.0
