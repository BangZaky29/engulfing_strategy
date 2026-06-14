# =====================================================
# mt5_client/candle_fetcher.py
# Ambil data candle dari MT5
# =====================================================

import MetaTrader5 as mt5
import pandas as pd

from config.mt5_config import MT5Config, EMAConfig
from mt5_client.indicators import get_ema


def get_closed_candles(mt5_cfg: MT5Config = None,
                       ema_cfg: EMAConfig = None,
                       tf_label: str = "M1",
                       verbose: bool = False) -> dict | None:
    """
    Ambil 2 candle terakhir yang sudah close + EMA + analisa body.
    Return dict berisi data C1 (prev) dan C2 (current).
    """
    if mt5_cfg is None:
        mt5_cfg = MT5Config()
    if ema_cfg is None:
        ema_cfg = EMAConfig()

    # Ambil rates dari MT5
    rates = mt5.copy_rates_from_pos(mt5_cfg.symbol, mt5_cfg.get_mt5_timeframe(tf_label), 0, mt5_cfg.candle_count)
    tick = mt5.symbol_info_tick(mt5_cfg.symbol)
    info = mt5.symbol_info(mt5_cfg.symbol)

    if rates is None or len(rates) < 3 or tick is None or info is None:
        if verbose:
            print(f"❌ Gagal ambil data {mt5_cfg.symbol}. error={mt5.last_error()}")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    # C1 = candle sebelumnya, C2 = candle terakhir yg sudah close
    c1 = df.iloc[-3]
    c2 = df.iloc[-2]

    # Hitung EMA
    ema_fast = get_ema(df, span=ema_cfg.fast, offset=ema_cfg.offset)
    ema_slow = get_ema(df, span=ema_cfg.slow, offset=ema_cfg.offset)
    spread = round(tick.ask - tick.bid, info.digits)

    # Body & wick C2 (Engulfing Candle / C1 in new rules)
    body_c2 = abs(c2["close"] - c2["open"])
    upper_wick_c2 = c2["high"] - max(c2["open"], c2["close"])
    lower_wick_c2 = min(c2["open"], c2["close"]) - c2["low"]
    is_bullish_c2 = c2["close"] > c2["open"]

    # Body C1 (Engulfed Candle / C2 in new rules)
    body_c1 = abs(c1["close"] - c1["open"])
    is_bullish_c1 = c1["close"] > c1["open"]

    import os
    # --- Market State (20 Candles Lookback) ---
    lookback_period = int(os.getenv("MARKET_LOOKBACK", "20"))
    # Cek apakah df cukup panjang
    if len(df) >= lookback_period + 3:
        # iloc[-2] adalah candle terakhir yg close
        lookback_df = df.iloc[-(lookback_period + 2):-2]
        
        # Average Range
        avg_range_20 = (lookback_df["high"] - lookback_df["low"]).mean()
        
        # EMA series untuk seluruh df (span=20 default)
        ema_series = df["close"].ewm(span=20, adjust=False).mean()
        
        # EMA slope point = abs(EMA now - EMA 20 ago)
        ema_now = ema_series.iloc[-2]
        ema_20_ago = ema_series.iloc[-(lookback_period + 2)]
        
        # Cross Count
        # cross terjadi jika body candle memotong EMA: (Open < EMA && Close > EMA) || (Open > EMA && Close < EMA)
        closes = lookback_df["close"].values
        opens = lookback_df["open"].values
        emas = ema_series.iloc[-(lookback_period + 2):-2].values
        
        cross_count = 0
        for i in range(len(closes)):
            if (opens[i] < emas[i] and closes[i] > emas[i]) or \
               (opens[i] > emas[i] and closes[i] < emas[i]):
                cross_count += 1
                
        # Side Strength
        closes_above = sum(closes > emas)
        closes_below = sum(closes < emas)
        side_strength = abs(closes_above - closes_below) / lookback_period
        
    else:
        avg_range_20 = 0.0
        ema_now = 0.0
        ema_20_ago = 0.0
        cross_count = 0
        side_strength = 0.0

    if verbose:
        warna = "🟩 Hijau" if is_bullish_c2 else "🟥 Merah"
        print(
            f"✅ {mt5_cfg.symbol} {tf_label} | C1(New): {c2['time']} {warna} "
            f"O:{c2['open']:.2f} H:{c2['high']:.2f} L:{c2['low']:.2f} C:{c2['close']:.2f} "
            f"| Spread: {spread}"
        )
        print(f"   📈 {ema_cfg.labels['fast']}: {ema_fast:.2f} | {ema_cfg.labels['slow']}: {ema_slow:.2f}")

    return {
        # Identifikasi
        "symbol": mt5_cfg.symbol,
        "timeframe": tf_label,

        # Info MT5 (untuk konversi point)
        "point": float(info.point),    # ukuran 1 MT5 point  (XAUUSD = 0.01)
        "digits": int(info.digits),    # jumlah desimal harga (XAUUSD = 2)

        # C2 (candle terakhir yg close)
        "timestamp": c2["time"],
        "open_": float(c2["open"]),
        "high_": float(c2["high"]),
        "low_": float(c2["low"]),
        "close_": float(c2["close"]),
        "volume": float(c2["tick_volume"]),
        "spread": spread,
        "body_size": float(body_c2),
        "upper_wick": float(upper_wick_c2),
        "lower_wick": float(lower_wick_c2),
        "is_bullish": bool(is_bullish_c2),

        # C1 (candle sebelumnya)
        "prev_timestamp": c1["time"],
        "prev_open": float(c1["open"]),
        "prev_high": float(c1["high"]),
        "prev_low": float(c1["low"]),
        "prev_close": float(c1["close"]),
        "prev_body_size": float(body_c1),
        "prev_is_bullish": bool(is_bullish_c1),

        # Indikator
        "ema_fast": float(ema_fast),
        "ema_slow": float(ema_slow),
        
        # Market State (20 Lookback)
        "avg_range_20": float(avg_range_20),
        "ema_now": float(ema_now),
        "ema_20_ago": float(ema_20_ago),
        "cross_count_20": int(cross_count),
        "side_strength_20": float(side_strength),
    }
