import subprocess
import time
import sys
from datetime import datetime

def run_watchdog():
    script = "rcs_main.py"
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Memulai Watchdog untuk {script}")
    
    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Menjalankan bot...")
            process = subprocess.Popen([sys.executable, script])
            process.wait()
            
            # Jika bot berhenti, kita cek return code-nya
            if process.returncode != 0:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Bot crash dengan exit code {process.returncode}. Restart dalam 10 detik...")
                time.sleep(10)
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bot berhenti secara normal (Graceful Exit). Watchdog dihentikan.")
                break
                
        except KeyboardInterrupt:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Watchdog dimatikan oleh user (Ctrl+C).")
            if 'process' in locals() and process.poll() is None:
                process.terminate()
            break
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ Watchdog Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_watchdog()
