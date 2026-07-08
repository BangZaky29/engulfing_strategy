# =====================================================
# config/execution_config.py
# Konfigurasi eksekusi MT5 (Lot, SL, TP, Slippage, dll)
# =====================================================

import math
import os
from dataclasses import dataclass, field


@dataclass
class ExecutionConfig:
    """Konfigurasi parameter trading/eksekusi."""

    # === SL/TP versi % tail (sesuai plan-perubahanOP.md) ===
    # sl_pct: posisi SL sebagai % relatif terhadap tail (ekor) dari candle trigger.
    # BUY  : 0% = close (dekat body) | 100% = tail low
    # SELL : 0% = close (dekat body) | 100% = tail high
    sl_pct: float = field(default_factory=lambda: float(os.getenv("EXECUTION_SL_PCT", "80.0")))

    # tp_pct: posisi TP sebagai % relatif terhadap jarak OP ke SL.
    # TP_distance = |entry - sl| * (tp_pct/100)
    tp_pct: float = field(default_factory=lambda: float(os.getenv("EXECUTION_TP_PCT", "100.0")))

    # Toggle untuk menonaktifkan Limit Order dan memaksa Market Execution
    use_limit_orders: bool = field(
        default_factory=lambda: os.getenv("EXECUTION_USE_LIMIT", "true").lower() == "true"
    )



    lot_size: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_LOT_SIZE", "0.01"))
    )


    def get_lot_size(self, symbol: str) -> float:
        """
        Ambil lot size dari .env spesifik ke simbol (misal LOT_XAUUSD=0.05).
        Jika tidak ada, fallback ke EXECUTION_LOT_SIZE default.
        """
        clean_sym = symbol.replace(" ", "_").replace("-", "_")
        
        # Check standard
        val = os.getenv(f"LOT_{clean_sym}")
        if val is None:
            # Fallback exact
            val = os.getenv(f"LOT_{symbol}")
            
        # Fallback aliases (e.g. BTC -> Bitcoin, NASDAQ-100 -> US_Tech_100)
        if val is None:
            if symbol == "BTC" or symbol == "BTCUSD":
                val = os.getenv("LOT_Bitcoin")
            elif symbol == "NASDAQ-100" or symbol == "US100" or symbol == "USTEC":
                val = os.getenv("LOT_US_Tech_100_index") or os.getenv("LOT_NASDAQ_100")
                
        if val is not None:
            try:
                return float(val)
            except ValueError:
                pass
        return self.lot_size

    slippage: int = field(
        default_factory=lambda: int(os.getenv("EXECUTION_SLIPPAGE", "20"))
    )
    magic_number: int = field(
        default_factory=lambda: int(os.getenv("EXECUTION_MAGIC_NUMBER", "777777"))
    )

    # === Filter B Specific ===
    op_pct_b: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_OP_PCT_B", "20"))
    )
    pending_order_expire_candles: int = field(
        default_factory=lambda: int(os.getenv("PENDING_ORDER_EXPIRE_CANDLES", "2"))
    )

    def calculate_sl_price(
        self,
        *,
        current_close: float,
        current_low: float,
        current_high: float,
        action_str: str,
    ) -> float:
        """Hitung SL berbasis ekor (tail) candle trigger menggunakan sl_pct.

        Sesuai test:
          BUY  : sl = low  + (close-low) * (1 - sl_pct/100)
                 Dengan sl_pct=100 -> sl=low
                      sl_pct=80  -> sl berada di antara close dan low (lebih dekat low)

          SELL : sl = high - (high-close) * (1 - sl_pct/100)
                 Dengan sl_pct=100 -> sl=high
        """
        action = str(action_str).upper().strip()
        sl_pct_ratio = float(self.sl_pct) / 100.0

        if action == "BUY":
            # 0% = close, 100% = low
            return current_close - (current_close - current_low) * sl_pct_ratio
        elif action == "SELL":
            # 0% = close, 100% = high
            return current_close + (current_high - current_close) * sl_pct_ratio

        else:
            raise ValueError(f"Unknown action_str for SL: {action_str}")

    def calculate_tp_price(
        self,
        *,
        entry_price: float,
        sl_price: float,
        action_str: str,
    ) -> float:
        """Hitung TP berbasis jarak entry ke SL menggunakan tp_pct.

        TP_distance = |entry - sl| * (tp_pct/100)
        BUY  : tp = entry + TP_distance
        SELL : tp = entry - TP_distance
        """
        action = str(action_str).upper().strip()
        tp_pct_ratio = float(self.tp_pct) / 100.0
        distance = abs(float(entry_price) - float(sl_price))
        tp_distance = distance * tp_pct_ratio

        if action == "BUY":
            return float(entry_price) + tp_distance
        elif action == "SELL":
            return float(entry_price) - tp_distance
        else:
            raise ValueError(f"Unknown action_str for TP: {action_str}")

