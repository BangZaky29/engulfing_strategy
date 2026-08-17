# =====================================================
# mt5_client/terminal_launcher.py
# Deteksi & Peluncur Otomatis Aplikasi Terminal MT5 Windows
# =====================================================

import os
import subprocess
import time
from utils.colors import cprint, Colors

def get_running_mt5_executable_paths() -> list[str]:
    """Mengambil daftar seluruh path terminal64.exe yang sedang aktif berjalan di Windows."""
    running_paths = []
    try:
        cmd = 'wmic process where "name like \'terminal%.exe\'" get ExecutablePath /format:csv'
        output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in output.splitlines():
            line = line.strip()
            if line and "Node,ExecutablePath" not in line and line.lower().endswith(".exe"):
                parts = line.split(",")
                if len(parts) >= 2:
                    p = parts[1].strip()
                    if p:
                        running_paths.append(os.path.normpath(p).lower())
    except Exception:
        # Fallback via tasklist
        try:
            cmd = 'tasklist /FI "IMAGENAME eq terminal64.exe" /NH'
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            if "terminal64.exe" in out.lower():
                running_paths.append("generic_terminal64_running")
        except Exception:
            pass

    return running_paths

def is_terminal_running(terminal_path: str, running_paths: list[str]) -> bool:
    """Mengecek apakah executable terminal MT5 tertentu sedang berjalan."""
    if not terminal_path or not os.path.exists(terminal_path):
        return False

    norm_target = os.path.normpath(terminal_path).lower()
    if norm_target in running_paths:
        return True

    return False

def ensure_all_target_terminals_running(accounts: list[dict]):
    """
    Mendeteksi apakah aplikasi GUI MT5 untuk masing-masing akun target sudah terbuka di Windows.
    Jika belum terbuka, buka secara otomatis.
    """
    if not accounts:
        return

    running_paths = get_running_mt5_executable_paths()
    newly_launched = False

    for acc in accounts:
        path = acc.get("path", "")
        if not path or not os.path.exists(path):
            continue

        if not is_terminal_running(path, running_paths):
            print(cprint(f"🚀 [AUTO-LAUNCHER] Membuka jendela MT5 untuk {acc['name']} ({acc['key']})...", Colors.YELLOW))
            try:
                # Buka executable MT5
                subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                newly_launched = True
            except Exception as e:
                print(cprint(f"❌ Gagal meluncurkan {path}: {e}", Colors.RED))
        else:
            print(cprint(f"✅ [AUTO-LAUNCHER] Terminal {acc['name']} ({acc['key']}) sudah aktif di Windows.", Colors.GREEN))

    # Jika ada terminal yang baru dibuka, beri jeda agar aplikasi loading sempurna
    if newly_launched:
        print(cprint("⏳ Menunggu 4 detik agar jendela MT5 yang baru dibuka selesai inisialisasi...", Colors.CYAN))
        time.sleep(4)
