# =====================================================
# mt5_client/indicators.py
# Technical indicators: EMA, dll
# =====================================================

import pandas as pd


def get_ema(df: pd.DataFrame, span: int, offset: int = -2) -> float:
    """
    Hitung EMA dari kolom 'close'.

    Args:
        df: DataFrame berisi kolom 'close'
        span: Period EMA (e.g. 10, 20)
        offset: Index candle (default -2 = candle terakhir yg close)

    Returns:
        Nilai EMA (float)
    """
    if "close" not in df.columns:
        raise ValueError("DataFrame harus memiliki kolom 'close'")

    ema_series = df["close"].ewm(span=span, adjust=False).mean()
    return float(ema_series.iloc[offset])
