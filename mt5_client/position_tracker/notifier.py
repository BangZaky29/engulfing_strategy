# =====================================================
# mt5_client/position_tracker/notifier.py
# Notifikasi WA untuk event posisi manual
# Target:
#   - OP Manual Recovery/Freeze → RCS_GROUP_JID
#   - OP Manual Liar            → PRIVATE_JID + Terminal
# =====================================================

import os
import time
import uuid

from .models import TrackedPosition
from utils.colors import cprint, Colors


def _send_wa(message: str, target_jid: str, event_type: str):
    """Helper kirim pesan ke Supabase WA Outbox."""
    if not target_jid:
        return
    try:
        from database.supabase_client import get_supabase
        supabase = get_supabase()
        if supabase is None:
            return

        supabase.table("wa_outbox").insert({
            "source_table": "position_tracker",
            "event_type": event_type,
            "group_jid": target_jid,
            "message_type": "TEXT",
            "message": message,
            "dedupe_key": f"pt_{event_type}_{int(time.time())}_{uuid.uuid4().hex[:8]}",
        }).execute()
    except Exception as e:
        print(cprint(f"⚠️ Gagal kirim WA notif ({event_type}): {e}", Colors.RED))


def notify_manual_position_detected(symbol: str, positions: list[TrackedPosition], is_freeze: bool = False):
    """
    Kirim notifikasi saat OP manual terdeteksi.

    Target:
    - Selalu ke PRIVATE_JID (info OP liar/manual)
    - Jika is_freeze=True juga ke RCS_GROUP_JID (recovery manual)
    """
    group_jid = os.getenv("RCS_GROUP_JID", "")
    private_jid = os.getenv("PRIVATE_JID", "")

    pos_details = []
    for p in positions:
        pos_details.append(
            f"  • Tkt #{p.ticket} | {p.direction} {p.volume} lot @ {p.open_price:.5f} | Floating: ${p.current_profit:.2f}"
        )
    details_str = "\n".join(pos_details)

    # Terminal log (selalu)
    print(cprint(f"\n{'='*50}", Colors.YELLOW))
    print(cprint(f"🔍 [{symbol}] OP MANUAL TERDETEKSI! ({len(positions)} posisi)", Colors.YELLOW))
    for line in pos_details:
        print(cprint(line, Colors.YELLOW))
    if is_freeze:
        print(cprint(f"   ❄️ Status: Dalam FREEZE — Kemungkinan OP Recovery oleh Trader", Colors.CYAN))
    else:
        print(cprint(f"   ⚠️ Status: OP Manual/Liar terdeteksi — Siklus baru DIBLOKIR", Colors.RED))
    print(cprint(f"{'='*50}\n", Colors.YELLOW))

    # --- Pesan ke PRIVATE_JID (info OP liar + recovery) ---
    msg_private = (
        f"🔍 *OP MANUAL TERDETEKSI* [{symbol}]\n\n"
        f"Jumlah: {len(positions)} posisi\n"
        f"{details_str}\n\n"
    )
    if is_freeze:
        msg_private += (
            f"❄️ Status: Dalam FREEZE mode\n"
            f"Kemungkinan OP Recovery oleh Trader.\n"
            f"Sistem TIDAK akan membuka siklus baru sampai semua OP manual ditutup."
        )
    else:
        msg_private += (
            f"⚠️ Status: OP Manual/Liar\n"
            f"Siklus baru untuk {symbol} DIBLOKIR sampai semua OP manual ditutup."
        )
    _send_wa(msg_private, private_jid, "PT_MANUAL_OPEN")

    # --- Pesan ke RCS_GROUP_JID (recovery saat freeze) ---
    if is_freeze and group_jid:
        msg_group = (
            f"🤖 *[POSITION TRACKER]*\n\n"
            f"🔍 *OP MANUAL TERDETEKSI* [{symbol}]\n\n"
            f"Jumlah: {len(positions)} posisi\n"
            f"{details_str}\n\n"
            f"❄️ Sistem mendeteksi OP recovery manual oleh Trader.\n"
            f"Kalkulasi profit/loss akan menyertakan OP ini secara otomatis."
        )
        _send_wa(msg_group, group_jid, "PT_MANUAL_OPEN_FREEZE")


def notify_manual_position_closed(symbol: str, positions: list[TrackedPosition], remaining: int):
    """
    Kirim notifikasi saat OP manual ditutup.
    Target: PRIVATE_JID + RCS_GROUP_JID
    """
    group_jid = os.getenv("RCS_GROUP_JID", "")
    private_jid = os.getenv("PRIVATE_JID", "")

    pos_details = []
    total_net = 0.0
    for p in positions:
        net = p.close_profit + p.close_swap + p.close_commission
        total_net += net
        result_emoji = "🟢" if net >= 0 else "🔴"
        pos_details.append(
            f"  • Tkt #{p.ticket} | {p.direction} {p.volume} lot | PnL: ${net:.2f} {result_emoji}"
        )
    details_str = "\n".join(pos_details)

    # Terminal log
    print(cprint(f"\n{'='*50}", Colors.CYAN))
    print(cprint(f"📤 [{symbol}] OP MANUAL DITUTUP ({len(positions)} posisi) | Net: ${total_net:.2f}", Colors.CYAN))
    for line in pos_details:
        print(cprint(line, Colors.CYAN))
    print(cprint(f"   📊 Sisa OP Manual aktif: {remaining}", Colors.CYAN))
    print(cprint(f"{'='*50}\n", Colors.CYAN))

    msg = (
        f"🤖 *[POSITION TRACKER]*\n\n"
        f"📤 *OP MANUAL DITUTUP* [{symbol}]\n\n"
        f"Jumlah ditutup: {len(positions)}\n"
        f"{details_str}\n\n"
        f"💰 Total Net PnL: *${total_net:.2f}*\n"
        f"📊 Sisa OP Manual aktif: {remaining}"
    )

    _send_wa(msg, private_jid, "PT_MANUAL_CLOSE")
    if group_jid:
        _send_wa(msg, group_jid, "PT_MANUAL_CLOSE")


def notify_all_manual_cleared(symbol: str):
    """
    Kirim notifikasi saat semua OP manual sudah ditutup.
    Target: PRIVATE_JID + RCS_GROUP_JID
    """
    group_jid = os.getenv("RCS_GROUP_JID", "")
    private_jid = os.getenv("PRIVATE_JID", "")

    # Terminal log
    print(cprint(f"\n{'='*50}", Colors.GREEN))
    print(cprint(f"✅ [{symbol}] Semua OP Manual telah ditutup. Sistem siap melanjutkan siklus.", Colors.GREEN))
    print(cprint(f"{'='*50}\n", Colors.GREEN))

    msg = (
        f"🤖 *[POSITION TRACKER]*\n\n"
        f"✅ *SEMUA OP MANUAL DITUTUP* [{symbol}]\n\n"
        f"Sistem siap melanjutkan siklus normal untuk {symbol}."
    )

    _send_wa(msg, private_jid, "PT_ALL_CLEARED")
    if group_jid:
        _send_wa(msg, group_jid, "PT_ALL_CLEARED")


def notify_system_paused_due_manual(symbol: str, manual_count: int, manual_floating: float):
    """
    Log ke terminal saat siklus baru di-block karena OP manual.
    Notifikasi WA hanya sekali (di-handle oleh throttle di tracker).
    """
    # Terminal log (setiap kali, tapi pakai end=\r agar tidak spam)
    print(
        cprint(
            f"⏸️ [{symbol}] PAUSED — {manual_count} OP Manual terbuka (Floating: ${manual_floating:.2f}). "
            f"Siklus baru DIBLOKIR.",
            Colors.YELLOW,
        ),
        end="\r",
        flush=True,
    )
