import multiprocessing
from dotenv import load_dotenv
load_dotenv()

from strategies.recovery_marubozu.mrcv_main import run_mrcv_bot

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        run_mrcv_bot()
    except KeyboardInterrupt:
        print("\n👋 MRCV Bot dihentikan (KeyboardInterrupt). Bye!")

