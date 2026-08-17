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

    res = {
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
    Tanpa memanggil mt5.login() sehingga AutoTrading tidak pernah mati.
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        return []

    from mt5_client.terminal_launcher import ensure_all_target_terminals_running
    ensure_all_target_terminals_running(accounts)

    results = []
    secondary_accounts = []

    for idx, acc in enumerate(accounts):
        if idx == 0:
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
    Tanpa memanggil mt5.login() sehingga AutoTrading tetap ALLOWED 🟢.
    Mengirim notifikasi WhatsApp ke setiap akun yang berhasil dieksekusi.
    Returns: (primary_order_result, all_results_list)
    """
    accounts = get_target_accounts(strategy_name)
    if not accounts:
        print(cprint(f"⚠️ [MultiAccount] Tidak ada akun target aktif untuk {strategy_name}", Colors.YELLOW))
        return None, []

    print(cprint(f"⚡ [MultiAccount Dispatcher] Memulai eksekusi ke {len(accounts)} akun ({', '.join([a['key'] for a in accounts])})...", Colors.MAGENTA))

    results = []
    primary_acc = accounts[0]
    secondary_accounts = accounts[1:]

    # 1. Eksekusi akun primer (ACC1) langsung di thread utama
    try:
        primary_res_dict = _execute_local_account_order(primary_acc, strategy_name, payload)
        results.append(primary_res_dict)
    except Exception as exc:
        print(cprint(f"⚠️ Error eksekusi primer {primary_acc['key']}: {exc}", Colors.RED))
        results.append({"key": primary_acc['key'], "name": primary_acc['name'], "login": primary_acc['login'], "success": False, "error": str(exc), "retcode": -1, "order": None})

    # 2. Eksekusi akun sekunder (ACC2, ACC3) secara paralel via sub-process
    if secondary_accounts:
        with ProcessPoolExecutor(max_workers=len(secondary_accounts)) as executor:
            future_to_acc = {executor.submit(_worker_execute_account_order, acc, strategy_name, payload): acc for acc in secondary_accounts}
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

    # 3. Kirim WA Notification terpusat untuk SEMUA akun yang sukses
    wa_message = payload.get("wa_message")
    if wa_message:
        dest_jid = payload.get("target_jid", os.getenv("PRIVATE_JID", os.getenv("RCS_GROUP_JID", "120363409493021715@g.us")))
        for r in results:
            if r.get("success") and r.get("order"):
                footer_label = f"\n\n🏷️ *AKUN:* {r['key']} ({r.get('name', r['key'])} | {r.get('login', '-')}) | *BOT:* {strategy_name.upper()}"
                full_wa = wa_message.strip() + footer_label
                wa_payload = {
                    'source_table': f'{strategy_name.lower()}_system',
                    'event_type': f'{strategy_name.upper()}_MULTI_EXEC',
                    'group_jid': dest_jid,
                    'message_type': 'TEXT',
                    'message': full_wa,
                    'dedupe_key': f'{strategy_name.lower()}_{r["key"]}_{r["order"]}_{int(time.time())}_{uuid.uuid4().hex[:4]}'
                }
                try:
                    execute_supabase(lambda sb: sb.table('wa_outbox').insert(wa_payload).execute())
                    print(cprint(f"📲 [{r['key']}] WA Notif terkirim dengan Label Footer Akun.", Colors.GREEN))
                except Exception as e:
                    print(cprint(f"⚠️ [{r['key']}] Gagal kirim WA outbox: {e}", Colors.RED))

    # Temukan akun primer pertama yang berhasil untuk return ke caller
    primary_res = None
    for r in results:
        if r.get("key") == primary_acc["key"] and r.get("success") and r.get("order"):
            primary_res = MultiOrderResult(
                retcode=r.get("retcode", mt5.TRADE_RETCODE_DONE),
                order=r.get("order"),
                price=r.get("price", payload.get("price", 0.0)),
                volume=r.get("volume", 0.01),
                comment=r.get("comment", ""),
                all_results=results
            )
            break

    # Fallback jika ACC1 gagal tapi akun lain sukses
    if primary_res is None:
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

    primary_acc = accounts[0]
    secondary_accounts = accounts[1:]
    total_canceled = 0

    # 1. Cancel akun primer di thread utama
    orders1 = mt5.orders_get(symbol=symbol)
    if orders1:
        for ord_item in orders1:
            if not magic_numbers or ord_item.magic in magic_numbers:
                req = {"action": mt5.TRADE_ACTION_REMOVE, "order": ord_item.ticket}
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    total_canceled += 1

    # 2. Cancel akun sekunder via sub-process
    if secondary_accounts:
        with ProcessPoolExecutor(max_workers=len(secondary_accounts)) as executor:
            futures = [executor.submit(_worker_cancel_pending_orders, acc, symbol, magic_numbers or []) for acc in secondary_accounts]
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
    from datetime import datetime, timedelta

    path = acc_info.get("path", "")
    if path and os.path.exists(path):
        init_ok = mt5_worker.initialize(path=path, portable=True, timeout=15000)
    else:
        init_ok = mt5_worker.initialize(timeout=15000)

    if not init_ok:
        return {"key": acc_info['key'], "name": acc_info['name'], "login": acc_info['login'], "profit": 0.0, "deals_count": 0}

    now = datetime.now()
    from_time = now - timedelta(hours=24)
    deals = mt5_worker.history_deals_get(from_time, now)
    
    total_pnl = 0.0
    matched_deals = 0
    if deals:
        for d in deals:
            if not tickets or (d.position_id in tickets or d.order in tickets or d.ticket in tickets):
                total_pnl += (d.profit + d.swap + d.commission)
                matched_deals += 1

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

    primary_acc = accounts[0]
    secondary_accounts = accounts[1:]
    results_map = {}
    total_profit = 0.0

    # 1. Query ACC1 di thread utama
    now = datetime.now()
    from_time = now - timedelta(hours=24)
    deals1 = mt5.history_deals_get(from_time, now)
    p1_pnl = 0.0
    p1_tickets = tickets_per_account.get(primary_acc['key'], [])
    if deals1:
        for d in deals1:
            if not p1_tickets or (d.position_id in p1_tickets or d.order in p1_tickets or d.ticket in p1_tickets):
                p1_pnl += (d.profit + d.swap + d.commission)

    results_map[primary_acc['key']] = {
        "key": primary_acc['key'],
        "name": primary_acc['name'],
        "login": getattr(mt5.account_info(), "login", primary_acc['login']),
        "profit": round(p1_pnl, 2)
    }
    total_profit += p1_pnl

    # 2. Query akun sekunder via sub-process
    if secondary_accounts:
        with ProcessPoolExecutor(max_workers=len(secondary_accounts)) as executor:
            future_to_acc = {
                executor.submit(
                    _worker_query_account_deals_pnl, 
                    acc, 
                    symbol, 
                    tickets_per_account.get(acc['key'], [])
                ): acc for acc in secondary_accounts
            }
            for fut in as_completed(future_to_acc):
                acc = future_to_acc[fut]
                try:
                    res = fut.result()
                    results_map[acc['key']] = res
                    total_profit += res.get("profit", 0.0)
                except Exception:
                    results_map[acc['key']] = {"key": acc['key'], "name": acc['name'], "login": acc['login'], "profit": 0.0}

    return {
        "accounts": results_map,
        "total_profit": round(total_profit, 2)
    }
