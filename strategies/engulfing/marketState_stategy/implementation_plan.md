# Filter B — EMA Ring Filter (f3_ema_ring)

> **Target Eksekusi**: Senin, **22 Juni 2026**
> **Scope**: Hanya `strategies/engulfing/filters_B/` — Filter A **tidak disentuh**

## Background

Saat ini Filter B (`filters_B`) hanya memiliki 2 filter aktif:
- **F1_B** → Cek engulfing trigger + posisi `Close C1` terhadap `ema_slow`
- **F2_B** → Cek ukuran ring (range point) candle C1

Masalahnya: F1_B hanya cek **Close C1** terhadap EMA. Skenario trigger yang **cross atau bersinggungan dengan EMA_20 tetap lolos** selama Close-nya berada di sisi yang benar. Ini menghasilkan sinyal palsu.

---

## Logika Filter Baru (f3_ema_ring)

### Aturan Inti

```
Untuk Bullish Engulfing (BUY):
  VALID   → Low C1  > EMA_20  AND  Low C2  > EMA_20
  INVALID → High C1 < EMA_20  OR   High C2 < EMA_20   (jadi bearish zone)
  INVALID → salah satu candle cross/touch EMA_20

Untuk Bearish Engulfing (SELL):
  VALID   → High C1 < EMA_20  AND  High C2 < EMA_20
  INVALID → Low C1  > EMA_20  OR   Low C2  > EMA_20   (jadi bullish zone)
  INVALID → salah satu candle cross/touch EMA_20
```

### Visual Diagram

```
──────────── EMA_20 ────────────

Bullish (BUY) VALID ✅
              │  C2 │  C1 │
              │     │     │   ← kedua candle FULL di atas EMA
──── EMA ─────────────────────


Bullish INVALID ❌ (C1 menyentuh/cross EMA)
              │     │  C1 │
──── EMA ────────── ↑ Low C1 menyentuh EMA ─────


Bearish (SELL) VALID ✅
──── EMA ─────────────────────
              │ C2  │  C1 │   ← kedua candle FULL di bawah EMA


Bearish INVALID ❌ (C2 menyentuh/cross EMA)
──── EMA ─── ↓ High C2 menyentuh EMA ─────────
              │ C2  │
```

### Formula Tepat

```python
# Bullish: SELURUH range C1 dan C2 harus di atas EMA_20
bullish_valid = (c1_low > ema_20) and (c2_low > ema_20)

# Bearish: SELURUH range C1 dan C2 harus di bawah EMA_20
bearish_valid = (c1_high < ema_20) and (c2_high < ema_20)
```

> Kondisi **touch** (`==`) dianggap **INVALID** karena candle bersinggungan dengan EMA.

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Strict atau ada toleransi?**
> Saat ini formula menggunakan `>` dan `<` (strict), artinya candle yang **menyentuh tepat** EMA_20 dianggap INVALID. Apakah ini sudah sesuai, atau perlu toleransi kecil (misal: 1 point margin)?

> [!IMPORTANT]
> **Q2 — Apakah ema_20 sudah tersedia di `candle_data`?**
> Dari `detector.py` line 46, tersedia `ema_now` (EMA value pada candle C1). Untuk C2, saat ini tidak ada `ema_value_c2` di `candle_data`. Apakah kita cukup pakai `ema_now` (EMA saat C1 close) untuk validasi kedua candle sekaligus, atau perlu passing `ema_c2` dari MT5?

> [!NOTE]
> **Asumsi default**: Karena EMA_20 di timeframe M5 bergerak lambat, **satu nilai `ema_now` cukup representatif untuk validasi kedua candle** (C1 dan C2). Kalau ingin presisi penuh, perlu tambah field `ema_c2` dari MT5 client.

---

## Proposed Changes

### `filters_B/`

#### [NEW] [f3_ema_ring.py](file:///C:/codingVibes/mt5/engulfing/strategies/engulfing/filters_B/f3_ema_ring.py)

File baru untuk logika validasi EMA Ring:

```python
# strategies/engulfing/filters_B/f3_ema_ring.py
# F3_B: EMA Ring Filter — Validasi seluruh range C1 & C2 terhadap EMA_20

def check_ema_ring_b(
    c1_high: float, c1_low: float,
    c2_high: float, c2_low: float,
    ema_20: float,
    pattern_type: str,          # "bullish_engulfing" | "bearish_engulfing"
    verbose: bool = False,
    color: str = "",
) -> bool:
    """
    Validasi: Seluruh range (high-low) candle C1 dan C2 harus
    BENAR-BENAR berada di satu sisi EMA_20.
    Candle yang cross atau menyentuh EMA_20 → INVALID.
    """
    if pattern_type == "bullish_engulfing":
        # Semua harga harus di atas EMA
        valid = (c1_low > ema_20) and (c2_low > ema_20)
        ...
    else:
        # Semua harga harus di bawah EMA
        valid = (c1_high < ema_20) and (c2_high < ema_20)
        ...
    return valid
```

---

#### [MODIFY] [__init__.py](file:///C:/codingVibes/mt5/engulfing/strategies/engulfing/filters_B/__init__.py)

Tambah export `check_ema_ring_b`:

```diff
  from .f1_trigger import check_engulfing_trigger_b
  from .f2_pattern import check_pattern_size_b
+ from .f3_ema_ring import check_ema_ring_b

  __all__ = [
      "check_engulfing_trigger_b",
      "check_pattern_size_b",
+     "check_ema_ring_b",
  ]
```

---

#### [MODIFY] [detector.py](file:///C:/codingVibes/mt5/engulfing/strategies/engulfing/detector.py)

Panggil `check_ema_ring_b` setelah F1_B lolos, sebelum F2_B:

```diff
  from .filters_B import check_engulfing_trigger_b, check_pattern_size_b
+ from .filters_B import check_ema_ring_b
```

Di dalam blok `if cfg.active_filter_strategy == 'B':`:

```diff
  # [F1_B] Engulfing Trigger & EMA Slow
  is_valid, pattern_type = check_engulfing_trigger_b(...)
  if not is_valid or pattern_type is None:
      return None

+ # [F3_B] EMA Ring Filter — seluruh range C1 & C2 harus strict satu sisi EMA
+ valid_ema_ring = check_ema_ring_b(
+     c1_high, c1_low, c2_high, c2_low,
+     ema_now, pattern_type, verbose, color
+ )
+ if not valid_ema_ring:
+     return None   # Skip langsung, tidak perlu build signal

  # [F2_B] Pattern Size
  valid_f2_b = check_pattern_size_b(...)
```

> **Note**: Filter ini di-`return None` (hard reject), bukan `skip_reason`, karena trigger yang cross EMA tidak layak dijadikan data riset sama sekali.

---

### `.env` / `engulfing_config.py`

> [!NOTE]
> Tidak ada perubahan config yang diperlukan. Filter ini adalah **hard filter** (pass/fail) yang tidak memiliki parameter threshold, sehingga tidak butuh environment variable baru.

---

## Urutan Filter B Setelah Perubahan

```
F1_B  →  Engulfing Trigger + Close C1 vs EMA_slow
  ↓ LOLOS
F3_B  →  [BARU] EMA Ring: seluruh C1+C2 strict di atas/bawah EMA_20   ← NEW
  ↓ LOLOS
F2_B  →  Pattern Size (ring point range C1)
  ↓ LOLOS
Build Signal + OP Order
```

---

## Verification Plan

### Unit Test Manual (jalankan di terminal)

```bash
# Test via main.py dengan data dummy atau live MT5
python main.py
```

Skenario yang harus dicek:

| Skenario | C1 Low | C2 Low | EMA_20 | Expected |
|---|---|---|---|---|
| Bullish FULL atas EMA | 3375 | 3371 | 3370 | ✅ VALID |
| Bullish C1 touch EMA | 3370 | 3373 | 3370 | ❌ INVALID |
| Bullish C2 cross EMA | 3372 | 3368 | 3370 | ❌ INVALID |
| Bearish FULL bawah EMA | - | High C1=3365 | 3370 | ✅ VALID |
| Bearish C1 touch EMA | - | High C1=3370 | 3370 | ❌ INVALID |

### Verbose Output yang Diharapkan

```
   [F3_B] EMA Ring: C1 Low (3375.00) > EMA (3370.00) ✅ | C2 Low (3371.00) > EMA (3370.00) ✅ -> OK
   [F3_B] EMA Ring: C1 Low (3370.00) touch/cross EMA (3370.00) -> SKIP ❌
```

---

## Summary Perubahan File

| File | Action | Keterangan |
|---|---|---|
| `filters_B/f3_ema_ring.py` | **NEW** | Logic utama EMA Ring filter |
| `filters_B/__init__.py` | **MODIFY** | Export `check_ema_ring_b` |
| `strategies/engulfing/detector.py` | **MODIFY** | Panggil F3_B setelah F1_B |
| `config/engulfing_config.py` | **TIDAK DIUBAH** | Tidak butuh param baru |
| `.env` | **TIDAK DIUBAH** | Hard filter, tanpa threshold |



Ada 2 open question di plan yang perlu konfirmasi sebelum Senin:

1. Strict atau ada toleransi? — Saat ini candle yang touch/== EMA dianggap invalid. Sudah sesuai?
2. ema_c2 perlu dikirim dari MT5 atau pakai ema_now saja? — Default asumsi pakai ema_now yang sama untuk C1 & C2 karena EMA_20 di M5 bergerak lambat.

Jawabannya : 
1. sudah selesai ema  EMA dianggap invalid. tidak boleh bersinggungan
2. pakai ema_now saja sudah cukup  karena harga c1 dan c2 juga sangat berdekatan