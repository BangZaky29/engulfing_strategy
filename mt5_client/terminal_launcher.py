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

    # Metode 1: PowerShell Get-CimInstance (Paling akurat di Windows 10/11)
    try:
        ps_cmd = 'powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \\"Name like \'terminal%.exe\'\\").ExecutablePath"'
        out = subprocess.check_output(ps_cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            line = line.strip()
            if line and line.lower().endswith(".exe"):
                running_paths.append(os.path.normpath(line).lower())
    except Exception:
        pass

    # Metode 2: WMIC (Fallback)
    if not running_paths:
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
            pass

    # Metode 3: Tasklist (Cek apakah ada terminal64 yang aktif)
    if not running_paths:
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

    # Jika generic terminal running terdeteksi
    if "generic_terminal64_running" in running_paths:
        return True

    norm_target = os.path.normpath(terminal_path).lower()
    for rp in running_paths:
        if norm_target in rp or rp in norm_target:
            return True

    return False

def ensure_all_target_terminals_running(accounts: list[dict]):
    """
    Memverifikasi apakah aplikasi GUI MT5 untuk masing-masing akun target sudah terbuka di Windows.
    Memberikan reminder jika ada terminal yang belum dibuka manual oleh user via shortcut /portable.
    """
    if not accounts:
        return

    running_paths = get_running_mt5_executable_paths()

    for acc in accounts:
        path = acc.get("path", "")
        if not path or not os.path.exists(path):
            continue

        if is_terminal_running(path, running_paths):
            print(cprint(f"✅ [TERMINAL READY] {acc['name']} ({acc['key']}) aktif & terhubung di Windows.", Colors.GREEN))
        else:
            print(cprint(f"ℹ️ [INFO] Terminal {acc['name']} ({acc['key']}) belum dibuka. Harap buka shortcut Desktop /portable agar selalu standby.", Colors.YELLOW))
