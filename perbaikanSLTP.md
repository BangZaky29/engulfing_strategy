# 🔧 ANALISIS & FIX: SL/TP Strategy B — Panduan Lengkap

> **Repo:** `BangZaky29/engulfing_strategy`  
> **Tujuan:** SL = 110% dari ekor C1 | TP = 75% dari jarak OP→SL  
> **Kesimpulan:** ✅ HANYA `.env` yang perlu diubah — kode Python sudah benar

---

## 📊 Flow Diagram: Bagaimana `.env` Terhubung ke Code

```
.env
 ├── EXECUTION_SL_PCT_B=110  ──→  execution_config.py
 │                                  └── sl_pct_b = os.getenv("EXECUTION_SL_PCT_B", "70")
 │                                        └── signal_builder.py
 │                                              └── sl_pct_b = exec_cfg.sl_pct_b
 │                                                    └── sl_price = c1_close - (range_ref * sl_pct_b/100)
 │                                                          └── signal["sl_price"]  ──→  execution.py
 │                                                                                        └── sl_price = sl_price_payload ✅
 │
 ├── EXECUTION_TP_PCT_B=75   ──→  execution_config.py
 │                                  └── tp_pct_b = os.getenv("EXECUTION_TP_PCT_B", "100")
 │                                        └── signal_builder.py
 │                                              └── tp_pct = exec_cfg.tp_pct_b
 │                                                    └── tp_price = op + |op-sl| * tp_pct/100
 │                                                          └── signal["tp_price"]  ──→  execution.py
 │                                                                                        └── tp_price = signal["tp_price"] ✅
 │
 ├── EXECUTION_SL_PCT=110.0  ──→  execution_config.py (FALLBACK ONLY)
 │                                  └── calculate_sl_price() → hanya aktif jika sl_price_payload=None
 │
 └── EXECUTION_TP_PCT=75.0   ──→  execution_config.py (FALLBACK ONLY)
                                    └── calculate_tp_price() → hanya aktif jika signal["tp_price"]=None
```

> **Catatan:** Strategy B selalu mengisi `signal["sl_price"]` dan `signal["tp_price"]`,
> sehingga fallback di `execution.py` **tidak pernah dipakai** saat Strategy B aktif.

---

## ✅ Verifikasi Matematika Formula

Formula di `signal_builder.py` sudah BENAR untuk tujuan ini:

```python
# BUY (bullish):
range_ref = c1_close - c1_low         # = panjang ekor bawah
sl_price  = c1_close - (range_ref * (sl_pct_b / 100.0))

# Interpretasi sl_pct_b:
#   100% → sl = close - range_ref       = Low          (tepat di ujung ekor)
#   110% → sl = close - range_ref*1.10  = Low - 10%    (10% di LUAR Low)
#   120% → sl = close - range_ref*1.20  = Low - 20%    (20% di LUAR Low)
```

**Simulasi angka nyata (Close=3300, Low=3290, High=3310):**

| Konfigurasi       | OP     | SL          | TP      | Risk   | Reward | RR    |
|-------------------|--------|-------------|---------|--------|--------|-------|
| LAMA (105% / 100%)| 3298.0 | 3289.5 (-0.5 dari Low) | 3306.5 | 8.50 pts | 8.50 pts | 1:1.00 |
| **BARU (110% / 75%)** | **3298.0** | **3289.0 (-1.0 dari Low)** | **3304.75** | **9.00 pts** | **6.75 pts** | **1:0.75** |

> SL 110% = SL berada **1.0 point di bawah Low** (10% dari range_ref=10 pts)

---

## 🎯 Yang Perlu Diubah: HANYA `.env`

### File: `C:\codingVibes\mt5\engulfing\.env`

Cari dan ubah **dua baris** ini:

```env
# ====================================================
# SEBELUM (nilai lama):
# ====================================================
EXECUTION_SL_PCT_B=105
EXECUTION_TP_PCT_B=100

# ====================================================
# SESUDAH (nilai baru — sesuai tujuan 110%/75%):
# ====================================================
EXECUTION_SL_PCT_B=110
EXECUTION_TP_PCT_B=75
```

**Pastikan juga dua baris fallback ini sudah ada (biasanya sudah):**
```env
# SL versi tail (ekor) — FALLBACK jika Strategy A atau payload kosong
EXECUTION_SL_PCT=110.0

# TP berbasis jarak OP ke SL — FALLBACK
EXECUTION_TP_PCT=75.0
```

---

## 📂 File Python yang TIDAK Perlu Diubah

| File | Status | Alasan |
|------|--------|--------|
| `config/execution_config.py` | ✅ Sudah benar | Sudah baca `EXECUTION_SL_PCT_B` & `EXECUTION_TP_PCT_B` via `os.getenv()` |
| `strategies/engulfing/signal_builder.py` | ✅ Sudah benar | Formula `close - range_ref * sl_pct_b/100` sudah support >100% |
| `mt5_client/execution.py` | ✅ Sudah benar | Prioritas pakai `sl_price_payload` dari signal, bukan hitung ulang |
| `config/engulfing_config.py` | ✅ Tidak relevan | Tidak berisi logika SL/TP |

---

## 🔍 Detail Kode yang Sudah Terhubung

### 1. `config/execution_config.py` — Membaca `.env`

```python
# Baris 124-129 — Sudah dinamis!
sl_pct_b: float = field(
    default_factory=lambda: float(os.getenv("EXECUTION_SL_PCT_B", "70"))  # ← default lama
)
tp_pct_b: float = field(
    default_factory=lambda: float(os.getenv("EXECUTION_TP_PCT_B", "100"))  # ← default lama
)
```

> Begitu `.env` diubah, nilai ini otomatis ikut berubah. Tidak ada hardcode di code.

### 2. `strategies/engulfing/signal_builder.py` — Pakai dari `exec_cfg`

```python
# Baris 94-115 (Strategy B path)
if cfg.active_filter_strategy == 'B':
    op_pct   = exec_cfg.op_pct_b    # ← EXECUTION_OP_PCT_B (tetap 20)
    sl_pct_b = exec_cfg.sl_pct_b    # ← EXECUTION_SL_PCT_B (UBAH ke 110)
    tp_pct   = exec_cfg.tp_pct_b    # ← EXECUTION_TP_PCT_B (UBAH ke 75)

    if pattern_type.startswith("bullish"):
        range_ref = c1_close - c1_low
        op_price  = c1_close - (range_ref * (op_pct / 100.0))
        sl_price  = c1_close - (range_ref * (sl_pct_b / 100.0))  # 110% → 10% di luar Low
        tp_dist   = abs(op_price - sl_price) * (tp_pct / 100.0)  # 75% dari jarak OP→SL
        tp_price  = op_price + tp_dist
    else:  # bearish
        range_ref = c1_high - c1_close
        op_price  = c1_close + (range_ref * (op_pct / 100.0))
        sl_price  = c1_close + (range_ref * (sl_pct_b / 100.0))  # 110% → 10% di luar High
        tp_dist   = abs(op_price - sl_price) * (tp_pct / 100.0)  # 75% dari jarak OP→SL
        tp_price  = op_price - tp_dist

    sl_pct_used = sl_pct_b  # dicatat di notes_payload untuk logging
```

### 3. `mt5_client/execution.py` — Pakai payload langsung

```python
# Baris 197-230 (BUY path)
# SL → langsung pakai dari payload (tidak hitung ulang!)
if sl_price_payload is not None:
    sl_price = sl_price_payload     # ← DARI SIGNAL_BUILDER ✅
    print(f"   [SL] Menggunakan SL H1 Dynamic dari detector: {sl_price:.2f}")
# ... fallback hanya jika sl_price_payload = None (tidak terjadi di Strategy B)

# TP → langsung pakai dari payload (tidak hitung ulang!)
if signal.get("tp_price") is not None:
    tp_price = float(signal["tp_price"])  # ← DARI SIGNAL_BUILDER ✅
    print(f"   [TP] Menggunakan TP payload dari detector: {tp_price:.2f}")
# ... fallback hanya jika tp_price = None (tidak terjadi di Strategy B)
```

---

## ⚠️ Optional: Update Default Values di execution_config.py

Ini **tidak wajib** karena `.env` kamu sudah set nilainya. Tapi sebaiknya default-nya konsisten:

```python
# config/execution_config.py — Baris 124-129
# Ganti default lama:
sl_pct_b: float = field(
    default_factory=lambda: float(os.getenv("EXECUTION_SL_PCT_B", "70"))   # ← lama
)
tp_pct_b: float = field(
    default_factory=lambda: float(os.getenv("EXECUTION_TP_PCT_B", "100"))  # ← lama
)

# Jadi default baru (sama dengan tujuan kamu):
sl_pct_b: float = field(
    default_factory=lambda: float(os.getenv("EXECUTION_SL_PCT_B", "110"))  # ← baru
)
tp_pct_b: float = field(
    default_factory=lambda: float(os.getenv("EXECUTION_TP_PCT_B", "75"))   # ← baru
)
```

> Ini hanya berguna kalau ada deployment baru yang lupa set `.env`.

---

## 🧪 Cara Verifikasi Setelah Ubah `.env`

Jalankan ini di terminal project kamu:

```bash
cd C:\codingVibes\mt5\engulfing
python -c "
from config.execution_config import ExecutionConfig
cfg = ExecutionConfig()
print(f'SL_PCT_B  = {cfg.sl_pct_b}')   # harus 110.0
print(f'TP_PCT_B  = {cfg.tp_pct_b}')   # harus 75.0
print(f'OP_PCT_B  = {cfg.op_pct_b}')   # tetap 20.0
print(f'SL_PCT    = {cfg.sl_pct}')     # harus 110.0 (fallback)
print(f'TP_PCT    = {cfg.tp_pct}')     # harus 75.0  (fallback)
"
```

**Output yang benar:**
```
SL_PCT_B  = 110.0
TP_PCT_B  = 75.0
OP_PCT_B  = 20.0
SL_PCT    = 110.0
TP_PCT    = 75.0
```

---

## 📌 Ringkasan Perubahan

| Apa | Di Mana | Nilai Lama | Nilai Baru |
|-----|---------|-----------|-----------|
| `EXECUTION_SL_PCT_B` | `.env` | `105` | **`110`** |
| `EXECUTION_TP_PCT_B` | `.env` | `100` | **`75`** |

> **Total perubahan: 2 baris di `.env` — tidak ada perubahan kode Python.**

---

*Dibuat berdasarkan analisis repo: `github.com/BangZaky29/engulfing_strategy`*