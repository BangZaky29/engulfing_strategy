# =====================================================
# database/signal_repo.py
# Repository: CRUD operasi untuk table 'engulfing_signals'
# =====================================================

from database.supabase_client import execute_supabase


class SignalRepo:
    """Repository untuk table engulfing_signals di Supabase."""

    TABLE = "engulfing_signals"

    @staticmethod
    def upsert(signal: dict) -> bool:
        """
        Insert/update sinyal engulfing.
        Upsert berdasarkan (symbol, timeframe, signal_time, pattern_type).
        """
        try:
            payload = {
                "symbol": signal["symbol"],
                "timeframe": signal["timeframe"],
                "signal_time": (
                    signal["signal_time"].isoformat()
                    if hasattr(signal["signal_time"], "isoformat")
                    else str(signal["signal_time"])
                ),
                "pattern_type": signal["pattern_type"],
                "prev_open": signal["prev_open"],
                "prev_close": signal["prev_close"],
                "prev_high": signal["prev_high"],
                "prev_low": signal["prev_low"],
                "curr_open": signal["curr_open"],
                "curr_close": signal["curr_close"],
                "curr_high": signal["curr_high"],
                "curr_low": signal["curr_low"],
                "engulf_ratio": signal.get("engulf_ratio"),
                "ema_fast_value": signal.get("ema_fast_value"),
                "ema_slow_value": signal.get("ema_slow_value"),
                "ema_trend": (signal.get("ema_trend")[:10] if signal.get("ema_trend") else None),
                "confidence_score": signal.get("confidence_score"),
                "is_confirmed": signal.get("is_confirmed", False),
                "ticket_id": signal.get("ticket_id"),
                "skip_reason": signal.get("skip_reason"),
                "notes": signal.get("notes", ""),
                "trading_session": signal.get("trading_session"),
            }

            execute_supabase(
                lambda sb: sb.table(SignalRepo.TABLE).upsert(
                    payload,
                    on_conflict="symbol,timeframe,signal_time,pattern_type",
                ).execute()
            )

            # Filter print log agar terminal bersih
            ticket_id_str = str(signal.get('ticket_id') or "")
            if not ticket_id_str:
                try:
                    import json
                    notes_obj = json.loads(signal.get('notes', '{}'))
                    ticket_id_str = str(notes_obj.get('ticket_id', ''))
                except:
                    pass
            
            if not ticket_id_str.startswith("INFO_") and not ticket_id_str.startswith("TFM_"):
                if signal.get('is_confirmed'):
                    emoji = "🚀"
                    status = f"EKSEKUSI ({signal.get('pattern_type')})"
                    notes = f" | Ticket: {signal.get('ticket_id')}"
                else:
                    emoji = "⏭️"
                    status = f"SKIPPED ({signal.get('pattern_type')})"
                    skip_reasons = signal.get('skip_reasons')
                    if isinstance(skip_reasons, list) and skip_reasons:
                        notes = f" | Alasan: {' | '.join(skip_reasons)}"
                    else:
                        notes = f" | Alasan: {signal.get('skip_reason')}"

                print(f"   {emoji} [Signal] {status} @ {signal['symbol']} {signal['timeframe']}{notes}")
            return True

        except Exception as e:
            print(f"❌ Error insert signal: {e}")
            return False

    @staticmethod
    def get_recent(symbol: str | None = None, limit: int = 20) -> list:
        """Ambil sinyal terbaru."""
        try:
            def _query(sb):
                query = (
                    sb.table(SignalRepo.TABLE)
                    .select("*")
                    .order("signal_time", desc=True)
                    .limit(limit)
                )
                if symbol:
                    query = query.eq("symbol", symbol)
                return query.execute()

            result = execute_supabase(_query)
            return result.data or []

        except Exception as e:
            print(f"❌ Error get signals: {e}")
            return []

    @staticmethod
    def get_by_confidence(min_confidence: float = 70, limit: int = 10) -> list:
        """Ambil sinyal dengan confidence tinggi."""
        try:
            result = execute_supabase(
                lambda sb: sb.table(SignalRepo.TABLE)
                .select("*")
                .gte("confidence_score", min_confidence)
                .order("confidence_score", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []

        except Exception as e:
            print(f"❌ Error get high confidence signals: {e}")
            return []

