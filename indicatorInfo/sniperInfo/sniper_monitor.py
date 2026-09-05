# =====================================================
# indicatorInfo/sniperInfo/sniper_monitor.py
# SniperMonitor — Core Engine Dual TF Engulfing Murni
# Berjalan di dalam loop MultiPatternScanner
# =====================================================

import os
import time

import MetaTrader5 as mt5

from config.sniper_config import SniperConfig
from indicatorInfo.sniperInfo.murni_detector import detect_engulfing_murni
from indicatorInfo.sniperInfo.sniper_state import (
    SniperState,
    SniperPhase,
    write_sniper_trigger,
    clear_sniper_trigger,
)
from indicatorInfo.sniperInfo.sniper_notifier import SniperNotifier
from utils.colors import cprint, Colors


# Mapping string TF ke konstanta MT5
TF_MAPPING = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


class SniperMonitor:
    """
    Monitor Engulfing Murni dual-timeframe (M30 → M5).

    Alur:
    1. IDLE: Poll M30 setiap ada candle baru → detect_engulfing_murni()
    2. WAITING_CONFIRM: M30 sudah trigger → poll M5 setiap candle baru
    3. Jika M5 engulfing murni SAME direction → CONFIRMED → tulis shared file
    4. Jika M30 candle baru tanpa M5 konfirmasi → EXPIRED → reset

    Dipanggil dari MultiPatternScanner.run_forever() setiap siklus scan.
    """

    def __init__(self):
        self.config = SniperConfig.from_env()
        self.notifier = SniperNotifier(self.config)

        # State per symbol
        self.states: dict[str, SniperState] = {
            sym: SniperState() for sym in self.config.symbols
        }

        # Pastikan symbol terpilih di Market Watch
        for sym in self.config.symbols:
            mt5.symbol_select(sym, True)

        print(cprint(
            f"🔫 [SNIPER] Monitor aktif | Symbols: {', '.join(self.config.symbols)} | "
            f"Primary: {self.config.tf_primary} → Confirm: {self.config.tf_confirm} | "
            f"Lot: {self.config.lot_size}",
            Colors.CYAN,
        ))

    def tick(self):
        """Dipanggil setiap siklus scanner loop (~5 detik)."""
        if not self.config.enabled:
            return

        for symbol in self.config.symbols:
            try:
                self._process_symbol(symbol)
            except Exception as e:
                print(cprint(f"⚠️ [SNIPER] Error pada {symbol}: {e}", Colors.RED))
                import traceback
                traceback.print_exc()

    def _process_symbol(self, symbol: str):
        """Proses satu symbol: poll primary TF, lalu confirm TF."""
        state = self.states[symbol]

        # ============================
        # 1. POLL PRIMARY TF (M30)
        # ============================
        primary_candle = self._get_candle_data(symbol, self.config.tf_primary)
        if primary_candle is None:
            return

        primary_ts = primary_candle["candle_ts"]

        # Deteksi pergantian candle primary
        primary_changed = (
            state.last_primary_candle_ts != 0
            and primary_ts != state.last_primary_candle_ts
        )
        state.last_primary_candle_ts = primary_ts

        # Jika M30 candle baru muncul saat WAITING_CONFIRM → M5 tidak konfirmasi → EXPIRED
        if primary_changed and state.phase == SniperPhase.WAITING_CONFIRM:
            print(cprint(
                f"⏰ [{symbol}] Sniper expired. {self.config.tf_confirm} tidak konfirmasi "
                f"sebelum {self.config.tf_primary} candle baru.",
                Colors.YELLOW,
            ))
            self.notifier.notify_expired(
                symbol, self.config.tf_primary, self.config.tf_confirm
            )
            clear_sniper_trigger()
            state.reset()

        # Saat IDLE + candle baru → cek engulfing murni primary
        if state.phase == SniperPhase.IDLE and primary_changed:
            direction = detect_engulfing_murni(primary_candle, source="scanner")
            if direction:
                # EMA Filter (Primary M30)
                if self.config.ema_filter_primary_enabled:
                    passed, reason = self._check_ema_filter(primary_candle, direction)
                    if not passed:
                        print(cprint(f"⏩ [{symbol}] {self.config.tf_primary} Engulfing {direction} diabaikan (EMA Filter): {reason}", Colors.YELLOW))
                        direction = None
                
                if direction:
                    state.set_primary_trigger(direction, primary_ts)
                    print(cprint(
                        f"🔫 [{symbol}] {self.config.tf_primary} Engulfing Murni {direction} "
                        f"terdeteksi — Menunggu {self.config.tf_confirm} konfirmasi...",
                        Colors.CYAN,
                    ))
                    self.notifier.notify_primary_trigger(
                        symbol, direction, self.config.tf_primary, self.config.tf_confirm
                    )

        # ============================
        # 2. POLL CONFIRM TF (M5)
        # ============================
        if state.phase != SniperPhase.WAITING_CONFIRM:
            return

        confirm_candle = self._get_candle_data(symbol, self.config.tf_confirm)
        if confirm_candle is None:
            return

        confirm_ts = confirm_candle["candle_ts"]

        # Deteksi pergantian candle confirm
        confirm_changed = (
            state.last_confirm_candle_ts != 0
            and confirm_ts != state.last_confirm_candle_ts
        )
        state.last_confirm_candle_ts = confirm_ts

        if not confirm_changed:
            return

        # Cek engulfing murni di confirm TF
        direction = detect_engulfing_murni(confirm_candle, source="scanner")
        if direction and direction == state.primary_direction:
            # EMA Filter (Confirm M5)
            if self.config.ema_filter_confirm_enabled:
                passed, reason = self._check_ema_filter(confirm_candle, direction)
                if not passed:
                    print(cprint(f"⏩ [{symbol}] {self.config.tf_confirm} Engulfing {direction} diabaikan (EMA Filter): {reason}", Colors.YELLOW))
                    direction = None
            
            if direction:
                # ✅ CONFIRMED! M30 + M5 sinkron engulfing murni
                state.set_confirmed(direction, confirm_ts)

            print(cprint(
                f"🎯 SNIPER | {symbol} {self.config.tf_primary}-{self.config.tf_confirm} "
                f"Engulfing Murni {direction} CONFIRMED!",
                Colors.GREEN,
            ))

            # Tulis shared trigger file untuk RCS
            write_sniper_trigger(
                symbol=symbol,
                direction=direction,
                tf_primary=self.config.tf_primary,
                tf_confirm=self.config.tf_confirm,
                primary_candle_ts=state.primary_candle_ts,
                confirm_candle_ts=confirm_ts,
                m5_open=confirm_candle["open_"],
                m5_high=confirm_candle["high_"],
                m5_low=confirm_candle["low_"],
                m5_close=confirm_candle["close_"],
            )

            # Kirim notifikasi WA
            self.notifier.notify_confirmed(
                symbol, direction, self.config.tf_primary, self.config.tf_confirm
            )

            # Reset state ke IDLE (siap siklus baru)
            state.reset()

    def _get_candle_data(self, symbol: str, tf_str: str) -> dict | None:
        """
        Ambil data candle yang sudah close dari MT5 dan hitung EMA jika perlu.
        Format output kompatibel dengan murni_detector (source='scanner').
        """
        tf_mt5 = TF_MAPPING.get(tf_str, mt5.TIMEFRAME_M5)

        is_ema_needed_here = (tf_str == self.config.tf_primary and self.config.ema_filter_primary_enabled) or \
                             (tf_str == self.config.tf_confirm and self.config.ema_filter_confirm_enabled)
        
        fetch_count = self.config.candle_count if is_ema_needed_here else 3
        rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 1, fetch_count)
        if rates is None or len(rates) < 2:
            return None

        # C1 = candle terakhir yang sudah close, C2 = sebelumnya
        c1 = rates[-1]
        c2 = rates[-2]
        
        # Hitung EMA
        ema_now = 0.0
        if is_ema_needed_here and len(rates) >= self.config.ema_period:
            import pandas as pd
            df = pd.DataFrame(rates)
            ema_series = df["close"].ewm(span=self.config.ema_period, adjust=False).mean()
            ema_now = float(ema_series.iloc[-1])

        c1_range = c1["high"] - c1["low"]
        body = abs(c1["close"] - c1["open"])
        body_pct = (body / c1_range * 100) if c1_range > 0 else 0
        
        info = mt5.symbol_info(symbol)
        point = info.point if info else 0.0001

        return {
            "close_": float(c1["close"]),
            "open_": float(c1["open"]),
            "high_": float(c1["high"]),
            "low_": float(c1["low"]),
            "c2_close": float(c2["close"]),
            "c2_open": float(c2["open"]),
            "c2_high": float(c2["high"]),
            "c2_low": float(c2["low"]),
            "body_pct": body_pct,
            "candle_ts": int(c1["time"]),
            "ema_now": ema_now,
            "point": point
        }

    def _check_ema_filter(self, candle: dict, direction: str) -> tuple[bool, str]:
        c1_open = candle["open_"]
        c1_close = candle["close_"]
        ema = candle["ema_now"]
        point = candle["point"]
        
        if ema == 0.0:
            return False, "EMA belum terhitung"
            
        dist_open_ema = int(round(abs(c1_open - ema) / point)) if point > 0 else 0
        
        # Opsi B: Body Only - Open & Close tidak boleh kena EMA.
        if direction == "BUY":
            # BUY: Trend Bullish -> Candle body harus murni di ATAS EMA
            if c1_open <= ema:
                return False, f"Open C1 ({c1_open}) menyentuh/berada di bawah EMA ({ema:.5f})"
            if c1_close <= ema:
                return False, f"Close C1 ({c1_close}) menyentuh/berada di bawah EMA ({ema:.5f})"
        else:
            # SELL: Trend Bearish -> Candle body harus murni di BAWAH EMA
            if c1_open >= ema:
                return False, f"Open C1 ({c1_open}) menyentuh/berada di atas EMA ({ema:.5f})"
            if c1_close >= ema:
                return False, f"Close C1 ({c1_close}) menyentuh/berada di atas EMA ({ema:.5f})"
                
        # Validasi Jarak EMA
        if dist_open_ema < self.config.ema_min_dist_pts:
            return False, f"Jarak Open-EMA ({dist_open_ema} pts) < min ({self.config.ema_min_dist_pts})"
        if dist_open_ema > self.config.ema_max_dist_pts:
            return False, f"Jarak Open-EMA ({dist_open_ema} pts) > max ({self.config.ema_max_dist_pts})"
            
        return True, "OK"
