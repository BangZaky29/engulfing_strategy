Nah ini poin yang sangat penting, dan menurut gue ini justru harus kita **kunci dulu konsepnya** sebelum refactor lagi. Soalnya kemarin di code masih ada campuran beberapa metode (Ring M5, H1 Dynamic, RR, Fixed USD), jadi gampang bikin bingung.

Kalau dari penjelasan lu, **rumus Ring jangan dihapus**. Yang dihapus hanya **cara menentukan persentasenya**. Jadi yang tetap hidup adalah konsep Ring H1.

---

# Arsitektur yang menurut gue paling bersih

## STEP 1 — Tentukan Ring H1

Ini **tidak boleh berubah**.

### BUY

```text
Ring = Close H1 → Low H1
```

misal

```text
Close = 3300
Low   = 3290
```

Ring

```text
10 point
```

---

### SELL

```text
Ring = Close H1 → High H1
```

misal

```text
Close = 3300
High  = 3312
```

Ring

```text
12 point
```

---

## STEP 2 — Hitung SL dari Ring

Ini memakai

```env
EXECUTION_SL_PCT
```

Misal

```env
EXECUTION_SL_PCT=110
```

BUY

```text
SL

=

Close

-

(Ring × 110%)
```

Contoh

```text
Close =3300

Low=3290

Ring=10

SL=3300-(10×1.10)

SL=3289
```

Artinya

**10% keluar dari ekor.**

---

SELL

```text
SL

=

Close

+

(Ring × 110%)
```

Misal

```text
Close=3300

High=3312

Ring=12

SL

=

3300+(12×1.10)

=

3313.2
```

---

# STEP 3 — Baru hitung TP

Nah ini juga jangan lagi pakai RR.

Jangan pakai USD.

Jangan pakai Tick.

Cukup

```text
Distance

=

Entry(OP)

↓

SL
```

Karena OP memang dari M5.

Misal

```text
BUY

Entry=3298

SL=3289
```

Distance

```text
9
```

---

Kalau

```env
EXECUTION_TP_PCT=75
```

maka

```text
TP Distance

=

9×75%

=

6.75
```

TP

```text
3298

+

6.75

=

3304.75
```

Selesai.

---

# Jadi urutannya

```text
H1 Trigger

↓

Close

↓

High/Low

↓

Ring

↓

SL %

↓

SL Price

↓

OP M5

↓

Distance OP→SL

↓

TP %

↓

TP Price
```

Menurut gue ini yang paling konsisten.

---

# Yang penting diperhatikan

Artinya nanti

## execution_config.py

HANYA punya dua fungsi

```python
calculate_sl_price()
```

yang menerima

```text
H1 Close

H1 High

H1 Low

BUY/SELL

SL %
```

---

dan

```python
calculate_tp_price()
```

yang menerima

```text
Entry M5

SL

TP %
```

Udah.

Tidak ada RR.

Tidak ada USD.

Tidak ada Tick.

Tidak ada Grade.

---

# Berarti detector.py nanti cukup ngapain?

Detector **jangan menghitung SL lagi.**

Detector cukup mengirim

```python
signal["h1_trigger_close"]

signal["h1_trigger_low"]

signal["h1_trigger_high"]
```

Udah.

---

# execution.py nanti ngapain?

Execution tinggal

```text
ambil OP M5

↓

ambil H1 Trigger

↓

calculate_sl_price()

↓

calculate_tp_price()

↓

send order
```

---

# Jadi roadmap refactor kita

## ✅ Sudah selesai

* `execution_config.py`

---

## ⏭️ Berikutnya (Paling penting)

**`execution.py`**

Targetnya:

* tetap memakai **Ring H1** sebagai dasar SL.
* OP tetap memakai harga M5 (market atau pending).
* seluruh perhitungan SL memakai `calculate_sl_price()`.
* seluruh perhitungan TP memakai `calculate_tp_price()`.
* hapus semua logika:

  * Fixed USD
  * RR Ratio
  * Tick Value
  * Tick Size
  * Fixed Money

Kalau ini sudah bersih, baru kita rapikan `signal_builder.py` dan terakhir `detector.py`. Dengan urutan itu, konsep **"Ring H1 → SL% → Distance OP-SL → TP%"** akan menjadi satu-satunya alur perhitungan di seluruh project. Menurut gue ini desain yang paling rapi, konsisten, dan gampang di-maintain ke depannya.
