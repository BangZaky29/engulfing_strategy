# =====================================================
# mt5_client/visualizer.py
# Generator Screenshot Chart gaya MT5 menggunakan mplfinance
# =====================================================

import os
import pandas as pd
import mplfinance as mpf
from config.mt5_config import EMAConfig


def generate_screenshot(rates,
                        ticket_id: int,
                        op_price: float,
                        sl_price: float,
                        tp_price: float,
                        ema_cfg: EMAConfig,
                        mode: str = "BUY",
                        entry_time: int = None,
                        entry_price: float = None,
                        exit_time: int = None,
                        exit_price: float = None,
                        tf_label: str = "M1",
                        output_dir: str = "temp_screenshots",
                        num_candles: int = 30) -> str | None:
    """
    Generate screenshot dari data rates MT5.
    Memplot garis OP (Biru), SL (Merah), dan TP (Hijau).
    """
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Convert ke DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        # Hitung EMA di seluruh data (agar akurat)
        df['ema_fast'] = df['close'].ewm(span=ema_cfg.fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=ema_cfg.slow, adjust=False).mean()

        # Shift EMA sesuai konfigurasi
        df['ema_fast'] = df['ema_fast'].shift(ema_cfg.offset)
        df['ema_slow'] = df['ema_slow'].shift(ema_cfg.offset)

        # Potong DataFrame hanya untuk N candle terakhir
        df_cropped = df.iloc[-num_candles:]

        # Buat Style MT5
        mc = mpf.make_marketcolors(up='lime', down='red',
                                   edge='inherit', wick='inherit', volume='in')
        # Gunakan base nightclouds (background hitam)
        s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds')

        # Siapkan Garis Horizontal (OP, SL, TP)
        hlines = dict(
            hlines=[op_price, sl_price, tp_price],
            colors=['deepskyblue', 'red', 'lime'],
            linestyle='-.',
            linewidths=1.2
        )

        # Siapkan Garis EMA (Hanya EMA 20 sesuai request user)
        ap = [
            mpf.make_addplot(df_cropped['ema_slow'], color='yellow', width=1.0)
        ]

        # Konfigurasi Tanda Panah (Arrow) HANYA untuk C2
        if entry_time:
            # Cari waktu open candle C3 (saat eksekusi)
            tf_seconds = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}.get(tf_label, 60)
            c3_candle_time = pd.to_datetime(entry_time - (entry_time % tf_seconds), unit='s')
            
            # C2 adalah candle persis sebelum C3
            c2_candle_time = c3_candle_time - pd.Timedelta(seconds=tf_seconds)
            
            c2_markers = [float('nan')] * len(df_cropped)
            
            # Cari index posisi C2
            for i, idx_time in enumerate(df_cropped.index):
                if idx_time == c2_candle_time:
                    if mode == "BUY":
                        # C2 Hijau (Bullish Engulfing). Panah putih ke ATAS di bawah candle C2.
                        y_pos = df_cropped.loc[idx_time, 'low']
                        margin = (df_cropped.loc[idx_time, 'high'] - df_cropped.loc[idx_time, 'low']) * 0.1
                        c2_markers[i] = y_pos - (margin if margin > 0 else 0.5)
                        ap.append(mpf.make_addplot(c2_markers, type='scatter', markersize=150, marker='^', color='white'))
                    else:
                        # C2 Merah (Bearish Engulfing). Panah putih ke BAWAH di atas candle C2.
                        y_pos = df_cropped.loc[idx_time, 'high']
                        margin = (df_cropped.loc[idx_time, 'high'] - df_cropped.loc[idx_time, 'low']) * 0.1
                        c2_markers[i] = y_pos + (margin if margin > 0 else 0.5)
                        ap.append(mpf.make_addplot(c2_markers, type='scatter', markersize=150, marker='v', color='white'))
        
        alines_conf = None
        if entry_time and exit_time and entry_price and exit_price:
            tf_seconds = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600}.get(tf_label, 60)
            entry_candle_time = pd.to_datetime(entry_time - (entry_time % tf_seconds), unit='s')
            exit_candle_time = pd.to_datetime(exit_time - (exit_time % tf_seconds), unit='s')
            
            if entry_candle_time in df_cropped.index and exit_candle_time in df_cropped.index:
                alines_conf = dict(alines=[[(entry_candle_time, entry_price), (exit_candle_time, exit_price)]],
                                   colors='dodgerblue' if mode == "BUY" else 'red',
                                   linestyle='--', linewidths=1.0)

        filename = os.path.join(output_dir, f"{ticket_id}.png")

        # Plot dan Save
        kwargs = dict(
            type='candle',
            style=s,
            hlines=hlines,
            addplot=ap,
            savefig=dict(fname=filename, dpi=150, bbox_inches='tight'),
            axisoff=True
        )
        if alines_conf:
            kwargs['alines'] = alines_conf

        mpf.plot(df_cropped, **kwargs)

        return filename

    except Exception as e:
        print(f"❌ Gagal generate screenshot: {e}")
        return None
