# =====================================================
# database/candle_repo.py
# Repository: CRUD operasi untuk table 'candles'
# =====================================================

from database.supabase_client import execute_supabase
from postgrest.types import CountMethod


class CandleRepo:
    """Repository untuk table candles di Supabase."""

    TABLE = "candles"

    @staticmethod
    def upsert(data: dict) -> bool:
        """
        Insert/update candle. Upsert berdasarkan (symbol, timeframe, timestamp).
        """
        try:
            payload = {
                "symbol": data["symbol"],
                "timeframe": data["timeframe"],
                "timestamp": (
                    data["timestamp"].isoformat()
                    if hasattr(data["timestamp"], "isoformat")
                    else str(data["timestamp"])
                ),
                "open_": data["open_"],
                "high_": data["high_"],
                "low_": data["low_"],
                "close_": data["close_"],
                "volume": data.get("volume", 0),
                "spread": data.get("spread", 0),
                "ema_fast": data.get("ema_fast"),
                "ema_slow": data.get("ema_slow"),
                "body_size": data.get("body_size"),
                "upper_wick": data.get("upper_wick"),
                "lower_wick": data.get("lower_wick"),
                "is_bullish": data.get("is_bullish"),
            }

            execute_supabase(
                lambda sb: sb.table(CandleRepo.TABLE).upsert(
                    payload, on_conflict="symbol,timeframe,timestamp"
                ).execute()
            )

            return True

        except Exception as e:
            print(f"❌ Error insert candle: {e}")
            return False

    @staticmethod
    def get_recent(symbol: str, timeframe: str, limit: int = 50) -> list:
        """Ambil candle terbaru dari Supabase."""
        try:
            result = execute_supabase(
                lambda sb: sb.table(CandleRepo.TABLE)
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .order("timestamp", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []

        except Exception as e:
            print(f"❌ Error get candles: {e}")
            return []

    @staticmethod
    def count(symbol: str, timeframe: str) -> int:
        """Hitung total candle tersimpan."""
        try:
            result = execute_supabase(
                lambda sb: sb.table(CandleRepo.TABLE)
                .select("id", count=CountMethod.exact)
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .execute()
            )
            return result.count or 0

        except Exception as e:
            print(f"❌ Error count candles: {e}")
            return 0

