# =====================================================
# mt5_client/position_tracker/event_log.py
# Pencatatan event posisi ke Supabase tabel position_events
# =====================================================

import time
import uuid
from datetime import datetime
from typing import Optional

from .models import TrackedPosition, PositionOrigin


def log_position_event(
    event_type: str,
    ticket: int,
    symbol: str,
    origin: str,
    strategy: str = "UNKNOWN",
    direction: str = "",
    volume: float = 0.0,
    profit: float = 0.0,
    swap: float = 0.0,
    commission: float = 0.0,
    metadata: dict | None = None,
):
    """
    Catat event posisi ke Supabase tabel position_events.

    event_type:
    - MANUAL_OPEN    : OP manual baru terdeteksi
    - MANUAL_CLOSE   : OP manual ditutup
    - SYSTEM_OPEN    : OP sistem terdaftar
    - SYSTEM_CLOSE   : OP sistem ditutup
    - SYSTEM_PAUSED  : Siklus di-pause karena OP manual
    - FREEZE_MANUAL  : OP manual terdeteksi saat FREEZE
    """
    try:
        from database.supabase_client import get_supabase
        supabase = get_supabase()
        if supabase is None:
            return

        payload = {
            "event_type": event_type,
            "ticket": ticket,
            "symbol": symbol,
            "direction": direction,
            "volume": volume,
            "origin": origin,
            "strategy": strategy,
            "profit": round(profit, 2),
            "metadata": {
                **(metadata or {}),
                "swap": round(swap, 4),
                "commission": round(commission, 4),
                "net_profit": round(profit + swap + commission, 2),
                "logged_at": datetime.now().isoformat(),
            },
        }

        supabase.table("position_events").insert(payload).execute()
    except Exception as e:
        print(f"⚠️ Gagal log position event ({event_type}): {e}")


def log_manual_open(symbol: str, positions: list[TrackedPosition]):
    """Log semua OP manual yang baru terdeteksi."""
    for pos in positions:
        log_position_event(
            event_type="MANUAL_OPEN",
            ticket=pos.ticket,
            symbol=symbol,
            origin=PositionOrigin.MANUAL.value,
            direction=pos.direction,
            volume=pos.volume,
            profit=pos.current_profit,
            swap=pos.current_swap,
            commission=pos.current_commission,
            metadata={
                "magic_number": pos.magic_number,
                "comment": pos.comment,
                "open_price": pos.open_price,
                "open_time": pos.open_time.isoformat() if pos.open_time else None,
            },
        )


def log_manual_close(symbol: str, positions: list[TrackedPosition]):
    """Log semua OP manual yang baru ditutup (profit dari broker history)."""
    for pos in positions:
        log_position_event(
            event_type="MANUAL_CLOSE",
            ticket=pos.ticket,
            symbol=symbol,
            origin=PositionOrigin.MANUAL.value,
            direction=pos.direction,
            volume=pos.volume,
            profit=pos.close_profit,
            swap=pos.close_swap,
            commission=pos.close_commission,
            metadata={
                "magic_number": pos.magic_number,
                "comment": pos.comment,
                "open_price": pos.open_price,
                "open_time": pos.open_time.isoformat() if pos.open_time else None,
                "close_time": pos.close_time.isoformat() if pos.close_time else None,
            },
        )


def log_system_paused(symbol: str, reason: str, manual_count: int, manual_floating: float):
    """Log event ketika siklus di-pause karena OP manual."""
    log_position_event(
        event_type="SYSTEM_PAUSED",
        ticket=0,
        symbol=symbol,
        origin="SYSTEM",
        strategy="ALL",
        metadata={
            "reason": reason,
            "manual_count": manual_count,
            "manual_floating": round(manual_floating, 2),
        },
    )
