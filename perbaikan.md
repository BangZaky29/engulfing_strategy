Nah ini baru cara yang gw suka. Jangan ubah banyak file sekaligus. Rapihin **1 file → test → commit → lanjut file berikutnya**. Jadi kalau ada bug kita langsung tahu sumbernya.

Karena **`execution_config.py` sudah fix**, sekarang kita jadikan file itu sebagai **Single Source of Truth** untuk SL & TP.

---

# Urutan refactor yang gw rekomendasiin

## ✅ STEP 1 (SEKARANG)

### `mt5_client/execution.py`

Ini PRIORITAS PALING TINGGI.

Karena file inilah yang benar-benar mengirim order ke MT5.

Targetnya:

> execution.py **tidak boleh menghitung SL/TP lagi**.

Dia cuma melakukan:

```
ambil data candle

↓

ExecutionConfig.calculate_sl_price()

↓

ExecutionConfig.calculate_tp_price()

↓

order_send()
```

Jadi nanti execution.py tinggal menjadi "pemanggil".

---

### Yang harus dihapus

#### 1.

Cari

```python
fixed_distance = 0.0
```

hapus semuanya.

---

#### 2.

Cari

```python
use_fixed_money
```

hapus semua.

Biasanya ada

```python
if getattr(exec_cfg, 'use_fixed_money', False):
```

hapus.

---

#### 3.

Cari

```python
target_profit_usd
```

hapus.

---

#### 4.

Cari

```python
tp_rr_ratio
```

hapus.

---

#### 5.

Cari

```python
sl_ring_pct
```

hapus.

---

#### 6.

Cari

```python
fixed_money_usd
```

hapus.

---

#### 7.

Cari

```python
trade_tick_value
```

yang dipakai buat hitung USD.

hapus.

---

#### 8.

Cari

```python
trade_tick_size
```

kalau hanya dipakai untuk TP USD.

hapus.

---

#### 9.

Cari

```python
ticks_needed
```

hapus.

---

#### 10.

Cari

```python
value_per_tick
```

hapus.

---

## Setelah dibersihkan

Logic BUY tinggal seperti ini

```
BUY

↓

tentukan MARKET / LIMIT

↓

SL payload ?

YES
↓

pakai payload

NO

↓

calculate_sl_price()

↓

TP payload ?

YES

↓

pakai payload

NO

↓

calculate_tp_price()

↓

send order
```

Udah.

Tidak ada logika lain.

---

# STEP 2

Setelah execution.py bersih

baru pindah ke

```
strategies/
engulfing/
signal_builder.py
```

Kenapa?

Karena file ini masih memakai

```
sl_pct_b

tp_pct_b
```

yang sudah lu hapus.

Nanti kita ubah supaya memakai

```
exec_cfg.sl_pct

exec_cfg.tp_pct
```

langsung.

---

# STEP 3

Baru

```
detector.py
```

Ini paling besar.

Karena masih ada

```
Fixed USD

RR

target profit

trade_tick_value

trade_tick_size
```

Semua itu nanti dibersihkan.

---

# STEP 4

Cari seluruh project

```
target_profit_usd
```

Kalau masih ada

↓

hapus.

---

# STEP 5

Cari

```
tp_rr_ratio
```

Kalau masih ada

↓

hapus.

---

# STEP 6

Cari

```
sl_ring_pct
```

Kalau masih ada

↓

hapus.

---

# STEP 7

Cari

```
fixed_money
```

Kalau masih ada

↓

hapus.

---

# Hasil akhirnya

Arsitektur project nanti jadi sederhana banget:

```
.env
│
├── EXECUTION_SL_PCT=110
├── EXECUTION_TP_PCT=75
│
▼
ExecutionConfig
│
├── calculate_sl_price()
└── calculate_tp_price()
│
▼
execution.py
│
▼
MT5
```

Dan file lain (**signal_builder**, **detector**, dll) **tidak lagi menghitung rumus SL/TP sendiri**. Mereka cukup meneruskan data candle (close, high, low, entry) ke `ExecutionConfig`. Dengan begitu, kalau suatu saat lu ubah:

```env
EXECUTION_SL_PCT=95
EXECUTION_TP_PCT=150
```

cukup restart bot, seluruh strategi langsung mengikuti tanpa perlu menyentuh kode lagi.

### Jadi fokus kita sekarang:

> **Rapikan `mt5_client/execution.py` dulu sampai bersih dari seluruh logika lama (Fixed Money, RR, Target USD, Ring SL).** Setelah itu baru pindah ke `signal_builder.py`, baru terakhir `detector.py`. Ini urutan yang paling aman dan minim risiko bug.

