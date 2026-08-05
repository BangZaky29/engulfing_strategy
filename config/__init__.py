# =====================================================
# config/__init__.py
# Central config loader - semua setting diakses dari sini
# =====================================================

from config.settings import *
from config.mt5_config import MT5Config, EMAConfig
from config.engulfing_config import EngulfingConfig
from config.execution_config import ExecutionConfig
from config.filter_c_config import FilterCConfig
from config.rcs_config import RCSConfig
from config.company_daily_guard import (
    check_company_daily_target,
    get_company_guard_status_text,
    should_send_company_notif,
    get_company_today_pnl_breakdown,
)
