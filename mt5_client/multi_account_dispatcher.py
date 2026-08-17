# =====================================================
# mt5_client/multi_account_dispatcher.py
# Multi-Process MT5 Dispatcher (ProcessPoolExecutor)
# Paralel murni tanpa bentrok C-DLL MT5 SDK di Windows
# =====================================================

import os
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
import MetaTrader5 as mt5
from database.supabase_client import execute_supabase
from utils.colors import cprint, Colors

def get_target_accounts(strategy_name: str) -> list[dict]:
    """Mengambil daftar akun target dari .env untuk strategi tertentu."""
    enabled = os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() == "true"
    if not enabled:
        return []

    accounts_str = os.getenv("ACCOUNTS_LIST", "ACC1,ACC2,ACC3")
    all_account_keys = [a.strip() for a in accounts_str.split(",") if a.strip()]

    target_env_key = f"{strategy_name.upper()}_TARGET_ACCOUNTS"
    target_str = os.getenv(target_env_key, accounts_str)
    target_keys = [a.strip() for a in target_str.split(",") if a.strip()]

    accounts = []
    for key in target_keys:
        if key not in all_account_keys:
            continue
        name = os.getenv(f"{key}_NAME", key)
        path = os.getenv(f"{key}_PATH", "")
        login_str = os.getenv(f"{key}_LOGIN", "0")
        password = os.getenv(f"{key}_PASSWORD", "")
        server = os.getenv(f"{key}_SERVER", "")

        try:
            login = int(login_str)
        except ValueError:
            login = 0

        if path and login > 0:
            accounts.append({
                "key": key,
                "name": name,
                "path": path,
                "login": login,
                "password": password,
                "server": server
            })

    return accounts

def _worker_execute_account_order(acc_info: dict, strategy_name: str, payload: dict) -> dict:
    """
    Sub-proses terisolasi (PID terpisah) untuk mengeksekusi order pada 1 terminal akun MT5 spesifik.
    """
    pid_tag = f"[PID-{os.getpid()}-{acc_info['key']}]"
    print(cprint(f"🚀 {pid_tag} Memulai eksekusi paralel akun {acc_info['name']} ({acc_info['login']})", Colors.CYAN))

    # 1. Inisialisasi koneksi terisolasi ke terminal akun target
    init_res = mt5.initialize(
        path=acc_info['path'],
        login=acc_info['login'],
        password=acc_info['password'],
        server=acc_info['server']
    )

    if not init_res:
        err = mt5.last_error()
        err_msg = f"{pid_tag} Gagal inisialisasi MT5 untuk {acc_info['name']} ({acc_info['login']}): {err}"
        print(cprint(f"❌ {err_msg}", Colors.RED))
        return {"key": acc_info['key'], "login": acc_info['login'], "success": False, "error": err_msg}

    symbol = payload.get("symbol", "XAUUSD")
    mt5.symbol_select(symbol, True)
    symbol_info = mt5.symbol_info(symbol)
    digits = symbol_info.digits if symbol_info else 2

    # 2. Hitung Lot Dinamis & Saldo Khusus Milik Akun Ini
    acc = mt5.account_info()
    funds = acc.balance if acc else 0.0
    
    # Lot OP1 dinamis akun
    if funds < 200.0:
        op1_lot = 0.01
    else:
        op1_lot = round(int(funds // 100) * 0.01, 2)
    op1_lot = max(0.01, op1_lot)

    # Sesuaikan lot order berdasarkan peran (OP1, OP2, OP3)
    order_role = payload.get("order_role", "OP1")
    if order_role == "OP2":
        volume = round(op1_lot * 2, 2)
    elif order_role == "OP3":
        volume = round(op1_lot * 3, 2)
    else:
        volume = op1_lot

    # 3. Rakit Request Order MT5
    req = {
        "action": payload.get("action", mt5.TRADE_ACTION_DEAL),
        "symbol": symbol,
        "volume": volume,
        "type": payload.get("type", mt5.ORDER_TYPE_BUY),
        "price": round(payload.get("price", 0.0), digits),
        "sl": round(payload.get("sl", 0.0), digits),
        "tp": round(payload.get("tp", 0.0), digits),
        "deviation": payload.get("deviation", 20),
        "magic": payload.get("magic", 999999),
        "comment": payload.get("comment", f"{strategy_name}_{order_role}"),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    res = mt5.order_send(req)

    # 4. Kirim WA Notification dengan Footer Label Identitas Akun & Bot
    wa_message = payload.get("wa_message")
    if wa_message:
        dest_jid = payload.get("target_jid", os.getenv("RCS_GROUP_JID", "120363409493021715@g.us"))
        footer_label = f"\n\n🏷️ *AKUN:* {acc_info['key']} ({acc_info['name']} | {acc_info['login']}) | *BOT:* {strategy_name.upper()}"
        full_wa_message = wa_message.strip() + footer_label

        wa_payload = {
            'source_table': f'{strategy_name.lower()}_system',
            'event_type': f'{strategy_name.upper()}_MULTI_EXEC',
            'group_jid': dest_jid,
            'message_type': 'TEXT',
            'message': full_wa_message,
            'dedupe_key': f'{strategy_name.lower()}_{acc_info["key"]}_{int(time.time())}_{uuid.uuid4().hex[:6]}'
        }
        try:
            execute_supabase(lambda sb: sb.table('wa_outbox').insert(wa_payload).execute())
            print(cprint(f"📲 {pid_tag} WA Notif dikirim ke {dest_jid} dengan Label Footer Akun.", Colors.GREEN))
        except Exception as e:
            print(cprint(f"⚠️ {pid_tag} Gagal insert WA outbox: {e}", Colors.RED))

    # 5. Shutdown koneksi MT5 sub-proses
    mt5.shutdown()

    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        msg = f"{pid_tag} ✅ Order Sukses! Ticket: #{res.order} | Vol: {res.volume} | Akun: {acc_info['name']}"
        print(cprint(msg, Colors.GREEN))
        return {"key": acc_info['key'], "login": acc_info['login'], "success": True, "ticket": res.order, "volume": res.volume}
    else:
        err_comment = res.comment if res else "Unknown Error"
        msg = f"{pid_tag} ❌ Order Gagal! Comment: {err_comment} | Akun: {acc_info['name']}"
        print(cprint(msg, Colors.RED))
        return {"key": acc_info['key'], "login": acc_info['login'], "success": False, "error": err_comment}

def dispatch_multi_account_order(strategy_name: str, payload: dict) -> list[dict]:
    """
    Fungsi penembak utama: Membuka ProcessPoolExecutor untuk mengeksekusi order
    ke seluruh akun target secara paralel murni tanpa bentrok.
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        print(cprint(f"⚠️ [MultiAccount] Tidak ada akun target aktif untuk {strategy_name}", Colors.YELLOW))
        return []

    print(cprint(f"⚡ [MultiAccount Dispatcher] Memulai eksekusi paralel murni ke {len(accounts)} akun ({', '.join([a['key'] for a in accounts])})...", Colors.MAGENTA))

    results = []
    with ProcessPoolExecutor(max_workers=len(accounts)) as executor:
        futures = {
            executor.submit(_worker_execute_account_order, acc, strategy_name, payload): acc
            for acc in accounts
        }
        for future in as_completed(futures):
            acc_target = futures[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as exc:
                print(cprint(f"⚠️ Error eksekusi sub-proses akun {acc_target['key']}: {exc}", Colors.RED))
                results.append({"key": acc_target['key'], "success": False, "error": str(exc)})

    return results
