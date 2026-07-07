BLUEPRINT LENGKAP
TF Monitor EA 03072026 + MFE Percent Research

File ZIP sumber:
TF_Monitor_EA_03072026_MFE_Percent.zip

Tujuan blueprint:
Dokumen ini menjelaskan struktur kode, alur logika, input, CSV, MFE Percent Research, OP Level Filter, dan batasan keras agar revisi berikutnya tidak merusak logika yang sudah benar.

====================================================================
1. IDENTITAS PROJECT
====================================================================

Nama EA utama:
MQL5/Experts/TF_Monitor_EA.mq5

Folder include:
MQL5/Include/TF_Monitor_EA/

Versi basis:
TF_monitor EA 03072026

Versi gabungan:
03072026 + MFE Percent Research + OP Level Filter

Fokus utama versi ini:
1. Tetap memakai logic OP 03072026.
2. Tidak mengubah Notification.mqh.
3. Tidak mengubah OPFilter.mqh.
4. Tidak mengubah TriggerLogic.mqh.
5. Tidak mengubah BiasLogic.mqh.
6. Menambahkan MFE lengkap untuk riset TP/SL percent.
7. Menambahkan OP Level Percent dari candle trigger H1 C1.
8. Menambahkan input tuning baru, dengan default aman.
9. Menambahkan kolom CSV baru untuk riset.

====================================================================
2. ATURAN KERAS REVISI
====================================================================

Aturan ini wajib dipertahankan di revisi berikutnya:

1. Logika status H1/M15/M5 yang sudah benar tidak boleh dirombak.
2. Status STRONG / VALID / RETRACE / WAIT tetap dihitung dari logic yang sudah ada.
3. M5 tetap dipakai sebagai filter/timing OP sesuai input OP CUSTOM FILTER - M5.
4. Notification.mqh tidak boleh diganti formatnya tanpa instruksi khusus.
5. OPFilter.mqh tidak boleh diganti karena sudah menjadi filter OP 03072026.
6. TradePlan.mqh boleh ditambah hanya untuk perhitungan data riset, bukan mengganti konsep SL/TP yang sudah disepakati.
7. MFE hanya alat ukur/logging. MFE tidak boleh mengubah entry, tidak boleh mengubah close, tidak boleh mengubah notifikasi.
8. Kolom CSV baru harus ditambah di belakang atau dengan struktur jelas. Jangan menggeser data lama tanpa alasan.
9. Default input baru harus aman. Jika filter baru ditambahkan, default-nya OFF supaya perilaku EA sama seperti 03072026.
10. Jika nanti dibuat filter untuk status lain seperti RETRACE STRONG, buat blok input sendiri. Jangan campur dengan blok STRONG yang sekarang.

====================================================================
3. STRUKTUR FILE
====================================================================

1. MQL5/Experts/TF_Monitor_EA.mq5
   File utama EA.
   Tugas:
   - Include semua modul.
   - OnInit membuat timer dan EMA handle.
   - OnDeinit melepas timer dan EMA handle.
   - OnTick update floating/MFE.
   - OnTimer menjalankan logic utama EA.
   - OnTradeTransaction memproses close trade.

2. MQL5/Include/TF_Monitor_EA/Config.mqh
   Tugas:
   - Menyimpan enum, struct, global variable, dan semua input EA.
   - Input baru MFE Percent Research dan OP Level Filter ada di sini.

3. MQL5/Include/TF_Monitor_EA/Utils.mqh
   Tugas:
   - Fungsi umum: text TF, arah, state, age candle, EMA, OHLC, spread, reset context, date/time, session, dll.
   - Menyimpan fungsi reset TFM_CurrentTrade.

4. MQL5/Include/TF_Monitor_EA/TriggerLogic.mqh
   Tugas:
   - Mendeteksi trigger Marubozu, Pinbar, Engulfing, ICT, Dominan Break.
   - Tidak diubah dari basis 03072026.

5. MQL5/Include/TF_Monitor_EA/BiasLogic.mqh
   Tugas:
   - Menghitung arah H1, M15, M5.
   - Menghitung status STRONG, VALID, RETRACE STRONG, RETRACE VALID, EARLY, LATE, WAIT.
   - Tidak diubah dari basis 03072026.

6. MQL5/Include/TF_Monitor_EA/OPFilter.mqh
   Tugas:
   - Menentukan apakah setup boleh OP berdasarkan filter H1/M15/M5.
   - Tidak diubah dari basis 03072026.

7. MQL5/Include/TF_Monitor_EA/TradePlan.mqh
   Tugas:
   - Menghitung entry, SL, TP, risk range H1, OP level percent.
   - Menjalankan OP Level Filter jika input UseOPLevelFilter = true.
   - Menghitung estimasi profit/loss USD.

8. MQL5/Include/TF_Monitor_EA/MFETracker.mqh
   Modul baru.
   Tugas:
   - Inisialisasi MFE saat order open.
   - Menghitung SL distance, TP distance.
   - Menghitung MaxProfit/MaxLoss percent.
   - Menghitung virtual TP/SL study hit.
   - Modul ini tidak mengubah entry/exit.

9. MQL5/Include/TF_Monitor_EA/Logger.mqh
   Tugas:
   - Membuat header CSV.
   - Menulis baris CSV.
   - Menambahkan data MFE dan OPLevel ke CSV.

10. MQL5/Include/TF_Monitor_EA/Notification.mqh
    Tugas:
    - Signal notification.
    - OP Block Experts.
    - OP Plan Experts.
    - Trade Open notification.
    - Trade Failed notification.
    - Close notification.
    - Tidak diubah dari basis 03072026.

11. MQL5/Include/TF_Monitor_EA/ChartMarker.mqh
    Tugas:
    - Menggambar marker entry dan result.

12. README_MFE_PERCENT_RESEARCH.txt
    Catatan singkat tambahan tentang versi MFE Percent Research.

====================================================================
4. ALUR PROGRAM UTAMA
====================================================================

OnInit:
1. Reset EA state.
2. Init EMA handle untuk H1, M15, M5.
3. Set timer berdasarkan MonitorTimerSeconds.
4. Print status loaded ke Experts jika PrintLoadStatus = true.

OnTick:
1. Memanggil TFM_UpdateFloatingStats().
2. Fungsi ini update MaxFloatingMinusPoints dan MaxFloatingPlusPoints saat posisi masih aktif.
3. Ini bagian utama untuk MFE berjalan real-time.

OnTimer:
1. Memanggil TFM_ProcessEALogic().
2. Proses ini melakukan scan H1/M15/M5, hitung status, log signal, lalu mencoba OP.

OnTradeTransaction:
1. Hanya memproses transaksi DEAL_ADD.
2. Memanggil TFM_ProcessClosedDeal(trans.deal).
3. Saat posisi close, MFE final ditulis ke CSV dan notifikasi close dikirim.

====================================================================
5. TIMEFRAME YANG DIPANTAU
====================================================================

EA memakai 3 timeframe tetap:

Index 0 = H1
Index 1 = M15
Index 2 = M5

H1:
- Arah utama OP.
- Candle trigger H1 C1 menjadi dasar risk range.
- SL percent diukur dari candle trigger H1 C1.

M15:
- Konfirmasi utama terhadap H1.
- Bisa wajib searah H1 berdasarkan input OP_M15_MustSameAsH1.

M5:
- Filter/timing OP.
- Bisa ON/OFF berdasarkan input OP_UseM5Filter.
- Bisa wajib searah H1 atau bebas berdasarkan input OP_M5_MustSameAsH1.

====================================================================
6. STATUS DAN BATASAN STATUS OP
====================================================================

Input terkait:
OneTradePerStrongSetup
RequireOriginalStrongStatus

OneTradePerStrongSetup:
Jika true, EA hanya OP satu kali untuk setup STRONG H1/M15 yang sama.
Jika false, M5 bisa ikut membentuk key OP sehingga dalam setup H1/M15 sama bisa ada peluang entry baru jika M5 berubah.

RequireOriginalStrongStatus:
Jika true, EA hanya boleh OP saat status = STRONG.
Jika false, EA tidak mewajibkan STRONG, tetapi saat ini belum ada pilihan status detail per status.

Desain saat ini:
Blok input OP CUSTOM FILTER H1/M15/M5 dipakai khusus untuk memaksimalkan STRONG.
Untuk sementara RequireOriginalStrongStatus disarankan tetap true.

Rencana masa depan:
Jika nanti ingin trading status lain, buat blok input sendiri, contoh:
- VALID FILTER - H1/M15/M5
- RETRACE STRONG FILTER - H1/M15/M5
- RETRACE VALID FILTER - H1/M15/M5
Jangan campur dengan blok STRONG saat ini.

====================================================================
7. INPUT UTAMA
====================================================================

=== TF MONITOR ===
MonitorTimerSeconds = interval timer scan.
TriggerLookbackBars = jumlah candle yang dicari untuk trigger.
FirstLoadDelaySeconds = delay awal setelah EA load.
PrintLoadStatus = print status load/wait data.
TradeOnFirstLoad = jika false, EA tidak langsung OP di snapshot pertama.

=== EMA FILTER GLOBAL ===
UseEMAFilter = filter EMA global untuk trigger.
EMAPeriod = periode EMA.

Catatan:
Jika UseEMAFilter = true, trigger yang lolos dianggap Trend di info EMA.
Jika ingin riset trigger reversal/berlawanan EMA, UseEMAFilter bisa dibuat false, lalu RequireTrend tiap TF diatur di OP CUSTOM FILTER.

=== TRADE ===
EnableTrade = ON/OFF trading.
LotSize = lot.
MagicNumber = magic EA.
MaxSpreadPoints = batas spread.
OnePositionPerSymbol = satu posisi per symbol.
SlippagePoints = deviation/slippage.
OneTradePerStrongSetup = satu OP per setup strong.
RequireOriginalStrongStatus = hanya OP saat STRONG asli.

====================================================================
8. OP CUSTOM FILTER - H1
====================================================================

Input:
OP_H1_UseMarubozu
OP_H1_UsePinbar
OP_H1_UseEngulfing
OP_H1_UseICT
OP_H1_UseDominanBreak
OP_H1_RequireTrend
OP_H1_MaxAge

Fungsi:
1. H1 wajib punya arah BUY/SELL.
2. Source trigger H1 harus termasuk yang diizinkan.
3. Age H1 tidak boleh lebih tua dari OP_H1_MaxAge.
4. Jika OP_H1_RequireTrend = true, EMA relation H1 harus Trend.
5. Arah OP selalu mengikuti arah H1.

OP_H1_MaxAge:
TFM_AGE_N berarti age 0 / trigger terbaru.
TFM_AGE_1 berarti maksimal 1 candle.
TFM_AGE_2 berarti maksimal 2 candle.
Dan seterusnya sampai TFM_AGE_15.

====================================================================
9. OP CUSTOM FILTER - M15
====================================================================

Input:
OP_M15_MustSameAsH1
OP_M15_UseMarubozu
OP_M15_UsePinbar
OP_M15_UseEngulfing
OP_M15_UseICT
OP_M15_UseDominanBreak
OP_M15_RequireTrend
OP_M15_MaxAge

Fungsi:
1. Jika OP_M15_MustSameAsH1 = true, M15 harus searah H1.
2. Source trigger M15 harus termasuk yang diizinkan.
3. Age M15 tidak boleh lebih tua dari OP_M15_MaxAge.
4. Jika OP_M15_RequireTrend = true, EMA relation M15 harus Trend.

====================================================================
10. OP CUSTOM FILTER - M5
====================================================================

Input:
OP_UseM5Filter
OP_M5_MustSameAsH1
OP_M5_UseMarubozu
OP_M5_UsePinbar
OP_M5_UseEngulfing
OP_M5_UseICT
OP_M5_UseDominanBreak
OP_M5_RequireTrend
OP_M5_MaxAge

Fungsi:
1. Jika OP_UseM5Filter = false, M5 hanya dicatat tetapi tidak menjadi syarat OP.
2. Jika OP_UseM5Filter = true, M5 harus lolos source, age, dan trend sesuai input.
3. Jika OP_M5_MustSameAsH1 = true, M5 harus searah H1.
4. Jika OP_M5_MustSameAsH1 = false, arah M5 bebas, tetapi arah OP tetap ikut H1.

====================================================================
11. LOGIKA SL DAN TP
====================================================================

Input:
OP_StopLossPercent
OP_TakeProfitPercent

SL dihitung dari candle trigger H1 C1.
TP dihitung dari jarak aktual OP ke SL.

Untuk BUY:
RiskRange H1 = H1 Close C1 - H1 Low C1
Close H1 C1 = 0%
Low H1 C1 = 100%
SL 100% = di Low H1 C1
SL 110% = sedikit di bawah Low H1 C1
SL 50% = setengah jarak Close ke Low

Untuk SELL:
RiskRange H1 = H1 High C1 - H1 Close C1
Close H1 C1 = 0%
High H1 C1 = 100%
SL 100% = di High H1 C1
SL 110% = sedikit di atas High H1 C1
SL 50% = setengah jarak Close ke High

TP:
TPPercent memakai basis jarak OP ke SL.
Jika OP ke SL = 100 point:
OP_TakeProfitPercent 100 = TP 100 point = RR 1:1
OP_TakeProfitPercent 150 = TP 150 point = RR 1:1.5
OP_TakeProfitPercent 50 = TP 50 point = RR 1:0.5

Catatan penting:
SLPercent adalah persen dari candle H1 C1.
TPPercent adalah persen dari jarak OP ke SL.

====================================================================
12. OP LEVEL FILTER DAN OP LEVEL PERCENT
====================================================================

Input:
UseOPLevelFilter
MinOPLevelPercent
MaxOPLevelPercent

Default:
UseOPLevelFilter = false
MinOPLevelPercent = 0.0
MaxOPLevelPercent = 100.0

Tujuan:
Mengetahui entry/OP aktual berada di level berapa dari range risk candle trigger H1 C1.
Ini dipakai untuk membaca apakah OP masih sehat atau sudah basi.

Untuk BUY:
Close H1 C1 = 0%
Low H1 C1 = 100%

Rumus BUY:
EntryLevelPercent = (H1Close - EntryPrice) / (H1Close - H1Low) * 100

Contoh BUY:
H1 Close = 4100
H1 Low = 4090
RiskRange = 10
Entry = 4098
EntryLevelPercent = 20%
Artinya OP masih dekat close C1, masih sehat.

Entry = 4092
EntryLevelPercent = 80%
Artinya OP sudah dekat low/ekor, cenderung basi.

Untuk SELL:
Close H1 C1 = 0%
High H1 C1 = 100%

Rumus SELL:
EntryLevelPercent = (EntryPrice - H1Close) / (H1High - H1Close) * 100

Contoh SELL:
H1 Close = 4100
H1 High = 4110
RiskRange = 10
Entry = 4102
EntryLevelPercent = 20%
Masih sehat.

Entry = 4108
EntryLevelPercent = 80%
Dekat high/ekor, cenderung basi.

Jika UseOPLevelFilter = false:
EntryLevelPercent hanya dicatat di CSV, tidak memblokir OP.

Jika UseOPLevelFilter = true:
EA akan skip jika EntryLevelPercent di bawah MinOPLevelPercent atau di atas MaxOPLevelPercent.

Reason skip:
OP_LEVEL_SETTING_INVALID
OP_LEVEL_BELOW_MIN
OP_LEVEL_ABOVE_MAX

Saran riset awal:
Biarkan UseOPLevelFilter = false sampai data CSV cukup.

====================================================================
13. MFE PERCENT RESEARCH
====================================================================

Input:
EnableMFEPercentResearch
StudyTP1Percent
StudyTP2Percent
StudyTP3Percent
StudyTP4Percent
StudyTP5Percent
StudySL1Percent
StudySL2Percent
StudySL3Percent
StudySL4Percent
StudySL5Percent

Default:
EnableMFEPercentResearch = true
StudyTP = 50, 75, 100, 125, 150
StudySL = 30, 50, 75, 100, 130

Tujuan MFE:
Mencari TP dan SL ideal dari data, bukan dari tebakan.

Data utama yang dicatat:
MaxFloatingPlusPoints = floating profit terbaik selama posisi hidup.
MaxFloatingMinusPoints = floating minus terburuk selama posisi hidup.
MaxProfitPrice = harga saat profit terbaik.
MaxLossPrice = harga saat loss terdalam.

Percent yang dihitung:
MaxProfitToH1RangePercent = MaxProfitPoints dibanding risk range H1 C1.
MaxLossToH1RangePercent = MaxLossPoints dibanding risk range H1 C1.
MaxProfitToSLPercent = MaxProfitPoints dibanding jarak OP ke SL.
MaxLossToSLPercent = MaxLossPoints dibanding jarak OP ke SL.
MaxProfitToTPPercent = MaxProfitPoints dibanding jarak OP ke TP.
MaxLossToTPPercent = MaxLossPoints dibanding jarak OP ke TP.

Initial values:
InitialRiskPoints = sama dengan initial SL distance.
InitialSLDistancePoints = jarak OP ke SL.
InitialTPDistancePoints = jarak OP ke TP.
InitialSLToH1RangePercent = initial SL distance dibanding risk range H1.
InitialTPToH1RangePercent = initial TP distance dibanding risk range H1.

Study TP:
StudyTP memakai basis jarak OP ke SL.
Jika StudyTP3Percent = 100, maka hit = 1 jika MaxProfitToSLPercent >= 100.
Artinya harga pernah bergerak profit sebesar 1x risk OP-SL.

Study SL:
StudySL memakai basis risk range H1 C1.
Jika StudySL2Percent = 50, maka hit = 1 jika MaxLossToH1RangePercent >= 50.
Artinya floating minus pernah mencapai 50% dari range risk H1 C1.

Catatan:
StudyTP/StudySL tidak mengubah TP/SL real.
Ini hanya data CSV.

====================================================================
14. CARA MEMBACA DATA MFE UNTUK SETTING
====================================================================

Untuk mencari TP ideal:
Lihat StudyTPHit.
Jika banyak trade StudyTP1Hit = 1 tapi StudyTP3Hit = 0, berarti TP 50% sering tercapai tetapi TP 100% terlalu jauh.
Jika StudyTP3Hit sering 1, maka TP 100% / RR 1:1 cukup realistis.
Jika StudyTP5Hit sering 1, maka TP 150% / RR 1:1.5 bisa dipertimbangkan.

Untuk mencari SL ideal:
Lihat StudySLHit dan MaxLossToH1RangePercent.
Jika banyak trade profit tapi StudySL1Hit = 1, berarti trade sering floating minus minimal 30% dulu.
Jika trade profit sering menyentuh StudySL2Hit = 1, maka SL 50% mungkin terlalu sempit.
Jika trade profit jarang menyentuh StudySL2Hit, maka SL 50% mungkin cukup.

Untuk membaca OP basi:
Lihat EntryLevelPercent.
0-25% = dekat close H1, sehat.
25-50% = masih wajar.
50-75% = mulai telat.
75-100% = dekat ekor, potensi basi.
>100% = harga sudah melewati area low/high trigger, perlu perhatian khusus.

Saran:
Awal test jangan aktifkan UseOPLevelFilter dulu.
Kumpulkan data.
Setelah terlihat OP di atas misalnya 70% jelek, baru set:
UseOPLevelFilter = true
MaxOPLevelPercent = 70

====================================================================
15. CSV RESEARCH LOG
====================================================================

Input:
EnableCSVLog
LogFileName

Default file:
TF_Monitor_EA_Research_MFE_Percent.csv

Lokasi:
FILE_COMMON MetaTrader 5.

Event yang ditulis:
SIGNAL = status STRONG terdeteksi.
OP_CHECK PASS = semua filter OP lolos dan plan siap.
OP_CHECK BLOCK = setup diblok oleh filter/reason.
ENTRY = order berhasil atau gagal.
CLOSE = posisi close.

Kolom CSV:
1 LogDate
2 LogTime
3 Event
4 Decision
5 Reason
6 Symbol
7 MagicNumber
8 Status
9 Direction
10 H1SignalTime
11 M15SignalTime
12 M5SignalTime
13 EntryTime
14 ExitTime
15 EntryHour
16 DayOfWeek
17 Session
18 H1Age
19 M15Age
20 M5Age
21 H1Source
22 M15Source
23 M5Source
24 H1EMA
25 M15EMA
26 M5EMA
27 H1_Open
28 H1_High
29 H1_Low
30 H1_Close
31 H1_RiskRangePoints
32 H1_RangePoints
33 EntryPrice
34 EntryLevelPercent
35 SLPercent
36 SLPrice
37 TPPercent
38 TPPrice
39 SpreadPoints
40 Ask
41 Bid
42 Lot
43 Ticket
44 Result
45 ExitPrice
46 ProfitPoint
47 ProfitUSD
48 MaxFloatingMinusPoints
49 MaxFloatingPlusPoints
50 TimeToResultMinutes
51 Notes
52 InitialRiskPoints
53 InitialSLDistancePoints
54 InitialTPDistancePoints
55 InitialSLToH1RangePercent
56 InitialTPToH1RangePercent
57 MaxProfitPrice
58 MaxLossPrice
59 MaxProfitPoints
60 MaxLossPoints
61 MaxProfitToH1RangePercent
62 MaxLossToH1RangePercent
63 MaxProfitToSLPercent
64 MaxLossToSLPercent
65 MaxProfitToTPPercent
66 MaxLossToTPPercent
67 StudyTP1Percent
68 StudyTP1Hit
69 StudyTP2Percent
70 StudyTP2Hit
71 StudyTP3Percent
72 StudyTP3Hit
73 StudyTP4Percent
74 StudyTP4Hit
75 StudyTP5Percent
76 StudyTP5Hit
77 StudySL1Percent
78 StudySL1Hit
79 StudySL2Percent
80 StudySL2Hit
81 StudySL3Percent
82 StudySL3Hit
83 StudySL4Percent
84 StudySL4Hit
85 StudySL5Percent
86 StudySL5Hit

Struktur kolom sudah dibuat 86 header dan 86 data per baris.

Catatan penting:
Jika file CSV lama dengan nama yang sama sudah pernah dibuat sebelum update header, hapus dulu atau ubah LogFileName agar header tidak campur.

====================================================================
16. NOTIFIKASI DAN EXPERTS LOG
====================================================================

Notification.mqh tidak diubah dari versi 03072026.

Jenis pesan:

1. SIGNAL
Format dasar:
TF Monitor EA | SIGNAL | STRONG | ... | H1 ... | M15 ... | M5 ... | Symbol

2. OP BLOCK
Hanya ke Experts jika PrintOPBlockToExperts = true.
Format dasar:
TF Monitor EA | OP BLOCK | Reason | ... | H1 ... | M15 ... | M5 ... | Symbol

3. OP PLAN
Ke Experts.
Menampilkan arah, symbol, R, OP, SL, TP, Loss percent/USD, Profit percent/USD.

4. TRADE OPEN
Ke Experts dan push jika NotifyTrade dan NotifyTradeOpen true.
Menampilkan arah, symbol, R, OP, SL, TP, Loss, Profit, Lot, status.

5. TRADE FAILED
Ke Experts dan push jika NotifyTrade dan NotifyTradeFailed true.

6. CLOSE RESULT
Ke Experts dan push jika NotifyTrade dan NotifyTradeClose true.
Menampilkan result, arah, symbol, OP, Exit, Profit/Loss USD, point.

MFE tidak dimasukkan ke notifikasi supaya notifikasi tetap ringkas dan tidak berubah.
MFE ditulis ke CSV.

====================================================================
17. ALUR ENTRY DETAIL
====================================================================

TFM_ProcessEALogic:
1. Update floating stats.
2. Cek delay first load.
3. Cek data ready.
4. Update semua state H1/M15/M5.
5. Hitung eventKey, statusText, snapshot.
6. Proses snapshot dan signal.
7. Jika firstSnapshot dan TradeOnFirstLoad = false, EA tidak OP langsung.
8. Panggil TFM_TryOpenTrade(statusText).

TFM_TryOpenTrade:
1. Cek status gate.
   Jika RequireOriginalStrongStatus = true dan status bukan STRONG, stop.
2. Cek OPFilter H1/M15/M5.
3. Buat entryKey.
4. Cek EnableTrade, posisi open, spread, hour filter.
5. FillTradePlan.
6. Cek OPLevelFilter jika aktif.
7. Print OP PLAN.
8. Log OP_CHECK PASS.
9. Kirim order Buy/Sell.
10. Jika gagal, log ENTRY SKIP dan notif trade failed.
11. Jika berhasil, cari actual position ticket.
12. Ambil actual entry price dari broker.
13. Recalculate EntryLevelPercent dari actual entry.
14. Recalculate TP dari actual entry ke SL.
15. Modify TP jika perlu.
16. Set context active.
17. Init MFE tracking.
18. Log ENTRY ORDER_OPENED.
19. Kirim trade open notification.
20. Gambar entry marker.

====================================================================
18. ALUR CLOSE DETAIL
====================================================================

TFM_ProcessClosedDeal:
1. Cek deal ticket valid.
2. Cek symbol sesuai.
3. Cek magic sesuai.
4. Cek entry type DEAL_ENTRY_OUT atau DEAL_ENTRY_INOUT.
5. Ambil exit price, profit, swap, commission, deal time, deal reason.
6. Hitung profitPoint dari entry ke exit.
7. Update MFE final jika exit lebih besar/kecil dari max sebelumnya.
8. Log CLOSE ke CSV.
9. Kirim close notification.
10. Draw result marker.
11. Set current trade inactive.

====================================================================
19. REASON OP BLOCK / SKIP YANG PENTING
====================================================================

Status:
STATUS_NOT_STRONG

OP Filter:
H1_DIRECTION_INVALID
H1_NO_DIRECTION
H1_NO_TIME
H1_TRIGGER_NOT_ALLOWED
H1_AGE_TOO_OLD
H1_EMA_NOT_TREND
M15_NOT_SAME_H1
M15_TRIGGER_NOT_ALLOWED
M15_AGE_TOO_OLD
M15_EMA_NOT_TREND
M5_NOT_SAME_H1
M5_TRIGGER_NOT_ALLOWED
M5_AGE_TOO_OLD
M5_EMA_NOT_TREND

Trade guard:
TRADE_DISABLED
HAS_OPEN_POSITION
SPREAD_FILTER
HOUR_FILTER

Trade plan:
H1_OHLC_INVALID
DIRECTION_INVALID
SL_PERCENT_INVALID
TP_PERCENT_INVALID
BUY_RISK_RANGE_INVALID
SELL_RISK_RANGE_INVALID
BUY_RISK_INVALID
SELL_RISK_INVALID
BUY_SL_NOT_BELOW_OP
SELL_SL_NOT_ABOVE_OP
BUY_TP_NOT_ABOVE_OP
SELL_TP_NOT_BELOW_OP
BUY_SL_TOO_CLOSE
SELL_SL_TOO_CLOSE
BUY_TP_TOO_CLOSE
SELL_TP_TOO_CLOSE
PLAN_PRICE_INVALID

OP Level:
OP_LEVEL_SETTING_INVALID
OP_LEVEL_BELOW_MIN
OP_LEVEL_ABOVE_MAX

Order:
ORDER_FAIL_xxx
ORDER_OPENED
POSITION_CLOSED

====================================================================
20. SETTING DEFAULT YANG DISARANKAN UNTUK RISET AWAL
====================================================================

RequireOriginalStrongStatus = true
OneTradePerStrongSetup = true

OP_H1_MaxAge = TFM_AGE_N
OP_M15_MaxAge = TFM_AGE_1 atau TFM_AGE_2
OP_UseM5Filter = true
OP_M5_MustSameAsH1 = true atau false sesuai test
OP_M5_RequireTrend = false untuk tidak terlalu ketat
OP_M5_MaxAge = TFM_AGE_N atau TFM_AGE_4 sesuai gaya entry

OP_StopLossPercent = 110
OP_TakeProfitPercent = 100

UseOPLevelFilter = false dulu
MinOPLevelPercent = 0
MaxOPLevelPercent = 100

EnableMFEPercentResearch = true
StudyTP = 50, 75, 100, 125, 150
StudySL = 30, 50, 75, 100, 130

Tujuan test awal:
Kumpulkan CSV dulu untuk membaca:
1. Strong setup mana yang sehat.
2. OP masuk di level berapa.
3. TP 50/75/100/125/150 mana yang sering tercapai.
4. SL 30/50/75/100/130 mana yang terlalu sempit atau aman.
5. Apakah M5 filter membantu atau membuat entry telat.

====================================================================
21. CARA TUNING SEPERTI EQUALIZER
====================================================================

Langkah tuning:

1. Mulai dari filter STRONG saja.
   RequireOriginalStrongStatus = true.

2. Jangan aktifkan OPLevelFilter dulu.
   UseOPLevelFilter = false.

3. Kumpulkan CSV minimal beberapa puluh trade.

4. Baca EntryLevelPercent.
   Jika trade jelek banyak di EntryLevelPercent > 70, coba MaxOPLevelPercent = 70.

5. Baca StudyTPHit.
   Jika TP 100 jarang hit tapi TP 75 sering hit, pertimbangkan OP_TakeProfitPercent = 75.

6. Baca StudySLHit.
   Jika trade profit sering floating minus sampai 50% H1, SL 50 terlalu sempit.
   Jika trade loss langsung minus 100% dan profit kecil, setup/filter perlu diperketat.

7. Uji perubahan satu-satu.
   Jangan mengubah banyak input sekaligus supaya tahu efeknya.

8. Setelah STRONG stabil, baru buat blok status lain seperti RETRACE STRONG.

====================================================================
22. CATATAN KHUSUS TENTANG ACTUAL ENTRY
====================================================================

TradePlan awal memakai Ask untuk BUY dan Bid untuk SELL.
Setelah order berhasil, EA membaca actual entry dari broker:
PositionGetDouble(POSITION_PRICE_OPEN)

Setelah actual entry terbaca:
1. EntryPrice disesuaikan ke harga aktual.
2. EntryLevelPercent dihitung ulang dari actual entry.
3. TP dihitung ulang dari actual entry ke SL.
4. EA mencoba PositionModify untuk update TP.

Tujuannya:
Data CSV EntryLevelPercent dan MFE memakai entry aktual, bukan hanya rencana entry.

====================================================================
23. YANG BELUM ADA / RENCANA MASA DEPAN
====================================================================

Belum ada:
1. Blok input khusus VALID.
2. Blok input khusus RETRACE STRONG.
3. Blok input khusus RETRACE VALID.
4. Filter otomatis berdasarkan StudyTP/StudySL.
5. Breakeven / trailing berdasarkan MFE.
6. Partial close.
7. Summary statistik otomatis dari CSV.

Rencana masa depan yang aman:
1. Setelah data STRONG cukup, buat status filter terpisah untuk RETRACE STRONG.
2. Copy konsep OP CUSTOM FILTER H1/M15/M5 tetapi dengan prefix RETRACE_STRONG.
3. Jangan memakai satu blok untuk semua status karena nanti data riset tercampur.
4. Tambahkan input filter hanya jika default OFF.

====================================================================
24. CHECKLIST SEBELUM REVISI BERIKUTNYA
====================================================================

Sebelum mengirim revisi kode berikutnya, wajib cek:

1. Notification.mqh apakah berubah tanpa permintaan? Jika berubah, batalkan.
2. OPFilter.mqh apakah berubah tanpa permintaan? Jika berubah, batalkan.
3. BiasLogic.mqh apakah berubah tanpa permintaan? Jika berubah, batalkan.
4. TriggerLogic.mqh apakah berubah tanpa permintaan? Jika berubah, batalkan.
5. Header CSV dan data line jumlah kolomnya sama.
6. Input baru default tidak mengubah behavior lama.
7. MFE tidak dipakai sebagai syarat entry kecuali user minta.
8. OPLevelFilter default tetap false.
9. TP tetap dihitung dari OP ke SL.
10. SL tetap dihitung dari H1 C1 directional risk range.
11. Actual entry dari broker tetap dipakai untuk MFE dan EntryLevelPercent.

====================================================================
25. RINGKASAN KONSEP INTI
====================================================================

Arah OP:
Ikut H1.

Status OP saat ini:
Fokus STRONG.

Filter OP:
H1/M15/M5 memakai OP CUSTOM FILTER.

SL:
Persen dari candle trigger H1 C1.
BUY: Close ke Low.
SELL: Close ke High.

TP:
Persen dari jarak OP ke SL.
100% = RR 1:1.
150% = RR 1:1.5.

OPLevelPercent:
Mengukur entry masuk di level berapa dari range H1 C1.
0% dekat close.
100% dekat low/high trigger.

MFE:
Mengukur floating terbaik dan terburuk selama trade.
Dipakai untuk menentukan TP/SL ideal dari CSV.

CSV:
Tempat utama riset.
Bukan notifikasi.

Notifikasi:
Tetap ringkas dan tidak diubah.

====================================================================
END OF BLUEPRINT
====================================================================
