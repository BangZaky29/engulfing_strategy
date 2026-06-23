# =====================================================
# config/mt5_config.py
# Konfigurasi MT5: symbol, timeframe, EMA
# =====================================================

import os
from dataclasses import dataclass, field


@dataclass
class MT5Config:
    """Konfigurasi koneksi dan data MT5."""
    symbols: list = field(default_factory=lambda: [x.strip() for x in os.getenv("MT5_SYMBOLS", "XAUUSD").split(",")])
    timeframes: list = field(default_factory=lambda: [x.strip() for x in os.getenv("MT5_TIMEFRAMES", "M1,M5").split(",")])
    strategy_timeframe: str = field(default_factory=lambda: os.getenv("STRATEGY_TIMEFRAME", "M1"))
    candle_count: int = field(default_factory=lambda: int(os.getenv("MT5_CANDLE_COUNT", "50")))
    
    # Doji Threshold Configuration
    doji_body_percent: float = field(default_factory=lambda: float(os.getenv("DOJI_BODY_PERCENT", "10")))

    # Mapping label → konstanta MT5 (di-resolve saat runtime)
    _TF_MAP = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 16385, "H4": 16388, "D1": 16408,
        "W1": 32769, "MN1": 49153,
    }

    def get_mt5_timeframe(self, label: str) -> int:
        """Konversi label timeframe ke konstanta MT5."""
        return self._TF_MAP.get(label, 1)  # Default M1

    def get_symbol_timeframe(self, symbol: str) -> str:
        """Mendapatkan timeframe spesifik untuk symbol tertentu dari .env (contoh: TF_BTCUSD)."""
        env_key = f"TF_{symbol.upper()}"
        return os.getenv(env_key, self.strategy_timeframe)

    def get_doji_abs_points(self, symbol: str) -> int:
        """Mendapatkan batas maksimal body dalam points untuk dianggap sebagai Doji per symbol."""
        defaults = {
            "XAUUSD": 10,
            "GBPUSD": 5,
            "BTCUSD": 100,
            "NASDAQ-100": 50
        }
        default_val = defaults.get(symbol.upper(), 10)
        return int(os.getenv(f"DOJI_ABS_POINTS_{symbol.upper()}", str(default_val)))

@dataclass
class EMAConfig:
    """Konfigurasi Exponential Moving Average."""
    fast: int = field(default_factory=lambda: int(os.getenv("EMA_FAST", "10")))
    slow: int = field(default_factory=lambda: int(os.getenv("EMA_SLOW", "20")))
    offset: int = field(default_factory=lambda: int(os.getenv("EMA_OFFSET", "-2")))

    @property
    def labels(self) -> dict:
        return {
            "fast": f"EMA_{self.fast}",
            "slow": f"EMA_{self.slow}",
        }
