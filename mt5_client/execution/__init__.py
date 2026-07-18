# =====================================================
# mt5_client/execution/__init__.py
# Re-export public API — supaya import path yang sudah ada
# di mt5_client/__init__.py dan test_op.py TIDAK PERLU diubah.
# =====================================================

from .executor import execute_engulfing_order
