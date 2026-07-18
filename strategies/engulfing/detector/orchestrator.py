# =====================================================
# strategies/engulfing/detector/orchestrator.py
# Orchestrator utama untuk mendeteksi engulfing pattern.
# Menggabungkan evaluasi Filter A/B dan integrasi Filter C.
# =====================================================

from config.engulfing_config import EngulfingConfig
from utils.colors import Colors, cprint, skip_msg, grade_color

from ..signal_builder import build_signal
from .filter_ab_eval import evaluate_filters_ab
from .filter_c_eval import apply_filter_c

def detect_engulfing(
    candle_data: dict,
    cfg: EngulfingConfig | None = None,
    verbose: bool = False,
    color: str = "",
) -> dict | None:
    """
    Fungsi utama untuk mendeteksi engulfing dan mengeksekusi urutan filter.
    Returns: signal dictionary atau None jika invalid.
    """
    if cfg is None:
        cfg = EngulfingConfig()

    symbol = candle_data.get("symbol", "XAUUSD")

    c1_is_bullish = candle_data["is_bullish"]
    c1_is_doji    = candle_data.get("is_doji", False)
    c2_is_bullish = candle_data["prev_is_bullish"]
    c2_is_doji    = candle_data.get("prev_is_doji", False)

    if c1_is_doji:
        warna_c1 = f"Putih [DOJI {'BUY' if c1_is_bullish else 'SELL'}]"
        clr_c1 = Colors.GRAY
    else:
        warna_c1 = "Hijau [BUY]" if c1_is_bullish else "Merah [SELL]"
        clr_c1 = Colors.GREEN if c1_is_bullish else Colors.RED

    if c2_is_doji:
        warna_c2 = f"Putih [DOJI {'BUY' if c2_is_bullish else 'SELL'}]"
        clr_c2 = Colors.GRAY
    else:
        warna_c2 = "Hijau [BUY]" if c2_is_bullish else "Merah [SELL]"
        clr_c2 = Colors.GREEN if c2_is_bullish else Colors.RED

    # --- Header verbose ---
    if verbose:
        print(cprint(f"   {'-'*52}", color))
        c1_label = cprint(warna_c1, clr_c1, bold=True)
        c2_label = cprint(warna_c2, clr_c2, bold=True)
        print(cprint("   [FILTER] ", color) + f"C1(Engulf)={c1_label}  C2(Ditela)={c2_label}")
        print(cprint(f"   {'-'*52}", color))

    # --- Evaluasi Filter A dan Filter B ---
    skip_reason, scoring_res, rr_ratio, pattern_type, valid_f3 = evaluate_filters_ab(
        candle_data, cfg, verbose, color
    )

    if skip_reason == "ABORT":
        return None

    # --- Build sinyal awal ---
    signal = build_signal(
        candle_data, pattern_type, scoring_res, rr_ratio, cfg
    )

    signal["skip_reasons"] = [skip_reason] if skip_reason else []
    if skip_reason:
        signal["is_confirmed"] = False
        signal["skip_reason"] = skip_reason
        if verbose:
            print(cprint(f"   {skip_msg(skip_reason)}", Colors.YELLOW))
        try:
            import json as _json
            notes_obj = _json.loads(signal.get("notes", "{}"))
            notes_obj["skip_reason"] = signal["skip_reason"]
            notes_obj["skip_reasons"] = signal["skip_reasons"]
            signal["notes"] = _json.dumps(notes_obj)
        except Exception:
            pass
    else:
        signal["is_confirmed"] = True
        signal["skip_reason"] = None

        # --- Terapkan Filter C ---
        apply_filter_c(signal, symbol, candle_data, pattern_type, cfg, verbose)

        # --- Cetak hasil sukses ---
        if verbose and signal.get("is_confirmed"):
            sl_pts = signal.get("sl_pts", 0)
            sl_price = signal.get("sl_price", 0.0)
            print(cprint(f"   {'-'*52}", color))
            session_str = signal.get("trading_session", "Unknown")
            print(cprint(f"   {pattern_type.upper()} LOLOS SEMUA FILTER! ✅", Colors.GREEN, bold=True))
            print(cprint(
                f"   Engulfing | {signal['symbol']} | {signal['timeframe']} | "
                f"{scoring_res['action_str']} | Grade : {grade_color(str(scoring_res['grade']))} | "
                f"B : {scoring_res['body_pct']}% | CP : {scoring_res['cp_pct']}% | "
                f"RR : {signal['rr_ratio']} | SL : {sl_price} ({sl_pts}pts) | Sesi : {session_str}",
                Colors.GREEN
            ))
            print(cprint(f"   {'-'*52}", color))

    return signal
