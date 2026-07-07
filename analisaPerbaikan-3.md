Iya bro, sekarang gw nangkep persis konsep yang lu mau. Dan menurut gue ini jauh lebih clean dibanding versi sebelumnya.

## Flow yang tetap dipertahankan

```
H1 Trigger (C1)
        │
        ▼
Hitung Ring H1
(Close ↔ High/Low)
        │
        ▼
Hitung SL (% dari .env)
        │
        ▼
Menunggu Trigger M5
        │
        ▼
OP di M5
        │
        ▼
Hitung Distance OP → SL
        │
        ▼
Hitung TP (% dari .env)
        │
        ▼
Send Order
```

Jadi **H1 tetap hanya menentukan posisi SL**, sedangkan **M5 tetap menentukan Entry/OP**.

---

# Contoh sesuai keinginan lu

## H1 Trigger BUY

```
Close = 3300
Low   = 3290

Ring = 10
```

.env

```env
EXECUTION_SL_PCT=110
EXECUTION_TP_PCT=75
```

## Hitung SL

```
SL = Close - (Ring × 110%)

SL = 3300 - (10 × 1.10)

SL = 3289
```

jadi

```
Close
│
│
│
Low (100%)
│
│
SL (110%)
```

SL berada **10% di luar ekor**.

---

## Lalu M5 trigger

Misal Entry M5

```
Entry = 3298
```

Distance

```
3298 → 3289

= 9 point
```

---

## Hitung TP

Sekarang **bukan lagi 1:1 tetap**.

Tetapi

```
TP Distance

=

Distance(OP→SL)

×

EXECUTION_TP_PCT
```

Karena

```
EXECUTION_TP_PCT=75
```

maka

```
TP Distance

=

9 × 75%

=

6.75
```

jadi

```
TP

=

3298

+

6.75

=

3304.75
```

---

# Artinya sekarang

Dulu

```
SL = 110%

TP = 110%

RR = 1 : 1
```

Sekarang berubah menjadi

```
SL = 110%

TP = 75%

RR otomatis menjadi

1 : 0.75
```

Kalau nanti `.env` diubah

```
EXECUTION_SL_PCT=80

EXECUTION_TP_PCT=150
```

langsung berubah menjadi

```
SL = 80%

TP = 150%

RR = 1 : 1.5
```

Tanpa ubah kode sama sekali.

---

# Rumus final

### BUY

```
Ring = H1 Close - H1 Low

SL = H1 Close - (Ring × SL%)

Distance = Entry(M5) - SL

TP = Entry + (Distance × TP%)
```

---

### SELL

```
Ring = H1 High - H1 Close

SL = H1 Close + (Ring × SL%)

Distance = SL - Entry(M5)

TP = Entry - (Distance × TP%)
```

---

# Jadi sebenarnya RR sudah tidak ada lagi

Ini yang menurut gue penting.

Project nanti **tidak lagi mengenal istilah RR**.

Yang ada hanya dua parameter:

```env
EXECUTION_SL_PCT=
EXECUTION_TP_PCT=
```

Misalnya

```
110
75
```

atau

```
90
200
```

atau

```
60
50
```

Semuanya otomatis dihitung.

---

## Menurut gue ini desain akhirnya

Ini yang akan menjadi **Single Source of Truth**:

* ✅ H1 Trigger → menentukan Ring.
* ✅ `EXECUTION_SL_PCT` → menentukan posisi SL dari Ring H1.
* ✅ M5 Trigger → menentukan harga Entry/OP.
* ✅ `EXECUTION_TP_PCT` → menentukan TP berdasarkan **jarak aktual Entry → SL**.

Dengan desain ini, seluruh perilaku SL/TP cukup dikontrol dari `.env`, tanpa lagi bergantung pada RR ratio, target USD, tick value, atau logika perhitungan lain yang tumpang tindih. Ini juga membuat strategi jauh lebih mudah di-tuning hanya dengan mengubah konfigurasi.
