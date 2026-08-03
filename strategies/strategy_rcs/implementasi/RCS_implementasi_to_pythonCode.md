# RCS (Reversal Candle System) — Implementation Plan

## Ringkasan

Blueprint RCS adalah sistem trading EA lengkap dengan **State Machine 3-phase** (IDLE → OP1 → FREEZE), deteksi **trigger candle** (Engulfing/ICT), eksekusi **multi-OP** (OP1/OP2/OP3), dan mekanisme **Hedge + Recovery**. Sistem ini akan diimplementasikan sebagai **mesin independen** (seperti `itr_main.py`) dengan struktur modular OOP.

## Analisa Blueprint

### State Machine (3 Phase)
| Phase | Deskripsi |
|-------|-----------|
| `PHASE_IDLE` | Menunggu candle baru yang lolos semua filter trigger |
| `PHASE_OP1` | OP1 sudah terbuka, memantau TP / OP2 / OP3 / SL |
| `PHASE_FREEZE` | Hedge terkunci (net exposure ~0) atau manual OP terdeteksi, menunggu semua posisi ditutup |

### Trigger Detection (1x per candle baru)
1. **Pola Candle**: Engulfing (C1 menelan full range C2) dan/atau ICT (liquidity sweep + rejection)
2. **Filter Wajib**: Range risiko, Body%, Spread, EMA Pullback
3. **Hasil**: Skip (dengan alasan) atau Valid → hitung level OP1/OP2/OP3

### Eksekusi Multi-OP
- **OP1**: Mode INSTANT_ZERO (market langsung) atau PERCENT (tunggu harga sentuh level)
- **OP2 Mode**: HEDGE / SL / HEDGE_REENTRY (3-OP system)
- **OP3**: Khusus mode HEDGE_REENTRY → HEDGE atau SL

### Freeze ↔ Unfreeze & Recovery
- Snapshot floating saat hedge terkunci
- Hitung "Hasil Recovery" setelah semua posisi ditutup

---

## Arsitektur Yang Akan Dibuat

### Prinsip Desain
- **Mesin terpisah**: `rcs_main.py` di root (seperti `itr_main.py`)
- **Tidak menyentuh modul shared**: `mt5_client/`, `database/`, `config/settings.py` tetap utuh
- **Modular OOP**: setiap concern di file terpisah
- **Konfigurasi via `.env`**: semua parameter RCS bisa diubah tanpa edit kode

### Folder Structure

```
engulfing/
├── rcs_main.py                              ← [NEW] Entry point RCS
├── .env                                     ← [MODIFY] Tambah section RCS
├── config/
│   ├── __init__.py                          ← [MODIFY] Export RCSConfig
│   └── rcs_config.py                        ← [NEW] Dataclass semua input RCS dari .env
└── strategies/
    └── strategy_rcs/
        ├── __init__.py                      ← [NEW] Package init
        ├── RCS_EA_MT5_Blueprint.md          ← [EXISTING] Blueprint referensi
        │
        ├── rcs_engine.py                    ← [NEW] Main loop + State Machine (run_rcs_bot)
        ├── rcs_state.py                     ← [NEW] RCSState dataclass (phase, level, tickets, snapshot)
        │
        ├── trigger/                         ← [NEW] Sub-package deteksi pola candle
        │   ├── __init__.py
        │   ├── engulfing_detector.py        ← [NEW] Deteksi pola Engulfing (C1 menelan C2)
        │   ├── ict_detector.py              ← [NEW] Deteksi pola ICT (liquidity sweep + rejection)
        │   ├── trigger_filter.py            ← [NEW] Semua filter (Range, Body%, Spread, EMA Pullback)
        │   └── level_calculator.py          ← [NEW] Hitung level OP1/OP2/OP3 dari Close C1
        │
        ├── engine/                          ← [NEW] Sub-package eksekusi & monitoring OP
        │   ├── __init__.py
        │   ├── op1_executor.py              ← [NEW] Entry OP1 (Instant-Zero & Percent mode)
        │   ├── op2_handler.py               ← [NEW] Logika OP2 (HEDGE / SL / HEDGE_REENTRY)
        │   ├── op3_handler.py               ← [NEW] Logika OP3 (khusus HEDGE_REENTRY)
        │   ├── tp_checker.py                ← [NEW] Cek TP kena (persen jarak / USD)
        │   └── sl_checker.py                ← [NEW] Cek SL (real broker / software fallback)
        │
        ├── freeze/                          ← [NEW] Sub-package Freeze & Recovery
        │   ├── __init__.py
        │   ├── freeze_manager.py            ← [NEW] Transisi ke Freeze, snapshot floating
        │   └── recovery_calculator.py       ← [NEW] Hitung Hasil Recovery setelah unfreeze
        │
        ├── rcs_order_manager.py             ← [NEW] Helper MT5 order khusus RCS (market/limit/close)
        │
        └── rcs_notifier.py                  ← [NEW] Notifikasi WA & console log per event
```

---

## Proposed Changes (Per Component)

---

### Component 1: Entry Point & Config

#### [NEW] [rcs_main.py](file:///c:/codingVibes/mt5/engulfing/rcs_main.py)
Entry point seperti `itr_main.py`. Import dan jalankan `run_rcs_bot()`.

#### [NEW] [rcs_config.py](file:///c:/codingVibes/mt5/engulfing/config/rcs_config.py)
Dataclass `RCSConfig` yang membaca semua parameter RCS dari `.env`:

| Grup | Variable .env | Default | Deskripsi |
|------|---------------|---------|-----------|
| **Core** | `RCS_ENABLED` | `false` | Toggle on/off |
| | `RCS_SYMBOL` | `XAUUSD` | Symbol target |
| | `RCS_SIGNAL_TIMEFRAME` | `M5` | TF untuk deteksi candle |
| | `RCS_CANDLE_COUNT` | `50` | Jumlah candle yang diambil |
| **Trigger Pattern** | `RCS_USE_ENGULFING` | `true` | Aktifkan deteksi Engulfing |
| | `RCS_USE_ICT` | `true` | Aktifkan deteksi ICT |
| | `RCS_ICT_SWEEP_LOOKBACK` | `5` | Lookback bars untuk ICT sweep |
| **Filter: Range** | `RCS_MIN_TRIGGER_RANGE` | `50` | Min range risiko (points) |
| | `RCS_MAX_TRIGGER_RANGE` | `500` | Max range risiko (points) |
| **Filter: Body** | `RCS_MIN_BODY_PERCENT` | `30` | Min body % candle |
| | `RCS_MAX_BODY_PERCENT` | `90` | Max body % candle |
| **Filter: Spread** | `RCS_USE_SPREAD_FILTER` | `true` | Toggle filter spread |
| | `RCS_MAX_SPREAD_POINTS` | `50` | Max spread (points) |
| **Filter: EMA Pullback** | `RCS_USE_EMA_PULLBACK` | `true` | Toggle EMA pullback filter |
| | `RCS_EMA_PERIOD` | `20` | Periode EMA |
| | `RCS_MAX_EMA_DISTANCE_PTS` | `200` | Max jarak Open ke EMA (points) |
| | `RCS_USE_EMA_SLOPE` | `false` | Toggle filter slope EMA |
| **OP1 Entry** | `RCS_OP1_ENTRY_MODE` | `PERCENT` | `INSTANT_ZERO` / `PERCENT` |
| | `RCS_ENTRY_PERCENT` | `20` | % dari riskRange untuk level OP1 |
| | `RCS_MAX_INSTANT_SLIP_PTS` | `30` | Slip filter mode Instant-Zero |
| | `RCS_MAX_TARGET_SLIP_PTS` | `20` | Slip filter mode Percent |
| | `RCS_ENTRY_TOLERANCE_PTS` | `5` | Toleransi sentuh level OP1 |
| | `RCS_LOT_SIZE_OP1` | `0.01` | Lot OP1 |
| | `RCS_MAGIC_OP1` | `901001` | Magic number OP1 |
| **TP1** | `RCS_TP_MODE` | `PERCENT` | `PERCENT` / `USD` |
| | `RCS_TP_PERCENT` | `100` | TP sebagai % jarak OP1→OP2 |
| | `RCS_TP_USD` | `500` | Target profit USD (mode USD) |
| **OP2** | `RCS_OP2_MODE` | `HEDGE` | `HEDGE` / `SL` / `HEDGE_REENTRY` |
| | `RCS_OP2_PERCENT` | `100` | % dari riskRange untuk level OP2 |
| | `RCS_LOT_SIZE_OP2` | `0.01` | Lot OP2 |
| | `RCS_MAGIC_OP2` | `901002` | Magic number OP2 |
| | `RCS_SL_COOLDOWN_CANDLES` | `3` | Cooldown setelah SL kena |
| **TP2 (HEDGE_REENTRY)** | `RCS_TP2_MODE` | `PERCENT` | `PERCENT` / `USD` |
| | `RCS_TP2_PERCENT` | `100` | TP2 sebagai % jarak OP1→OP2 |
| | `RCS_TP2_USD` | `500` | Target profit USD TP2 |
| **OP3 (HEDGE_REENTRY)** | `RCS_OP3_MODE` | `HEDGE` | `HEDGE` / `SL` |
| | `RCS_OP3_PERCENT` | `150` | % dari riskRange untuk level OP3 |
| | `RCS_MAGIC_OP3` | `901003` | Magic number OP3 |
| | `RCS_OP3_COOLDOWN_CANDLES` | `5` | Cooldown setelah OP3 SL |
| **Trigger Management** | `RCS_TRIGGER_MODE` | `NORMAL` | Mode manajemen trigger |
| | `RCS_MAX_TRIGGER_AGE` | `3` | Max umur trigger (candles) |
| **Slippage** | `RCS_SLIPPAGE` | `20` | Slippage ke broker (points) |
| **Notifikasi** | `RCS_NOTIF_TRIGGER` | `true` | Notif saat trigger valid |
| | `RCS_NOTIF_SKIP` | `true` | Notif saat trigger skip |
| | `RCS_NOTIF_OPEN` | `true` | Notif saat OP dibuka |
| | `RCS_NOTIF_RESULT` | `true` | Notif hasil trade |
| | `RCS_NOTIF_FREEZE` | `true` | Notif info freeze |
| | `RCS_GROUP_JID` | `` | WA Group JID untuk notif |
| **CSV Log** | `RCS_USE_CSV_LOG` | `false` | Toggle CSV logging |
| | `RCS_CSV_PREFIX` | `RCS` | Prefix nama file CSV |

#### [MODIFY] [.env](file:///c:/codingVibes/mt5/engulfing/.env)
Tambahkan section `# STRATEGI: RCS (Reversal Candle System)` di akhir file.

#### [MODIFY] [config/__init__.py](file:///c:/codingVibes/mt5/engulfing/config/__init__.py)
Tambahkan `from config.rcs_config import RCSConfig`.

---

### Component 2: State Machine & Engine

#### [NEW] [rcs_state.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/rcs_state.py)
Dataclass `RCSState` untuk menyimpan seluruh runtime state:
- `phase`: enum `PHASE_IDLE` / `PHASE_OP1` / `PHASE_FREEZE`
- `trigger_direction`: `BUY` / `SELL` (dari sinyal trigger)
- `trigger_risk_range`: float (jarak Close-Low bullish / High-Close bearish)
- `op1_level`, `op2_level`, `op3_level`: float (level harga target)
- `op1_ticket`, `op2_ticket`, `op3_ticket`: int | None
- `op1_open_price`: float (harga fill OP1 aktual)
- `tp1_price`, `tp2_price`: float
- `freeze_start_floating_usd`: float (snapshot floating saat hedge)
- `freeze_start_time`: datetime | None
- `freeze_is_hedge`: bool (true jika freeze dari hedge EA, bukan manual)
- `cooldown_until_candle`: int (counter cooldown dalam candle)
- `trigger_age`: int (umur trigger dalam candles)
- Method `reset()` untuk kembali ke IDLE

#### [NEW] [rcs_engine.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/rcs_engine.py)
Fungsi `run_rcs_bot()` — main loop:
1. Load `RCSConfig`, init MT5, init `RCSState`
2. **Main Loop** (per-candle polling + per-tick monitoring):
   - Setiap candle baru pada `RCS_SIGNAL_TIMEFRAME`:
     - Jika `PHASE_IDLE` → panggil trigger detection
     - Jika trigger valid → transisi ke `PHASE_OP1`, hitung level
   - Setiap tick (loop cepat):
     - Jika `PHASE_OP1`:
       - Cek TP via `tp_checker`
       - Cek OP2/OP3 trigger via `op2_handler` / `op3_handler`
       - Cek SL via `sl_checker`
       - Cek posisi "vanished" (broker SL/SO/manual close)
     - Jika `PHASE_FREEZE`:
       - Cek apakah semua posisi/order sudah ditutup
       - Jika ya → hitung recovery → unfreeze → kembali IDLE

---

### Component 3: Trigger Detection

#### [NEW] [engulfing_detector.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/trigger/engulfing_detector.py)
- `detect_engulfing(c1, c2) → TriggerResult | None`
- C1 harus "menelan" full range C2 termasuk ekor (High C1 > High C2 & Low C1 < Low C2)

#### [NEW] [ict_detector.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/trigger/ict_detector.py)
- `detect_ict(candles_df, lookback_bars) → TriggerResult | None`
- Liquidity sweep N candle + rejection candle

#### [NEW] [trigger_filter.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/trigger/trigger_filter.py)
- `apply_all_filters(candle_data, config, ema_value) → (bool, str)`
- Filter chain: Range → Body% → Spread → EMA Pullback
- Return `(passed, skip_reason)` 

#### [NEW] [level_calculator.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/trigger/level_calculator.py)
- `calculate_levels(close_c1, risk_range, direction, config) → dict`
- Hitung OP1, OP2, OP3 dari: `Close ± (riskRange × Percent/100)`

---

### Component 4: Engine Execution (OP1/OP2/OP3)

#### [NEW] [op1_executor.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/engine/op1_executor.py)
- Mode `INSTANT_ZERO`: market order langsung + slip filter
- Mode `PERCENT`: monitor harga → entry saat sentuh level ± toleransi

#### [NEW] [op2_handler.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/engine/op2_handler.py)
- `HEDGE`: buka posisi LAWAN → set Freeze
- `SL`: set SL real ke broker, fallback software SL
- `HEDGE_REENTRY`: buka posisi SEARAH di level OP2 → ganti target ke TP2

#### [NEW] [op3_handler.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/engine/op3_handler.py)
- `HEDGE`: buka lawan lot = OP1+OP2 → Freeze
- `SL`: tutup semua → cooldown → kembali IDLE

#### [NEW] [tp_checker.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/engine/tp_checker.py)
- `TP_MODE_PERCENT`: TP = % jarak OP1→OP2
- `TP_MODE_USD`: target profit USD → convert ke jarak harga

#### [NEW] [sl_checker.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/engine/sl_checker.py)
- Cek SL real broker
- Fallback: software SL monitor setiap tick

---

### Component 5: Freeze & Recovery

#### [NEW] [freeze_manager.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/freeze/freeze_manager.py)
- `enter_freeze(state, positions)`: snapshot floating, catat waktu
- `check_unfreeze(state, symbol)`: cek apakah semua posisi/order sudah 0
- Manual OP detection → auto-freeze

#### [NEW] [recovery_calculator.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/freeze/recovery_calculator.py)
- Hitung profit dari deal history (OP1/OP2/OP3 + deal manual selama freeze)
- Hasil Recovery = `total_profit - freeze_start_floating_usd`

---

### Component 6: Order Manager & Notifier

#### [NEW] [rcs_order_manager.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/rcs_order_manager.py)
Helper MT5: `send_market_order()`, `send_limit_order()`, `close_position()`, `close_all_positions()`, `get_positions_by_magic()`, `get_deals_history()`

#### [NEW] [rcs_notifier.py](file:///c:/codingVibes/mt5/engulfing/strategies/strategy_rcs/rcs_notifier.py)
Notifikasi WA + console log: Trigger, Skip, Open, TP/SL Result, Freeze/Unfreeze. Termasuk estimasi USD per event.

---

## Phase Pengerjaan (Step-by-Step)

> [!IMPORTANT]
> Setiap phase adalah unit kerja mandiri yang bisa ditest sebelum lanjut ke phase berikutnya.

### Phase 1: Foundation (Config + State + Entry Point)
**Target**: Mesin bisa dijalankan, terhubung ke MT5, membaca config, dan loop idle.

| # | Task | File |
|---|------|------|
| 1.1 | Buat `RCSConfig` dataclass | `config/rcs_config.py` |
| 1.2 | Tambah section RCS di `.env` | `.env` |
| 1.3 | Update `config/__init__.py` | `config/__init__.py` |
| 1.4 | Buat `RCSState` dataclass + enum Phase | `strategies/strategy_rcs/rcs_state.py` |
| 1.5 | Buat `rcs_engine.py` skeleton (loop + state machine) | `strategies/strategy_rcs/rcs_engine.py` |
| 1.6 | Buat `rcs_main.py` entry point | `rcs_main.py` |
| 1.7 | Buat `__init__.py` untuk package | `strategies/strategy_rcs/__init__.py` |

**Verifikasi**: `python rcs_main.py` → koneksi MT5 OK, loop berjalan, menunggu di `PHASE_IDLE`.

---

### Phase 2: Trigger Detection
**Target**: Deteksi pola Engulfing/ICT + semua filter, print hasil trigger/skip ke console.

| # | Task | File |
|---|------|------|
| 2.1 | Buat Engulfing detector | `trigger/engulfing_detector.py` |
| 2.2 | Buat ICT detector | `trigger/ict_detector.py` |
| 2.3 | Buat filter chain (Range, Body%, Spread, EMA) | `trigger/trigger_filter.py` |
| 2.4 | Buat level calculator (OP1/OP2/OP3) | `trigger/level_calculator.py` |
| 2.5 | Buat `trigger/__init__.py` | `trigger/__init__.py` |
| 2.6 | Integrasikan trigger ke `rcs_engine.py` PHASE_IDLE | `rcs_engine.py` |

**Verifikasi**: Jalankan bot → trigger terdeteksi dan level dihitung → state pindah ke `PHASE_OP1`.

---

### Phase 3: OP1 Execution
**Target**: Eksekusi OP1 (market/limit) saat trigger valid, TP terpasang.

| # | Task | File |
|---|------|------|
| 3.1 | Buat `rcs_order_manager.py` (helper MT5) | `rcs_order_manager.py` |
| 3.2 | Buat OP1 executor (Instant-Zero + Percent mode) | `engine/op1_executor.py` |
| 3.3 | Buat TP checker (Percent + USD mode) | `engine/tp_checker.py` |
| 3.4 | Buat `engine/__init__.py` | `engine/__init__.py` |
| 3.5 | Integrasikan OP1 + TP ke `rcs_engine.py` | `rcs_engine.py` |

**Verifikasi**: Trigger → OP1 terbuka → TP tercapai → posisi tertutup → kembali IDLE.

---

### Phase 4: OP2 System
**Target**: Sistem OP2 lengkap (HEDGE/SL/HEDGE_REENTRY).

| # | Task | File |
|---|------|------|
| 4.1 | Buat OP2 handler (3 mode) | `engine/op2_handler.py` |
| 4.2 | Buat SL checker (real + software fallback) | `engine/sl_checker.py` |
| 4.3 | Integrasikan OP2 ke `rcs_engine.py` PHASE_OP1 | `rcs_engine.py` |

**Verifikasi**: OP1 aktif → harga sentuh OP2 level → OP2 terbuka → SL/Hedge sesuai mode.

---

### Phase 5: OP3 + Freeze/Recovery
**Target**: Sistem 3-OP lengkap + Freeze-Recovery mechanism.

| # | Task | File |
|---|------|------|
| 5.1 | Buat OP3 handler | `engine/op3_handler.py` |
| 5.2 | Buat Freeze manager | `freeze/freeze_manager.py` |
| 5.3 | Buat Recovery calculator | `freeze/recovery_calculator.py` |
| 5.4 | Buat `freeze/__init__.py` | `freeze/__init__.py` |
| 5.5 | Integrasikan OP3 + Freeze ke `rcs_engine.py` | `rcs_engine.py` |

**Verifikasi**: Skenario penuh: Trigger → OP1 → OP2 HEDGE_REENTRY → OP3 HEDGE → Freeze → Close All → Recovery dihitung → Unfreeze → IDLE.

---

### Phase 6: Notifikasi & Polish
**Target**: Notifikasi WA lengkap + error handling + logging.

| # | Task | File |
|---|------|------|
| 6.1 | Buat RCS notifier (WA + console) | `rcs_notifier.py` |
| 6.2 | Integrasikan notif di semua event engine | Semua engine files |
| 6.3 | Tambah vanished position detection | `rcs_engine.py` |
| 6.4 | Tambah manual OP detection → auto-freeze | `freeze/freeze_manager.py` |
| 6.5 | Final error handling & graceful shutdown | `rcs_engine.py` |

**Verifikasi**: Semua event mengirim notif WA + console log lengkap dengan estimasi USD.

---

## Open Questions

> [!IMPORTANT]
> **Q1**: Apakah RCS ini hanya untuk 1 symbol (seperti ITR yang single symbol), atau multi-symbol?
> Blueprint menunjukkan single symbol per instance. Saya assume **single symbol** per mesin.

> [!IMPORTANT]
> **Q2**: Apakah perlu integrasi CSV logging (seperti di blueprint MQ5), atau cukup console log + WA notif saja untuk versi Python pertama?

> [!IMPORTANT]
> **Q3**: Untuk data candle RCS, apakah boleh reuse `mt5_client/candle_fetcher.py` (`get_closed_candles()`) yang sudah ada, atau perlu fetcher khusus yang return raw DataFrame (untuk lookback ICT sweep)?
> Saya recommend: reuse `get_closed_candles()` untuk data C1/C2, dan buat tambahan helper ringan untuk mengambil N candle lookback untuk ICT sweep saja.

> [!IMPORTANT]
> **Q4**: Untuk notifikasi WA, apakah pakai mekanisme yang sama via `wa_outbox` Supabase table seperti ITR?

---

## Verification Plan

### Per-Phase Testing
Setiap phase memiliki verification point sendiri (lihat di atas).

### Manual Verification
- Jalankan `python rcs_main.py` dan verifikasi:
  - Koneksi MT5 berhasil
  - Trigger detection bekerja (print di console)
  - OP1 terbuka sesuai mode
  - OP2/OP3 bereaksi sesuai level
  - Freeze/Unfreeze cycle lengkap
  - Notifikasi WA terkirim

### Integration Check
- Pastikan `python main.py` (Engulfing scanner) tetap berjalan normal
- Pastikan `python itr_main.py` (ITR bot) tetap berjalan normal
- RCS berjalan di mesin/terminal terpisah tanpa konflik

---

> [!NOTE]
> Total estimasi: **~20+ file baru**, **2 file dimodifikasi** (`.env` dan `config/__init__.py`). Tidak ada perubahan pada modul mesin existing (`mt5_client/`, `database/`, `app/`).
