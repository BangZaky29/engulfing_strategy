# =====================================================
# mt5_client/multi_account_dispatcher.py
# Multi-Account MT5 Dispatcher (Direct Terminal Worker Architecture)
# 100% Bebas mt5.login() Switching - AutoTrading Tetap ALLOWED 🟢
# =====================================================

import os
import time
import uuid
from datetime import datetime, timedelta
from collections import namedtuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import MetaTrader5 as mt5
from database.supabase_client import execute_supabase
from utils.colors import cprint, Colors

MultiOrderResult = namedtuple("MultiOrderResult", ["retcode", "order", "price", "volume", "comment", "all_results"], defaults=[None, None, 0.0, 0.0, "", []])

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

        if login > 0:
            accounts.append({
                "key": key,
                "name": name,
                "path": path,
                "login": login,
                "password": password,
                "server": server
            })

    return accounts

def _worker_audit_account(acc_info: dict) -> dict:
    """Worker sub-process untuk mengaudit dana & kesehatan akun tertentu via portable path."""
    import MetaTrader5 as mt5_worker
    import os

    path = acc_info.get("path", "")
    if path and os.path.exists(path):
        init_ok = mt5_worker.initialize(path=path, portable=True, timeout=15000)
    else:
        init_ok = mt5_worker.initialize(timeout=15000)

    if not init_ok:
        err = mt5_worker.last_error()
        return {
            "key": acc_info['key'],
            "name": acc_info['name'],
            "login": acc_info['login'],
            "server": acc_info['server'],
            "connected": False,
            "error": f"Init failed: {err}"
        }

    acc = mt5_worker.account_info()
    term = mt5_worker.terminal_info()

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
        ping_str = f"{ping_ms} ms 🟡 (Good)"
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

    actual_login = getattr(acc, "login", acc_info['login']) if acc else acc_info['login']
    actual_server = getattr(acc, "server", acc_info['server']) if acc else acc_info['server']

    res = {
        "key": acc_info['key'],
        "name": acc_info['name'],
        "login": actual_login,
        "server": actual_server,
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

    mt5_worker.shutdown()
    return res

def _read_local_account_funds(acc_info: dict) -> dict:
    """Membaca akun primer (ACC1) langsung dari sesi MT5 utama tanpa shutdown."""
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
        ping_str = f"{ping_ms} ms 🟡 (Good)"
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

    return {
        "key": acc_info['key'],
        "name": acc_info['name'],
        "login": getattr(acc, "login", acc_info['login']) if acc else acc_info['login'],
        "server": getattr(acc, "server", acc_info['server']) if acc else acc_info['server'],
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
    Mengambil rincian dana & kesehatan semua akun target langsung dari terminalnya masing-masing.
    Hanya ACC1 yang dibaca dari sesi lokal, sedangkan akun lain (ACC2, ACC3) dibaca via worker sub-process.
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        return []

    from mt5_client.terminal_launcher import ensure_all_target_terminals_running
    ensure_all_target_terminals_running(accounts)

    results = []
    secondary_accounts = []

    for acc in accounts:
        if acc['key'] == 'ACC1':
            results.append(_read_local_account_funds(acc))
        else:
            secondary_accounts.append(acc)

    if secondary_accounts:
        with ProcessPoolExecutor(max_workers=len(secondary_accounts)) as executor:
            futures = {executor.submit(_worker_audit_account, acc): acc for acc in secondary_accounts}
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    results.append(res)
                except Exception as e:
                    acc = futures[fut]
                    results.append({
                        "key": acc['key'],
                        "name": acc['name'],
                        "login": acc['login'],
                        "server": acc['server'],
                        "connected": False,
                        "error": str(e)
                    })

    order_map = {acc['key']: i for i, acc in enumerate(accounts)}
    results.sort(key=lambda x: order_map.get(x.get('key', ''), 99))
    return results

def _worker_execute_account_order(acc_info: dict, strategy_name: str, payload: dict) -> dict:
    """Worker sub-process untuk mengeksekusi order pada terminal akun tertentu via portable path."""
    import MetaTrader5 as mt5_worker
    import os

    path = acc_info.get("path", "")
    if path and os.path.exists(path):
        init_ok = mt5_worker.initialize(path=path, portable=True, timeout=15000)
    else:
        init_ok = mt5_worker.initialize(timeout=15000)

    if not init_ok:
        err = mt5_worker.last_error()
        err_msg = f"Init terminal failed untuk {acc_info['name']} ({acc_info['key']}): {err}"
        return {"key": acc_info['key'], "login": acc_info['login'], "name": acc_info['name'], "success": False, "error": err_msg, "retcode": -1, "order": None}

    symbol = payload.get("symbol", "XAUUSD")
    mt5_worker.symbol_select(symbol, True)
    symbol_info = mt5_worker.symbol_info(symbol)
    digits = symbol_info.digits if symbol_info else 2

    # Filling mode detection
    filling_mode = mt5_worker.ORDER_FILLING_FOK
    if symbol_info:
        if (symbol_info.filling_mode & 1) == 1:
            filling_mode = mt5_worker.ORDER_FILLING_FOK
        elif (symbol_info.filling_mode & 2) == 2:
            filling_mode = mt5_worker.ORDER_FILLING_IOC
        else:
            filling_mode = mt5_worker.ORDER_FILLING_RETURN

    # Hitung Lot Dinamis Akun
    acc = mt5_worker.account_info()
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

    # Ambil harga realtime terkini
    tick = mt5_worker.symbol_info_tick(symbol)
    order_type = payload.get("type", mt5_worker.ORDER_TYPE_BUY)

    if payload.get("action") == mt5_worker.TRADE_ACTION_DEAL:
        if order_type == mt5_worker.ORDER_TYPE_BUY:
            price = tick.ask if tick else payload.get("price", 0.0)
        else:
            price = tick.bid if tick else payload.get("price", 0.0)
    else:
        price = payload.get("price", 0.0)

    # Request Order MT5
    req = {
        "action": payload.get("action", mt5_worker.TRADE_ACTION_DEAL),
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": round(price, digits),
        "deviation": payload.get("deviation", 20),
        "magic": payload.get("magic", 999999),
        "comment": payload.get("comment", f"{strategy_name}_{order_role}"),
        "type_time": mt5_worker.ORDER_TIME_GTC,
        "type_filling": filling_mode if payload.get("action") == mt5_worker.TRADE_ACTION_DEAL else mt5_worker.ORDER_FILLING_RETURN,
    }

    # Pasang SL & TP jika ada
    sl_val = payload.get("sl", 0.0)
    tp_val = payload.get("tp", 0.0)
    if sl_val and sl_val > 0:
        req["sl"] = round(sl_val, digits)
    if tp_val and tp_val > 0:
        req["tp"] = round(tp_val, digits)

    res = mt5_worker.order_send(req)

    # Jika gagal 10016 (Invalid Stops) saat market order, retry tanpa stops
    if res and res.retcode == 10016 and payload.get("action") == mt5_worker.TRADE_ACTION_DEAL:
        req.pop("sl", None)
        req.pop("tp", None)
        res = mt5_worker.order_send(req)

    actual_login = acc.login if acc else acc_info['login']
    mt5_worker.shutdown()

    if res and res.retcode == mt5_worker.TRADE_RETCODE_DONE:
        return {
            "key": acc_info['key'],
            "name": acc_info['name'],
            "login": actual_login,
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
        return {
            "key": acc_info['key'],
            "name": acc_info['name'],
            "login": actual_login,
            "success": False,
            "error": err_comment,
            "retcode": retcode,
            "order": None
        }

def _execute_local_account_order(acc_info: dict, strategy_name: str, payload: dict) -> dict:
    """Mengeksekusi order pada akun primer (ACC1) langsung di thread utama tanpa login switch."""
    symbol = payload.get("symbol", "XAUUSD")
    mt5.symbol_select(symbol, True)
    symbol_info = mt5.symbol_info(symbol)
    digits = symbol_info.digits if symbol_info else 2

    filling_mode = mt5.ORDER_FILLING_FOK
    if symbol_info:
        if (symbol_info.filling_mode & 1) == 1:
            filling_mode = mt5.ORDER_FILLING_FOK
        elif (symbol_info.filling_mode & 2) == 2:
            filling_mode = mt5.ORDER_FILLING_IOC
        else:
            filling_mode = mt5.ORDER_FILLING_RETURN

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

    tick = mt5.symbol_info_tick(symbol)
    order_type = payload.get("type", mt5.ORDER_TYPE_BUY)

    if payload.get("action") == mt5.TRADE_ACTION_DEAL:
        if order_type == mt5.ORDER_TYPE_BUY:
            price = tick.ask if tick else payload.get("price", 0.0)
        else:
            price = tick.bid if tick else payload.get("price", 0.0)
    else:
        price = payload.get("price", 0.0)

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
        "type_filling": filling_mode if payload.get("action") == mt5.TRADE_ACTION_DEAL else mt5.ORDER_FILLING_RETURN,
    }

    sl_val = payload.get("sl", 0.0)
    tp_val = payload.get("tp", 0.0)
    if sl_val and sl_val > 0:
        req["sl"] = round(sl_val, digits)
    if tp_val and tp_val > 0:
        req["tp"] = round(tp_val, digits)

    res = mt5.order_send(req)

    if res and res.retcode == 10016 and payload.get("action") == mt5.TRADE_ACTION_DEAL:
        print(cprint(f"⚠️ [{acc_info['key']}] Retcode 10016 (Invalid stops). Mengirim ulang deal tanpa stops...", Colors.YELLOW))
        req.pop("sl", None)
        req.pop("tp", None)
        res = mt5.order_send(req)

    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        msg = f"[{acc_info['key']}] ✅ Order Sukses! Ticket: #{res.order} | Vol: {res.volume} | Price: {res.price} | Akun: {acc_info['name']}"
        print(cprint(msg, Colors.GREEN))
        return {
            "key": acc_info['key'],
            "name": acc_info['name'],
            "login": acc.login if acc else acc_info['login'],
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
        msg = f"[{acc_info['key']}] ❌ Order Gagal! Retcode: {retcode} ({err_comment}) | Akun: {acc_info['name']}"
        print(cprint(msg, Colors.RED))
        return {
            "key": acc_info['key'],
            "name": acc_info['name'],
            "login": acc.login if acc else acc_info['login'],
            "success": False,
            "error": err_comment,
            "retcode": retcode,
            "order": None
        }

def dispatch_multi_account_order(strategy_name: str, payload: dict) -> tuple[MultiOrderResult | None, list[dict]]:
    """
    Fungsi penembak utama: Mengeksekusi order ke seluruh akun target secara instan & simultan.
    Hanya ACC1 yang dieksekusi di local thread (jika ACC1 termasuk target).
    Akun lain (ACC2, ACC3) dieksekusi via worker sub-process terisolasi.
    Returns: (primary_order_result, all_results_list)
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        print(cprint(f"⚠️ [MultiAccount] Tidak ada akun target aktif untuk {strategy_name}", Colors.YELLOW))
        return None, []

    print(cprint(f"⚡ [MultiAccount Dispatcher] Memulai eksekusi ke {len(accounts)} akun ({', '.join([a['key'] for a in accounts])})...", Colors.MAGENTA))

    results = []
    local_acc = None
    worker_accounts = []

    for acc in accounts:
        if acc['key'] == 'ACC1':
            local_acc = acc
        else:
            worker_accounts.append(acc)

    # 1. Eksekusi ACC1 di thread utama jika ACC1 ada di target
    if local_acc:
        try:
            primary_res_dict = _execute_local_account_order(local_acc, strategy_name, payload)
            results.append(primary_res_dict)
        except Exception as exc:
            print(cprint(f"⚠️ Error eksekusi primer {local_acc['key']}: {exc}", Colors.RED))
            results.append({"key": local_acc['key'], "name": local_acc['name'], "login": local_acc['login'], "success": False, "error": str(exc), "retcode": -1, "order": None})

    # 2. Eksekusi akun worker (ACC2, ACC3) secara paralel via sub-process
    if worker_accounts:
        with ProcessPoolExecutor(max_workers=len(worker_accounts)) as executor:
            future_to_acc = {executor.submit(_worker_execute_account_order, acc, strategy_name, payload): acc for acc in worker_accounts}
            for fut in as_completed(future_to_acc):
                acc = future_to_acc[fut]
                try:
                    res_dict = fut.result()
                    results.append(res_dict)
                    if res_dict.get("success"):
                        print(cprint(f"[{acc['key']}] ✅ Order Sukses! Ticket: #{res_dict.get('order')} | Vol: {res_dict.get('volume')} | Price: {res_dict.get('price')} | Akun: {acc['name']}", Colors.GREEN))
                    else:
                        print(cprint(f"[{acc['key']}] ❌ Order Gagal! Retcode: {res_dict.get('retcode')} ({res_dict.get('error')}) | Akun: {acc['name']}", Colors.RED))
                except Exception as exc:
                    print(cprint(f"⚠️ Error eksekusi sekunder {acc['key']}: {exc}", Colors.RED))
                    results.append({"key": acc['key'], "name": acc['name'], "login": acc['login'], "success": False, "error": str(exc), "retcode": -1, "order": None})

    # Temukan akun pertama yang berhasil untuk return ke caller
    primary_res = None
    for r in results:
        if r.get("success") and r.get("order"):
            primary_res = MultiOrderResult(
                retcode=r.get("retcode", mt5.TRADE_RETCODE_DONE),
                order=r.get("order"),
                price=r.get("price", payload.get("price", 0.0)),
                volume=r.get("volume", 0.01),
                comment=r.get("comment", ""),
                all_results=results
            )
            break

    return primary_res, results

def get_account_footer_label(strategy_name: str) -> str:
    """
    Membuat label footer akun yang bersih dan terpadu untuk pesan notifikasi Signal / OP.
    Contoh:
    🏷️ *AKUN:* ACC1 (Headway_Demo_1 | 5034723) | *BOT:* RCS
    atau (jika multi-akun):
    🏷️ *AKUN:* ACC1 (5034723), ACC3 (5597691) | *BOT:* RCS
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        return f"\n\n🏷️ *BOT:* {strategy_name.upper()}"

    if len(accounts) == 1:
        acc = accounts[0]
        return f"\n\n🏷️ *AKUN:* {acc['key']} ({acc['name']} | {acc['login']}) | *BOT:* {strategy_name.upper()}"
    else:
        acc_strs = [f"{a['key']} ({a['login']})" for a in accounts]
        return f"\n\n🏷️ *AKUN:* {', '.join(acc_strs)} | *BOT:* {strategy_name.upper()}"

def _worker_cancel_pending_orders(acc_info: dict, symbol: str, magic_numbers: list[int]) -> int:
    """Worker sub-process untuk membatalkan pending order pada akun sekunder."""
    import MetaTrader5 as mt5_worker
    import os

    path = acc_info.get("path", "")
    if path and os.path.exists(path):
        init_ok = mt5_worker.initialize(path=path, portable=True, timeout=15000)
    else:
        init_ok = mt5_worker.initialize(timeout=15000)

    if not init_ok:
        return 0

    orders = mt5_worker.orders_get(symbol=symbol)
    canceled = 0
    if orders:
        for ord_item in orders:
            if not magic_numbers or ord_item.magic in magic_numbers:
                req = {
                    "action": mt5_worker.TRADE_ACTION_REMOVE,
                    "order": ord_item.ticket
                }
                res = mt5_worker.order_send(req)
                if res and res.retcode == mt5_worker.TRADE_RETCODE_DONE:
                    canceled += 1

    mt5_worker.shutdown()
    return canceled

def cancel_multi_account_pending_orders(strategy_name: str, symbol: str, magic_numbers: list[int] | None = None) -> int:
    """Membatalkan seluruh pending order dari semua akun target (ACC1, ACC2, ACC3)."""
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        orders = mt5.orders_get(symbol=symbol)
        cnt = 0
        if orders:
            for ord_item in orders:
                if not magic_numbers or ord_item.magic in magic_numbers:
                    req = {"action": mt5.TRADE_ACTION_REMOVE, "order": ord_item.ticket}
                    res = mt5.order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        cnt += 1
        return cnt

    local_acc = None
    worker_accounts = []
    for acc in accounts:
        if acc['key'] == 'ACC1':
            local_acc = acc
        else:
            worker_accounts.append(acc)

    total_canceled = 0

    # 1. Cancel akun primer di thread utama jika ada di target
    if local_acc:
        orders1 = mt5.orders_get(symbol=symbol)
        if orders1:
            for ord_item in orders1:
                if not magic_numbers or ord_item.magic in magic_numbers:
                    req = {"action": mt5.TRADE_ACTION_REMOVE, "order": ord_item.ticket}
                    res = mt5.order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        total_canceled += 1

    # 2. Cancel akun worker via sub-process
    if worker_accounts:
        with ProcessPoolExecutor(max_workers=len(worker_accounts)) as executor:
            futures = [executor.submit(_worker_cancel_pending_orders, acc, symbol, magic_numbers or []) for acc in worker_accounts]
            for fut in as_completed(futures):
                try:
                    total_canceled += fut.result()
                except Exception:
                    pass

    return total_canceled

def _worker_query_account_deals_pnl(acc_info: dict, symbol: str, tickets: list[int]) -> dict:
    """Worker sub-process untuk mengambil real PnL dari deals history broker akun sekunder."""
    import MetaTrader5 as mt5_worker
    import os
    import time

    path = acc_info.get("path", "")
    if path and os.path.exists(path):
        init_ok = mt5_worker.initialize(path=path, portable=True, timeout=15000)
    else:
        init_ok = mt5_worker.initialize(timeout=15000)

    if not init_ok:
        return {"key": acc_info['key'], "name": acc_info['name'], "login": acc_info['login'], "profit": 0.0, "deals_count": 0}

    total_pnl = 0.0
    matched_deals = 0

    if tickets:
        for t in tickets:
            t_pnl = 0.0
            found_out = False
            for _ in range(15):
                deals = mt5_worker.history_deals_get(position=t)
                if deals:
                    for d in deals:
                        if d.entry == mt5_worker.DEAL_ENTRY_OUT or d.entry == 2:
                            t_pnl += (d.profit + d.swap + d.commission)
                            found_out = True
                    if found_out:
                        break
                time.sleep(0.2)

            if found_out:
                total_pnl += t_pnl
                matched_deals += 1
            else:
                now = int(time.time())
                deals = mt5_worker.history_deals_get(now - 86400, now + 3600)
                if deals:
                    for d in deals:
                        if (d.position_id == t or d.order == t) and (d.entry == mt5_worker.DEAL_ENTRY_OUT or d.entry == 2):
                            total_pnl += (d.profit + d.swap + d.commission)
                            matched_deals += 1
                            break
    else:
        now = int(time.time())
        deals = mt5_worker.history_deals_get(now - 3600, now + 3600)
        if deals:
            for d in reversed(deals):
                if d.symbol == symbol and (d.entry == mt5_worker.DEAL_ENTRY_OUT or d.entry == 2):
                    total_pnl = (d.profit + d.swap + d.commission)
                    matched_deals = 1
                    break

    actual_login = getattr(mt5_worker.account_info(), "login", acc_info['login'])
    mt5_worker.shutdown()
    return {
        "key": acc_info['key'],
        "name": acc_info['name'],
        "login": actual_login,
        "profit": round(total_pnl, 2),
        "deals_count": matched_deals
    }

def get_multi_account_cycle_profit(strategy_name: str, symbol: str, tickets_per_account: dict) -> dict:
    """
    Mengambil real profit tertutup dari SELURUH akun target untuk siklus yang baru saja selesai.
    tickets_per_account: dict misal {"ACC1": [999120865], "ACC3": [999121747]}
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        return {"accounts": {}, "total_profit": 0.0}

    local_acc = None
    worker_accounts = []
    for acc in accounts:
        if acc['key'] == 'ACC1':
            local_acc = acc
        else:
            worker_accounts.append(acc)

    results_map = {}
    total_profit = 0.0

    # 1. Query ACC1 di thread utama jika ada di target
    if local_acc:
        p1_pnl = 0.0
        p1_tickets = tickets_per_account.get(local_acc['key'], [])
        if p1_tickets:
            for t in p1_tickets:
                t_pnl = 0.0
                found_out = False
                for _ in range(15):
                    deals = mt5.history_deals_get(position=t)
                    if deals:
                        for d in deals:
                            if d.entry == mt5.DEAL_ENTRY_OUT or d.entry == 2:
                                t_pnl += (d.profit + d.swap + d.commission)
                                found_out = True
                        if found_out:
                            break
                    time.sleep(0.2)
                if found_out:
                    p1_pnl += t_pnl
                else:
                    now = int(time.time())
                    deals = mt5.history_deals_get(now - 86400, now + 3600)
                    if deals:
                        for d in deals:
                            if (d.position_id == t or d.order == t) and (d.entry == mt5.DEAL_ENTRY_OUT or d.entry == 2):
                                p1_pnl += (d.profit + d.swap + d.commission)
                                break
        else:
            now = int(time.time())
            deals = mt5.history_deals_get(now - 3600, now + 3600)
            if deals:
                for d in reversed(deals):
                    if d.symbol == symbol and (d.entry == mt5.DEAL_ENTRY_OUT or d.entry == 2):
                        p1_pnl = (d.profit + d.swap + d.commission)
                        break

        results_map[local_acc['key']] = {
            "key": local_acc['key'],
            "name": local_acc['name'],
            "login": getattr(mt5.account_info(), "login", local_acc['login']),
            "profit": round(p1_pnl, 2)
        }
        total_profit += p1_pnl

    # 2. Query akun worker via sub-process
    if worker_accounts:
        with ProcessPoolExecutor(max_workers=len(worker_accounts)) as executor:
            future_to_acc = {
                executor.submit(
                    _worker_query_account_deals_pnl, 
                    acc, 
                    symbol, 
                    tickets_per_account.get(acc['key'], [])
                ): acc for acc in worker_accounts
            }
            for fut in as_completed(future_to_acc):
                acc = future_to_acc[fut]
                try:
                    res = fut.result()
                    results_map[acc['key']] = res
                    total_profit += res.get("profit", 0.0)
                except Exception as e:
                    print(cprint(f"⚠️ Error audit profit deal {acc['key']}: {e}", Colors.RED))
                    results_map[acc['key']] = {"key": acc['key'], "name": acc['name'], "login": acc['login'], "profit": 0.0}

    # Urutkan berdasarkan urutan akun target
    order_map = {acc['key']: i for i, acc in enumerate(accounts)}
    sorted_accounts = dict(sorted(results_map.items(), key=lambda item: order_map.get(item[0], 99)))

    return {
        "accounts": sorted_accounts,
        "total_profit": round(total_profit, 2)
    }

def _worker_check_account_tickets_active(acc_info: dict, symbol: str, tickets: list[int]) -> dict:
    """Worker sub-process untuk memeriksa apakah ada tiket dari list yang masih aktif (posisi/order) di terminal sekunder."""
    import MetaTrader5 as mt5_worker
    import os

    path = acc_info.get("path", "")
    if path and os.path.exists(path):
        init_ok = mt5_worker.initialize(path=path, portable=True, timeout=15000)
    else:
        init_ok = mt5_worker.initialize(timeout=15000)

    if not init_ok:
        return {
            "key": acc_info['key'],
            "connected": False,
            "active_tickets": tickets,
            "has_active": len(tickets) > 0,
            "positions_map": {},
            "orders_map": {}
        }

    positions = mt5_worker.positions_get(symbol=symbol)
    orders = mt5_worker.orders_get(symbol=symbol)

    active_tickets = []
    pos_map = {}
    ord_map = {}

    tkt_set = set(tickets) if tickets else set()
    if positions:
        for p in positions:
            if not tkt_set or p.ticket in tkt_set:
                active_tickets.append(p.ticket)
                pos_map[p.ticket] = {
                    "ticket": p.ticket,
                    "price_open": p.price_open,
                    "profit": p.profit,
                    "type": p.type,
                    "volume": p.volume
                }
    if orders:
        for o in orders:
            if not tkt_set or o.ticket in tkt_set:
                if o.ticket not in active_tickets:
                    active_tickets.append(o.ticket)
                ord_map[o.ticket] = {
                    "ticket": o.ticket,
                    "price_open": o.price_open,
                    "state": o.state,
                    "type": o.type,
                    "volume": getattr(o, 'volume_initial', 0.0)
                }

    mt5_worker.shutdown()
    return {
        "key": acc_info['key'],
        "connected": True,
        "active_tickets": active_tickets,
        "has_active": len(active_tickets) > 0,
        "positions_map": pos_map,
        "orders_map": ord_map
    }

def check_multi_account_tickets_active(strategy_name: str, symbol: str, tickets_per_account: dict) -> dict:
    """
    Memeriksa status aktif (posisi/order) dari tiket-tiket di seluruh akun target.
    tickets_per_account: dict misal {"ACC2": [1000730011, 1000730133]}
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        local_pos = mt5.positions_get(symbol=symbol)
        local_ord = mt5.orders_get(symbol=symbol)
        all_tkt = []
        for t_list in tickets_per_account.values():
            all_tkt.extend(t_list)
        tkt_set = set(all_tkt) if all_tkt else set()
        active = []
        pos_map = {}
        ord_map = {}
        if local_pos:
            for p in local_pos:
                if not tkt_set or p.ticket in tkt_set:
                    active.append(p.ticket)
                    pos_map[p.ticket] = {"ticket": p.ticket, "price_open": p.price_open, "profit": p.profit, "type": p.type, "volume": p.volume}
        if local_ord:
            for o in local_ord:
                if not tkt_set or o.ticket in tkt_set:
                    if o.ticket not in active: active.append(o.ticket)
                    ord_map[o.ticket] = {"ticket": o.ticket, "price_open": o.price_open, "state": o.state, "type": o.type, "volume": getattr(o, 'volume_initial', 0.0)}
        return {
            "has_active": len(active) > 0,
            "accounts": {"ACC1": {"active_tickets": active, "positions_map": pos_map, "orders_map": ord_map}}
        }

    local_acc = None
    worker_accounts = []
    for acc in accounts:
        if acc['key'] == 'ACC1':
            local_acc = acc
        else:
            worker_accounts.append(acc)

    results_map = {}
    overall_has_active = False

    # 1. Check local ACC1 if targeted
    if local_acc:
        tkts = tickets_per_account.get('ACC1', [])
        tkt_set = set(tkts) if tkts else set()
        local_pos = mt5.positions_get(symbol=symbol)
        local_ord = mt5.orders_get(symbol=symbol)
        active = []
        pos_map = {}
        ord_map = {}
        if local_pos:
            for p in local_pos:
                if not tkt_set or p.ticket in tkt_set:
                    active.append(p.ticket)
                    pos_map[p.ticket] = {"ticket": p.ticket, "price_open": p.price_open, "profit": p.profit, "type": p.type, "volume": p.volume}
        if local_ord:
            for o in local_ord:
                if not tkt_set or o.ticket in tkt_set:
                    if o.ticket not in active: active.append(o.ticket)
                    ord_map[o.ticket] = {"ticket": o.ticket, "price_open": o.price_open, "state": o.state, "type": o.type, "volume": getattr(o, 'volume_initial', 0.0)}
        
        has_act = len(active) > 0
        if has_act: overall_has_active = True
        results_map['ACC1'] = {
            "key": 'ACC1',
            "connected": True,
            "active_tickets": active,
            "has_active": has_act,
            "positions_map": pos_map,
            "orders_map": ord_map
        }

    # 2. Check worker accounts
    if worker_accounts:
        with ProcessPoolExecutor(max_workers=len(worker_accounts)) as executor:
            future_to_acc = {
                executor.submit(
                    _worker_check_account_tickets_active,
                    acc,
                    symbol,
                    tickets_per_account.get(acc['key'], [])
                ): acc for acc in worker_accounts
            }
            for fut in as_completed(future_to_acc):
                acc = future_to_acc[fut]
                try:
                    res = fut.result()
                    results_map[acc['key']] = res
                    if res.get("has_active"):
                        overall_has_active = True
                except Exception as exc:
                    print(cprint(f"⚠️ Error check worker tickets {acc['key']}: {exc}", Colors.RED))
                    overall_has_active = True
                    results_map[acc['key']] = {
                        "key": acc['key'],
                        "connected": False,
                        "active_tickets": tickets_per_account.get(acc['key'], []),
                        "has_active": True,
                        "positions_map": {},
                        "orders_map": {}
                    }

    return {
        "has_active": overall_has_active,
        "accounts": results_map
    }

def _worker_close_all_positions(acc_info: dict, symbol: str, magic_numbers: list[int]) -> int:
    """Worker sub-process untuk mengeksekusi CLOSE ALL posisi & pending order pada terminal sekunder."""
    import MetaTrader5 as mt5_worker
    import os

    path = acc_info.get("path", "")
    if path and os.path.exists(path):
        init_ok = mt5_worker.initialize(path=path, portable=True, timeout=15000)
    else:
        init_ok = mt5_worker.initialize(timeout=15000)

    if not init_ok:
        return 0

    canceled = 0
    # 1. Close positions
    positions = mt5_worker.positions_get(symbol=symbol)
    if positions:
        for p in positions:
            if not magic_numbers or p.magic in magic_numbers:
                action_type = mt5_worker.ORDER_TYPE_SELL if p.type == mt5_worker.ORDER_TYPE_BUY else mt5_worker.ORDER_TYPE_BUY
                tick = mt5_worker.symbol_info_tick(symbol)
                price = tick.bid if action_type == mt5_worker.ORDER_TYPE_SELL else tick.ask if tick else p.price_open
                req = {
                    "action": mt5_worker.TRADE_ACTION_DEAL,
                    "position": p.ticket,
                    "symbol": symbol,
                    "volume": p.volume,
                    "type": action_type,
                    "price": price,
                    "deviation": 20,
                    "magic": p.magic,
                    "comment": "MRCV_CLOSE_ALL",
                    "type_time": mt5_worker.ORDER_TIME_GTC,
                    "type_filling": mt5_worker.ORDER_FILLING_IOC
                }
                res = mt5_worker.order_send(req)
                if res and res.retcode == mt5_worker.TRADE_RETCODE_DONE:
                    canceled += 1

    # 2. Cancel pending orders
    orders = mt5_worker.orders_get(symbol=symbol)
    if orders:
        for o in orders:
            if not magic_numbers or o.magic in magic_numbers:
                req = {"action": mt5_worker.TRADE_ACTION_REMOVE, "order": o.ticket}
                res = mt5_worker.order_send(req)
                if res and res.retcode == mt5_worker.TRADE_RETCODE_DONE:
                    canceled += 1

    mt5_worker.shutdown()
    return canceled

def close_multi_account_all_positions(strategy_name: str, symbol: str, magic_numbers: list[int]) -> int:
    """Mengeksekusi Close ALL posisi & pending order di seluruh akun target strategy (ACC1, ACC2, ACC3)."""
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        from strategies.recovery_marubozu.orders.mrcv_order_manager import close_all_positions as local_close
        local_close(symbol, magic_numbers)
        return 0

    local_acc = None
    worker_accounts = []
    for acc in accounts:
        if acc['key'] == 'ACC1':
            local_acc = acc
        else:
            worker_accounts.append(acc)

    total_closed = 0

    # 1. Close local ACC1
    if local_acc:
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for p in positions:
                if not magic_numbers or p.magic in magic_numbers:
                    action_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                    tick = mt5.symbol_info_tick(symbol)
                    price = tick.bid if action_type == mt5.ORDER_TYPE_SELL else tick.ask if tick else p.price_open
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": p.ticket,
                        "symbol": symbol,
                        "volume": p.volume,
                        "type": action_type,
                        "price": price,
                        "deviation": 20,
                        "magic": p.magic,
                        "comment": "MRCV_CLOSE_ALL",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC
                    }
                    res = mt5.order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        total_closed += 1
        orders = mt5.orders_get(symbol=symbol)
        if orders:
            for o in orders:
                if not magic_numbers or o.magic in magic_numbers:
                    req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                    res = mt5.order_send(req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        total_closed += 1

    # 2. Close worker accounts
    if worker_accounts:
        with ProcessPoolExecutor(max_workers=len(worker_accounts)) as executor:
            futures = [executor.submit(_worker_close_all_positions, acc, symbol, magic_numbers) for acc in worker_accounts]
            for fut in as_completed(futures):
                try:
                    total_closed += fut.result()
                except Exception:
                    pass

    return total_closed

def _worker_get_account_positions_profit(acc_info: dict, symbol: str, magic_numbers: list[int]) -> float:
    """Worker sub-process untuk menghitung total floating profit posisi aktif pada terminal sekunder."""
    import MetaTrader5 as mt5_worker
    import os

    path = acc_info.get("path", "")
    if path and os.path.exists(path):
        init_ok = mt5_worker.initialize(path=path, portable=True, timeout=15000)
    else:
        init_ok = mt5_worker.initialize(timeout=15000)

    if not init_ok:
        return 0.0

    positions = mt5_worker.positions_get(symbol=symbol)
    profit = 0.0
    if positions:
        for p in positions:
            if not magic_numbers or p.magic in magic_numbers:
                profit += (p.profit + p.swap + getattr(p, 'commission', 0.0))

    mt5_worker.shutdown()
    return profit

def get_multi_account_positions_profit(strategy_name: str, symbol: str, magic_numbers: list[int]) -> float:
    """Menghitung total floating profit posisi aktif dari seluruh akun target."""
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        positions = mt5.positions_get(symbol=symbol)
        if not positions: return 0.0
        return sum(p.profit + p.swap + getattr(p, 'commission', 0.0) for p in positions if not magic_numbers or p.magic in magic_numbers)

    local_acc = None
    worker_accounts = []
    for acc in accounts:
        if acc['key'] == 'ACC1':
            local_acc = acc
        else:
            worker_accounts.append(acc)

    total_floating = 0.0

    # 1. Local ACC1
    if local_acc:
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for p in positions:
                if not magic_numbers or p.magic in magic_numbers:
                    total_floating += (p.profit + p.swap + getattr(p, 'commission', 0.0))

    # 2. Worker accounts
    if worker_accounts:
        with ProcessPoolExecutor(max_workers=len(worker_accounts)) as executor:
            futures = [executor.submit(_worker_get_account_positions_profit, acc, symbol, magic_numbers) for acc in worker_accounts]
            for fut in as_completed(futures):
                try:
                    total_floating += fut.result()
                except Exception:
                    pass

    return round(total_floating, 2)


