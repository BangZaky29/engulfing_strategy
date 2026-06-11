# =====================================================
# database/stats_repo.py
# Repository: CRUD operasi untuk table 'engulfing_stats'
# =====================================================

from database.supabase_client import get_supabase


class StatsRepo:
    """Repository untuk table engulfing_stats di Supabase."""

    TABLE = "engulfing_stats"

    @staticmethod
    def update_daily(symbol: str, timeframe: str, date_str: str,
                     pattern_type: str, confidence: float) -> bool:
        """
        Update/insert statistik harian.
        Jika sudah ada record untuk hari itu → update counter.
        Jika belum → insert baru.
        """
        try:
            sb = get_supabase()

            # Cek existing record
            existing = (
                sb.table(StatsRepo.TABLE)
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .eq("date", date_str)
                .execute()
            )

            if existing.data and len(existing.data) > 0:
                row = existing.data[0]
                new_bullish = row["total_bullish"] + (1 if pattern_type == "bullish_engulfing" else 0)
                new_bearish = row["total_bearish"] + (1 if pattern_type == "bearish_engulfing" else 0)
                total = new_bullish + new_bearish
                new_avg = (
                    ((row["avg_confidence"] * (total - 1)) + confidence) / total
                    if total > 0
                    else confidence
                )
                new_highest = max(row["highest_confidence"], confidence)

                sb.table(StatsRepo.TABLE).update({
                    "total_bullish": new_bullish,
                    "total_bearish": new_bearish,
                    "avg_confidence": round(new_avg, 2),
                    "highest_confidence": round(new_highest, 2),
                    "updated_at": "now()",
                }).eq("id", row["id"]).execute()

            else:
                sb.table(StatsRepo.TABLE).insert({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "date": date_str,
                    "total_bullish": 1 if pattern_type == "bullish_engulfing" else 0,
                    "total_bearish": 1 if pattern_type == "bearish_engulfing" else 0,
                    "avg_confidence": round(confidence, 2),
                    "highest_confidence": round(confidence, 2),
                }).execute()

            print(f"📊 Stats diupdate: {symbol} {date_str}")
            return True

        except Exception as e:
            print(f"❌ Error update stats: {e}")
            return False

    @staticmethod
    def get_daily(symbol: str, timeframe: str, date_str: str) -> dict | None:
        """Ambil stats untuk tanggal tertentu."""
        try:
            sb = get_supabase()
            result = (
                sb.table(StatsRepo.TABLE)
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .eq("date", date_str)
                .single()
                .execute()
            )
            return result.data

        except Exception:
            return None

    @staticmethod
    def get_range(symbol: str, timeframe: str, 
                  from_date: str, to_date: str) -> list:
        """Ambil stats dalam rentang tanggal."""
        try:
            sb = get_supabase()
            result = (
                sb.table(StatsRepo.TABLE)
                .select("*")
                .eq("symbol", symbol)
                .eq("timeframe", timeframe)
                .gte("date", from_date)
                .lte("date", to_date)
                .order("date", desc=True)
                .execute()
            )
            return result.data or []

        except Exception as e:
            print(f"❌ Error get stats range: {e}")
            return []
