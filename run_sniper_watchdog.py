import os
import time
from dotenv import load_dotenv
from config.mt5_config import MT5Config
from mt5_client.connection import init_mt5
from mt5_client.position_tracker.tracker import PositionTracker
from strategies.sniperStrategy.sniper_core import SniperEngine
from utils.colors import cprint, Colors

def main():
    import sys, io
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    load_dotenv()
    print(cprint("🚀 Memulai Standalone Sniper Watchdog Engine...", Colors.CYAN))
    
    mt5_cfg = MT5Config()
    if not init_mt5(mt5_cfg, "SNIPER"):
        print(cprint("❌ Gagal terhubung ke MT5. Exiting...", Colors.RED))
        return

    symbols_str = os.getenv("SNIPER_SYMBOL", "XAUUSD")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]

    tracker = PositionTracker()

    engine = SniperEngine(symbols, tracker)

    import MetaTrader5 as mt5
    acc_info = mt5.account_info()
    acc_dict = {}
    if acc_info:
        acc_dict = {
            "name": acc_info.name,
            "server": acc_info.server,
            "balance": acc_info.balance,
            "equity": acc_info.equity,
            "margin": acc_info.margin
        }

    print(cprint("\n===============================================", Colors.CYAN))
    print(cprint(f"🎯 SNIPER ENGINE STARTUP REPORT", Colors.CYAN))
    print(cprint("===============================================", Colors.CYAN))
    print(f"Account : {acc_dict.get('name')} ({acc_dict.get('server')})")
    print(f"Balance : ${acc_dict.get('balance', 0):.2f}")
    print(f"Symbols : {', '.join(symbols)}")
    print(f"Timefrm : {engine.config.tf_primary} -> {engine.config.tf_confirm}")
    print(f"Op Pctg : Entry={engine.config.entry_percent}%, TP={engine.config.tp_percent}%")
    print(f"EMA FLT : M30={'ON' if engine.config.ema_filter_primary_enabled else 'OFF'}, M5={'ON' if engine.config.ema_filter_confirm_enabled else 'OFF'} (Period: {engine.config.ema_period}, MaxDist: {engine.config.ema_max_dist_pts} pts)")
    print(cprint("===============================================\n", Colors.CYAN))

    # Kirim notifikasi WA
    from indicatorInfo.sniperInfo.sniper_notifier import SniperNotifier
    notifier = SniperNotifier(engine.config)
    notifier.notify_startup(acc_dict, symbols)

    print(cprint(f"✅ Standalone Sniper Watchdog berjalan untuk symbol: {symbols}", Colors.GREEN))
    if not engine.config.strategy_enabled:
        print(cprint("⚠️ SNIPER_STRATEGY_ENABLED is false. Engine is sleeping.", Colors.YELLOW))

    try:
        while True:
            for symbol in symbols:
                engine.process_tick(symbol)
            time.sleep(2)
    except KeyboardInterrupt:
        print(cprint("\n🛑 Standalone Sniper Watchdog dihentikan oleh user.", Colors.YELLOW))
    except Exception as e:
        print(cprint(f"\n❌ Error fatal pada Standalone Sniper Watchdog: {e}", Colors.RED))
    finally:
        import MetaTrader5 as mt5
        mt5.shutdown()

if __name__ == "__main__":
    main()
