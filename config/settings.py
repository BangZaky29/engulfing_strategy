# =====================================================
# config/settings.py
# Load environment variables dari .env
# =====================================================

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env dari root project
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)


# === Supabase ===
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# === Polling ===
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "1"))

# === Strategy ===
ACTIVE_FILTER_STRATEGY: str = os.getenv("ACTIVE_FILTER_STRATEGY", "A").upper()


def validate_env():
    """Validasi bahwa semua required env vars sudah terisi."""
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("SUPABASE_SERVICE_KEY")
    
    if missing:
        raise EnvironmentError(
            f"❌ Environment variables berikut belum diset: {', '.join(missing)}\n"
            f"   Pastikan file .env ada di: {_env_path}"
        )
        
    if ACTIVE_FILTER_STRATEGY not in ["A", "B"]:
        raise EnvironmentError(
            f"❌ Konfigurasi ACTIVE_FILTER_STRATEGY salah! Hanya boleh 'A' atau 'B'.\n"
            f"   Nilai saat ini: {ACTIVE_FILTER_STRATEGY}"
        )
        
    return True
