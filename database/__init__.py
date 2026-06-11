# =====================================================
# database/__init__.py
# Database package - akses semua repo dari sini
# =====================================================

from database.supabase_client import get_supabase
from database.candle_repo import CandleRepo
from database.signal_repo import SignalRepo
from database.stats_repo import StatsRepo
