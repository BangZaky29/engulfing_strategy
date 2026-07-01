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

    # === Fixed Target Profit ===
    target_profit_usd: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_TARGET_PROFIT_USD", "8.0"))
    )

    # === Fixed USD Risk/Reward ===
    use_fixed_money: bool = field(
        default_factory=lambda: os.getenv("EXECUTION_USE_FIXED_MONEY", "true").lower() == "true"
    )
    fixed_money_usd: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_FIXED_MONEY_USD", "10.0"))
    )

    # === SL — Metode Ring % ===
    sl_ring_pct: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_SL_RING_PCT", "80"))
    )
    """
    Posisi SL sebagai % dari ring C2, dihitung MENJAUH dari Close.

    Konsep Ring:
      Candle Hijau (Bullish/BUY)  : 0% = Close | 100% = Low
        ring_range  = Close - Low
        sl_distance = ring_range * (sl_ring_pct / 100)
        sl_price    = Close - sl_distance

      Candle Merah (Bearish/SELL) : 0% = Close | 100% = High
        ring_range  = High - Close
        sl_distance = ring_range * (sl_ring_pct / 100)
        sl_price    = Close + sl_distance

    Contoh sl_ring_pct=80, Close=3300, Low=3290 (ring=10):
      sl_distance = 10 * 0.80 = 8
      sl_price    = 3300 - 8  = 3292  ← 80% menjauh dari Close, dekat Low
    """

    # === TP — Rasio Risk:Reward dari Entry ===
    tp_rr_ratio: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_TP_RR_RATIO", "1.0"))
    )
    """
    Rasio TP terhadap jarak Entry → SL (Risk:Reward).

      sl_from_entry = |entry_price - sl_price|
      tp_distance   = sl_from_entry * tp_rr_ratio

    Contoh tp_rr_ratio=1.0 (1:1):
      entry=3300.50, sl=3292.00 → sl_from_entry=8.50
      tp_price = 3300.50 + 8.50 = 3309.00

    Contoh tp_rr_ratio=1.5 (1:1.5):
      tp_price = 3300.50 + (8.50 * 1.5) = 3313.25
    """

    # === Filter B Specific ===
    op_pct_b: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_OP_PCT_B", "20"))
    )
    sl_pct_b: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_SL_PCT_B", "70"))
    )
    tp_pct_b: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_TP_PCT_B", "100"))
    )
    min_profit_usd: float = field(
        default_factory=lambda: float(os.getenv("EXECUTION_MIN_PROFIT_USD", "7.0"))
    )
    pending_order_expire_candles: int = field(
        default_factory=lambda: int(os.getenv("PENDING_ORDER_EXPIRE_CANDLES", "2"))
    )
