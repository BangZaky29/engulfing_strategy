# =====================================================
# mt5_client/multi_account_dispatcher.py
# Multi-Process MT5 Dispatcher (ProcessPoolExecutor)
# Paralel murni tanpa bentrok C-DLL MT5 SDK di Windows
# =====================================================

import os
import time
import uuid
from collections import namedtuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import MetaTrader5 as mt5
from database.supabase_client import execute_supabase
from utils.colors import cprint, Colors

# Objek hasil order tiruan kompatibel dengan MT5 OrderSendResult
MultiOrderResult = namedtuple("MultiOrderResult", ["retcode", "order", "price", "volume", "comment"])

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

def _worker_get_single_account_funds(acc_info: dict) -> dict:
    """
    Sub-proses untuk membaca status kesehatan dan dana pada 1 terminal akun MT5 spesifik.
    """
    pid_tag = f"[PID-{os.getpid()}-{acc_info['key']}]"
    
    init_res = mt5.initialize(
        path=acc_info['path'],
        login=acc_info['login'],
        password=acc_info['password'],
        server=acc_info['server'],
        timeout=60000
    )

    if not init_res:
        err = mt5.last_error()
        print(cprint(f"⚠️ {pid_tag} Gagal koneksi untuk audit akun {acc_info['name']}: {err}", Colors.YELLOW))
        return {
            "key": acc_info['key'],
            "name": acc_info['name'],
            "login": acc_info['login'],
            "server": acc_info['server'],
            "connected": False,
            "error": str(err)
        }

    acc = mt5.account_info()
    term = mt5.terminal_info()

    trade_mode = getattr(acc, "trade_mode", 0) if acc else 0
    if trade_mode == 2:
        account_type = "REAL 🔴"
    elif trade_mode == 0:
        account_type = "DEMO 🟡"
    else:
        account_type = "CONTEST 🔵"

    balance = float(getattr(acc, "balance", 0.0)) if acc else 0.0
    equity = float(getattr(acc, "equity", 0.0)) if acc else 0.0
    margin_free = float(getattr(acc, "margin_free", 0.0)) if acc else 0.0
    margin_used = float(getattr(acc, "margin", 0.0)) if acc else 0.0
    margin_level = float(getattr(acc, "margin_level", 0.0)) if acc else 0.0
    leverage = int(getattr(acc, "leverage", 0)) if acc else 0

    if margin_used == 0 or margin_level == 0:
        health_status = "SEHAT 🟢 (0 Margin)"
    elif margin_level >= 500:
        health_status = f"SEHAT 🟢 ({margin_level:.1f}%)"
    elif margin_level >= 200:
        health_status = f"SEDANG 🟡 ({margin_level:.1f}%)"
    else:
        health_status = f"BAHAYA 🔴 ({margin_level:.1f}%)"

    ping_us = int(getattr(term, "ping_last", 0)) if term else 0
    ping_ms = round(ping_us / 1000.0, 1)
    if ping_ms <= 0:
        ping_str = "N/A"
    elif ping_ms <= 50:
        ping_str = f"{ping_ms} ms 🟢 (Fast)"
    elif ping_ms <= 150:
        ping_str = f"{ping_ms} ms 🟢 (Normal)"
    else:
        ping_str = f"{ping_ms} ms 🟡 (Slow)"

    autotrading = "ALLOWED 🟢" if getattr(term, "trade_allowed", True) else "DISABLED 🔴"

    source_type = os.getenv("DYNAMIC_LOT_SOURCE", "BALANCE").upper()
    funds_for_lot = balance if source_type == "BALANCE" else equity

    if funds_for_lot < 200.0:
        op1_lot = 0.01
    else:
        op1_lot = round(int(funds_for_lot // 100) * 0.01, 2)
    op1_lot = max(0.01, op1_lot)

    base_loss_usd = float(os.getenv("MRCV_MAX_NET_LOSS", os.getenv("RCS_DAILY_LOSS_TARGET_USD", "-15.0")))
    scaled_loss = -abs(base_loss_usd) * (op1_lot / 0.01)

    mt5.shutdown()

    return {
        "key": acc_info['key'],
        "name": acc_info['name'],
        "login": acc_info['login'],
        "server": acc_info['server'],
        "connected": True,
        "account_type": account_type,
        "balance": balance,
        "equity": equity,
        "margin_free": margin_free,
        "margin_used": margin_used,
        "margin_level": margin_level,
        "health_status": health_status,
        "leverage": f"1:{leverage}" if leverage > 0 else "-",
        "ping_str": ping_str,
        "autotrading": autotrading,
        "source_type": source_type,
        "dynamic_lot": op1_lot,
        "scaled_max_loss": scaled_loss,
        "base_max_loss": -abs(base_loss_usd)
    }

def get_multi_account_funds_info(strategy_name: str) -> list[dict]:
    """
    Mengambil rincian dana & kesehatan semua akun target secara paralel via ProcessPoolExecutor.
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        return []

    results = []
    with ProcessPoolExecutor(max_workers=max(1, len(accounts))) as executor:
        futures = {
            executor.submit(_worker_get_single_account_funds, acc): acc
            for acc in accounts
        }
        for future in as_completed(futures):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                acc_t = futures[future]
                results.append({
                    "key": acc_t['key'],
                    "name": acc_t['name'],
                    "login": acc_t['login'],
                    "connected": False,
                    "error": str(e)
                })

    # Sort results according to original order in ACCOUNTS_LIST
    order_map = {acc['key']: idx for idx, acc in enumerate(accounts)}
    results.sort(key=lambda x: order_map.get(x['key'], 999))
    return results

def _worker_execute_account_order(acc_info: dict, strategy_name: str, payload: dict) -> dict:
    """
    Sub-proses terisolasi (PID terpisah) untuk mengeksekusi order pada 1 terminal akun MT5 spesifik.
    """
    pid_tag = f"[PID-{os.getpid()}-{acc_info['key']}]"
    print(cprint(f"🚀 {pid_tag} Memulai eksekusi paralel akun {acc_info['name']} ({acc_info['login']})", Colors.CYAN))

    # 1. Inisialisasi koneksi terisolasi ke terminal akun target dengan timeout 60 detik
    init_res = False
    for attempt in range(1, 3):
        init_res = mt5.initialize(
            path=acc_info['path'],
            login=acc_info['login'],
            password=acc_info['password'],
            server=acc_info['server'],
            timeout=60000
        )
        if init_res:
            break
        time.sleep(1)

    if not init_res:
        err = mt5.last_error()
        err_msg = f"{pid_tag} Gagal inisialisasi MT5 untuk {acc_info['name']} ({acc_info['login']}): {err}"
        print(cprint(f"❌ {err_msg}", Colors.RED))
        return {"key": acc_info['key'], "login": acc_info['login'], "success": False, "error": err_msg, "retcode": -1}

    symbol = payload.get("symbol", "XAUUSD")
    mt5.symbol_select(symbol, True)
    symbol_info = mt5.symbol_info(symbol)
    digits = symbol_info.digits if symbol_info else 2

    # Filling mode detection
    filling_mode = mt5.ORDER_FILLING_FOK
    if symbol_info:
        if (symbol_info.filling_mode & 1) == 1:
            filling_mode = mt5.ORDER_FILLING_FOK
        elif (symbol_info.filling_mode & 2) == 2:
            filling_mode = mt5.ORDER_FILLING_IOC
        else:
            filling_mode = mt5.ORDER_FILLING_RETURN

    # 2. Hitung Lot Dinamis & Saldo Khusus Milik Akun Ini
    acc = mt5.account_info()
    funds = acc.balance if acc else 0.0
    
    if funds < 200.0:
        op1_lot = 0.01
    else:
        op1_lot = round(int(funds // 100) * 0.01, 2)
    op1_lot = max(0.01, op1_lot)

    order_role = payload.get("order_role", "OP1")
    if order_role == "OP2":
        volume = round(op1_lot * 2, 2)
    elif order_role == "OP3":
        volume = round(op1_lot * 3, 2)
    else:
        volume = op1_lot

    # Ambil harga realtime terkini dari terminal sub-proses
    tick = mt5.symbol_info_tick(symbol)
    order_type = payload.get("type", mt5.ORDER_TYPE_BUY)
    
    if payload.get("action") == mt5.TRADE_ACTION_DEAL:
        if order_type == mt5.ORDER_TYPE_BUY:
            price = tick.ask if tick else payload.get("price", 0.0)
        else:
            price = tick.bid if tick else payload.get("price", 0.0)
    else:
        price = payload.get("price", 0.0)

    # 3. Rakit Request Order MT5
    req = {
        "action": payload.get("action", mt5.TRADE_ACTION_DEAL),
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": round(price, digits),
        "deviation": payload.get("deviation", 20),
        "magic": payload.get("magic", 999999),
        "comment": payload.get("comment", f"{strategy_name}_{order_role}"),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_mode,
    }

    # Pasang SL & TP jika ada
    sl_val = payload.get("sl", 0.0)
    tp_val = payload.get("tp", 0.0)
    if sl_val and sl_val > 0:
        req["sl"] = round(sl_val, digits)
    if tp_val and tp_val > 0:
        req["tp"] = round(tp_val, digits)

    res = mt5.order_send(req)

    # Jika gagal 10016 (Invalid Stops) saat market order, retry tanpa stops (TP dihandle sistem)
    if res and res.retcode == 10016 and payload.get("action") == mt5.TRADE_ACTION_DEAL:
        print(cprint(f"⚠️ {pid_tag} Retcode 10016 (Invalid stops). Mengirim ulang market deal tanpa stops...", Colors.YELLOW))
        req.pop("sl", None)
        req.pop("tp", None)
        res = mt5.order_send(req)

    # 4. Kirim WA Notification dengan Footer Label Identitas Akun & Bot
    wa_message = payload.get("wa_message")
    if wa_message and res and res.retcode == mt5.TRADE_RETCODE_DONE:
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
            print(cprint(f"📲 {pid_tag} WA Notif terkirim dengan Label Footer Akun.", Colors.GREEN))
        except Exception as e:
            print(cprint(f"⚠️ {pid_tag} Gagal insert WA outbox: {e}", Colors.RED))

    # 5. Shutdown koneksi MT5 sub-proses
    mt5.shutdown()

    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        msg = f"{pid_tag} ✅ Order Sukses! Ticket: #{res.order} | Vol: {res.volume} | Price: {res.price} | Akun: {acc_info['name']}"
        print(cprint(msg, Colors.GREEN))
        return {
            "key": acc_info['key'],
            "login": acc_info['login'],
            "success": True,
            "ticket": res.order,
            "order": res.order,
            "price": res.price,
            "volume": res.volume,
            "retcode": res.retcode,
            "comment": res.comment
        }
    else:
        err_comment = res.comment if res else "Unknown Error"
        retcode = res.retcode if res else -1
        msg = f"{pid_tag} ❌ Order Gagal! Retcode: {retcode} ({err_comment}) | Akun: {acc_info['name']}"
        print(cprint(msg, Colors.RED))
        return {
            "key": acc_info['key'],
            "login": acc_info['login'],
            "success": False,
            "error": err_comment,
            "retcode": retcode,
            "order": None
        }

def dispatch_multi_account_order(strategy_name: str, payload: dict) -> tuple[MultiOrderResult | None, list[dict]]:
    """
    Fungsi penembak utama: Membuka ProcessPoolExecutor untuk mengeksekusi order
    ke seluruh akun target secara paralel murni tanpa bentrok.
    Returns: (primary_order_result, all_results_list)
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        print(cprint(f"⚠️ [MultiAccount] Tidak ada akun target aktif untuk {strategy_name}", Colors.YELLOW))
        return None, []

    print(cprint(f"⚡ [MultiAccount Dispatcher] Memulai eksekusi paralel murni ke {len(accounts)} akun ({', '.join([a['key'] for a in accounts])})...", Colors.MAGENTA))

    results = []
    with ProcessPoolExecutor(max_workers=max(1, len(accounts))) as executor:
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
                results.append({"key": acc_target['key'], "success": False, "error": str(exc), "retcode": -1, "order": None})

    # Sort results according to original order
    order_map = {acc['key']: idx for idx, acc in enumerate(accounts)}
    results.sort(key=lambda x: order_map.get(x['key'], 999))

    # Temukan akun primer pertama yang berhasil (biasanya ACC1)
    primary_res = None
    for r in results:
        if r.get("success") and r.get("order"):
            primary_res = MultiOrderResult(
                retcode=r.get("retcode", mt5.TRADE_RETCODE_DONE),
                order=r.get("order"),
                price=r.get("price", payload.get("price", 0.0)),
                volume=r.get("volume", 0.01),
                comment=r.get("comment", "")
            )
            break

    return primary_res, results
