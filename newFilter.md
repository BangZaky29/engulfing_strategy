



Siap bro. Kita breakdown **semua rumus dan alur filter indikator Engulfing Research** yang sekarang kita bangun.

Saya luruskan dulu istilahnya:

```text
C1 = candle trigger / candle engulfing
C2 = candle sebelumnya
```

C1 harus **sudah close**, bukan candle running.

---

# 0. Syarat Awal: Engulfing Trigger

Sebelum masuk scoring, candle harus lolos trigger dulu.

## Bullish Engulfing

```text
C2 bearish:
Close C2 < Open C2

C1 bullish:
Close C1 > Open C1

Valid engulfing:
Close C1 >= Open C2
```

## Bearish Engulfing

```text
C2 bullish:
Close C2 > Open C2

C1 bearish:
Close C1 < Open C1

Valid engulfing:
Close C1 <= Open C2
```

Kalau belum lolos ini, semua scoring tidak dihitung.

---

# 1. Range C1

Range C1 adalah tinggi total candle engulfing.

```text
Range C1 = High C1 - Low C1
```

Untuk XAU, kita ubah ke point seperti crosshair MT5:

```text
RangePoint = (High C1 - Low C1) / _Point
```

Contoh:

```text
High C1 = 3375.00
Low C1  = 3371.00

Range = 4.00
_Point = 0.01

RangePoint = 4.00 / 0.01 = 400
```

Jadi:

```text
R : 400
```

Artinya candle C1 tingginya 400 point atau 4 USD.

---

# 2. Persentase Body C1

Body adalah isi candle, dari open ke close.

```text
Body = abs(Close C1 - Open C1)
```

Dalam point:

```text
BodyPoint = abs(Close C1 - Open C1) / _Point
```

Persentase body:

```text
Body% = BodyPoint / RangePoint × 100
```

Contoh:

```text
Range = 400
Body  = 280

Body% = 280 / 400 × 100
      = 70%
```

Jadi notif:

```text
B : 70%
```

Artinya:

```text
70% dari candle C1 adalah body.
```

Semakin besar B%, semakin dominan buyer/seller.

---

# 3. Persentase Wick / Ekor C1

Wick adalah total ekor atas + ekor bawah.

```text
WickPoint = RangePoint - BodyPoint
```

Persentase wick:

```text
Wick% = 100 - Body%
```

Contoh:

```text
Range = 400
Body  = 280

Wick = 120

Body% = 70%
Wick% = 30%
```

Artinya:

```text
70% body
30% wick
```

Kalau wick besar, berarti banyak rejection / tarik-menarik harga.

---

# 4. CP — Candle Power / Close Power

Ini salah satu point paling penting.

CP mengukur:

```text
Seberapa jauh Close C1 menelan C2.
```

Bukan cuma valid engulfing, tapi seberapa kuat close-nya.

---

## Bullish CP

```text
CP = (Close C1 - Open C2) / (High C2 - Low C2) × 100
```

Contoh:

```text
C2:
High = 3370
Open = 3368
Low  = 3364

Range C2 = 3370 - 3364 = 6.00 = 600 point

C1:
Close = 3374
```

Hitung penetrasi:

```text
Close C1 - Open C2
3374 - 3368 = 6.00 = 600 point
```

CP:

```text
600 / 600 × 100 = 100%
```

Artinya close C1 sudah menelan 100% ukuran range C2.

---

## Bearish CP

```text
CP = (Open C2 - Close C1) / (High C2 - Low C2) × 100
```

Contoh:

```text
C2:
High = 3370
Open = 3368
Low  = 3364

Range C2 = 600 point

C1 bearish:
Close = 3362
```

Penetrasi:

```text
Open C2 - Close C1
3368 - 3362 = 6.00 = 600 point
```

CP:

```text
600 / 600 × 100 = 100%
```

---

## Cara baca CP

| CP | Arti |
|---:|---|
| < 50% | Lemah |
| 50–80% | Lumayan |
| 80–100% | Kuat |
| > 100% | Sangat kuat |

Kalau notif:

```text
CP : 128%
```

Artinya:

```text
Close C1 bukan cuma engulfing,
tapi sudah menembus lebih jauh dari ukuran C2.
```

---

# 5. EMA — Posisi Trigger terhadap EMA

EMA kita pakai untuk baca konteks C1 terhadap EMA 20.

Default:

```text
EMA = EMA 20
```

Yang dihitung:

```text
Open C1
Close C1
EMA value pada candle C1
```

---

## Status EMA

### Cross

```text
Open C1 < EMA dan Close C1 > EMA
```

atau

```text
Open C1 > EMA dan Close C1 < EMA
```

Artinya candle C1 menembus EMA.

```text
EMA : Cross
```

---

### Above

```text
Close C1 > EMA
```

Artinya trigger close di atas EMA.

```text
EMA : Above
```

---

### Below

```text
Close C1 < EMA
```

Artinya trigger close di bawah EMA.

```text
EMA : Below
```

---

# 6. Market State / Market Stitch

Yang ini kita hitung di belakang layar.

Tujuannya:

```text
Membedakan market trending atau sideways.
```

Karena engulfing di market trend biasanya lebih bagus, sedangkan engulfing di sideways sering fake.

---

## Data yang dipakai

Kita pakai:

```text
EMA sekarang
EMA beberapa candle sebelumnya
Average Range
Jumlah candle cross EMA
Mayoritas close di atas/bawah EMA
```

Default:

```text
MarketLookback = 20 candle
```

---

## A. EMA Slope

Mengukur kemiringan EMA.

```text
SlopePoint = abs(EMA sekarang - EMA 20 candle lalu) / _Point
```

Lalu dibandingkan dengan rata-rata range:

```text
SlopeRatio = SlopePoint / AverageRange
```

Kalau EMA hampir datar:

```text
SlopeRatio kecil
```

Kemungkinan sideways.

Kalau EMA miring jelas:

```text
SlopeRatio besar
```

Kemungkinan trending.

---

## B. Cross Ratio

Menghitung seberapa sering candle bolak-balik menembus EMA.

```text
CrossRatio = jumlah candle cross EMA / jumlah candle yang dicek
```

Kalau terlalu sering cross EMA:

```text
Market = Sideways
```

Karena harga bolak-balik EMA.

---

## C. Side Strength

Menghitung apakah harga mayoritas berada di satu sisi EMA.

```text
SideStrength = abs(jumlah close di atas EMA - jumlah close di bawah EMA) / total candle
```

Kalau mayoritas candle berada satu sisi EMA:

```text
Market = Trending
```

Kalau seimbang atas-bawah:

```text
Market = Sideways / normal
```

---

# Scoring Grade

Sekarang score utama dihitung dari:

```text
Score =
BodyScore
+ RangeScore
+ EMAScore
+ CPScore
+ MarketStateScore
```

Bobotnya:

| Komponen | Bobot |
|---|---:|
| Body % | 40 |
| Range | 30 |
| EMA | 20 |
| CP | 10 |
| Market State | +5 / -15 |

---

## Body Score

```text
BodyScore = Body% / 100 × 40
```

Contoh:

```text
B = 70%

BodyScore = 70 / 100 × 40
          = 28
```

---

## Range Score

Range C1 dibandingkan dengan average range 20 candle.

```text
RangeRatio = Range C1 / AverageRange
```

Lalu:

```text
RangeScore = min(RangeRatio, 1.5) / 1.5 × 30
```

Contoh:

```text
Range C1 = 400
AverageRange = 250

RangeRatio = 400 / 250 = 1.6
```

Karena maksimum 1.5:

```text
RangeScore = 30
```

---

## EMA Score

```text
EMA Cross = 20
EMA Above / Below = 15
Touch / None = 0
```

---

## CP Score

```text
CPScore = min(CP, 100) / 100 × 10
```

Contoh:

```text
CP = 128%
```

Dibatasi menjadi 100:

```text
CPScore = 10
```

Contoh lain:

```text
CP = 70%

CPScore = 70 / 100 × 10
        = 7
```

---

## Market State Score

```text
Trending = +5
Sideways = -15
Normal   = 0
```

Kenapa sideways dihukum besar?

Karena di XAU M5, engulfing di sideways sering terlihat valid tapi gampang mental balik.

---

# Grade Akhir

Setelah total score dihitung, grade-nya:

| Score | Grade |
|---:|---|
| 95–100 | A+ |
| 90–94 | A |
| 85–89 | B+ |
| 80–84 | B |
| 75–79 | C+ |
| 70–74 | C |
| < 70 | D |

---

# Alur Filter Lengkap

Urutannya seperti ini:

```text
1. Cek candle sudah close
2. Cek trigger engulfing
3. Hitung Range C1
4. Hitung Body% dan Wick%
5. Hitung CP%
6. Hitung posisi EMA
7. Hitung Market State
8. Hitung Score
9. Konversi ke Grade
10. Tentukan Action:
    BUY REVERSAL
    SELL REVERSAL
    BUY TREND
    SELL TREND
11. Tentukan RR dan SL suggestion
12. Kirim notif
```

---

# Format Notif Final

```text
Engulfing | XAUUSD | M5 | BUY REVERSAL | Grade : A | B : 71% | CP : 128% | RR : 1.5 | SL : 75%
```

Artinya:

```text
Ada bullish engulfing
di XAUUSD M5

Tipe setup:
BUY REVERSAL

Kualitas:
Grade A

Body C1:
71%

Close Power:
128%

Saran TP:
1.5R

Saran SL:
75% dari candle C1
```

---

# Kesimpulan Simple

Yang paling penting dibaca:

```text
1. Grade
2. Action: Reversal / Trend
3. B%
4. CP%
5. RR dan SL suggestion
```

Untuk keputusan cepat:

```text
A+ / A = prioritas
B+ = masih layak test
B = hati-hati
C+ = hanya untuk research
C / D = skip
```

Dan untuk Research EA nanti, kita sepakat:

```text
Trade:
A+, A, B+, B, C+

Skip:
C, D
```

Karena kita mau kumpulkan data dulu, baru nanti final setting-nya dikunci.