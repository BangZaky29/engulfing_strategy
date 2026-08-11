import subprocess
import time
import sys
import os
from datetime import datetime

def run_watchdog():
    # Target script is inside indicatorInfo/triggerInfo
    script = os.path.join("indicatorInfo", "triggerInfo", "multi_scanner.py")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Memulai Watchdog untuk {script}")
    
    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Menjalankan MultiPatternScanner...")
            process = subprocess.Popen([sys.executable, script])
            process.wait()
            
            if process.returncode != 0:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Scanner crash dengan exit code {process.returncode}. Restart dalam 10 detik...")
                time.sleep(10)
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scanner berhenti secara normal. Watchdog dihentikan.")
                break
                
        except KeyboardInterrupt:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Watchdog Scanner dimatikan oleh user (Ctrl+C).")
            if 'process' in locals() and process.poll() is None:
                process.terminate()
            break
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ Watchdog Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_watchdog()
