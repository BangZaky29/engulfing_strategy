import os
import time
from dotenv import load_dotenv
from config.mt5_config import MT5Config
from mt5_client.connection import init_mt5_connection
from strategies.strategy_rcs.position_tracker import PositionTracker
from strategies.sniperStrategy.sniper_core import SniperEngine
from utils.colors import cprint, Colors

def main():
    load_dotenv()
    print(cprint("🚀 Memulai Standalone Sniper Watchdog Engine...", Colors.CYAN))
    
    mt5_cfg = MT5Config()
    if not init_mt5_connection(mt5_cfg.terminal_path):
        print(cprint("❌ Gagal terhubung ke MT5. Exiting...", Colors.RED))
        return

    symbols_str = os.getenv("SNIPER_SYMBOL", "XAUUSD")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]

    tracker = PositionTracker(symbols)
    tracker.sync_all_positions()

    engine = SniperEngine(symbols, tracker)

    print(cprint(f"✅ Standalone Sniper Watchdog berjalan untuk symbol: {symbols}", Colors.GREEN))
    if not engine.config.strategy_enabled:
        print(cprint("⚠️ SNIPER_STRATEGY_ENABLED is false. Engine is sleeping.", Colors.YELLOW))

    try:
        while True:
            tracker.sync_all_positions()
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
