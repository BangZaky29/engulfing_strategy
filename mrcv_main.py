# =====================================================
# mrcv_main.py - Entry point: Marubozu Recovery Machine
# =====================================================

from dotenv import load_dotenv
load_dotenv()

from strategies.recovery_marubozu.mrcv_engine import run_mrcv_bot

if __name__ == "__main__":
    run_mrcv_bot()
