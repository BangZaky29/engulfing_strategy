====================================================================
BLUEPRINT LENGKAP - MultiPatternScanner (Indikator MT5)
Versi dokumen ini mengacu ke: MultiPatternScanner v2.19
====================================================================

DAFTAR ISI
1. Ringkasan & Tujuan
2. Struktur File / Arsitektur
3. Alur Kerja Utama (OnInit, OnTimer, OnCalculate)
4. Mesin Scan (Scanner.mqh) - Detail Lengkap
5. Semua Input/Pengaturan (per grup)
6. Semua Pattern - Aturan Deteksi Lengkap
   5.1 Engulfing
   5.2 ICT
   5.3 Marobozu
   5.4 Same Candle
7. Sistem Dedup Sinyal (anti notif dobel)
8. Filter EMA
9. Mekanisme "Warmup" / Tunggu History Stabil
10. Guard Notifikasi Lintas-Instance
11. Format Notifikasi HP
12. Sistem Dot di Chart
13. Variable Global (state) - Daftar Lengkap
14. Cara Menambah Pattern Baru
15. Riwayat Versi (Changelog Ringkas)
16. Batasan & Catatan Penting

====================================================================
1. RINGKASAN & TUJUAN
====================================================================

MultiPatternScanner adalah indikator MetaTrader 5 (MQL5) yang:
- Memindai beberapa timeframe sekaligus (M5/M15/M30/H1/H4/D1, bisa
  dipilih mana yang aktif).
- Mendeteksi beberapa pola candle sekaligus (Engulfing, ICT,
  Marobozu, Same Candle - bisa ditambah pattern baru tanpa mengubah
  file lain).
- Menandai sinyal dengan dot berwarna di chart (opsional, bisa
  dimatikan tanpa mematikan notifikasi).
- Mengirim push notification ke HP (MetaQuotes ID) setiap ada
  sinyal baru, dengan prinsip "1 trigger = 1 info" (tidak boleh
  dobel/berulang untuk candle yang sama).
- Punya filter EMA opsional yang berlaku global (kecuali pattern
  yang sengaja dikecualikan, misal Same Candle).

Prinsip desain penting yang disepakati selama pengembangan:
- Setiap pattern berdiri sendiri di file-nya masing-masing -
  mengubah 1 pattern TIDAK mempengaruhi pattern lain.
- "1 trigger = 1 notifikasi" adalah aturan paling penting - semua
  mekanisme dedup, guard lintas-instance, dan warmup history dibuat
  khusus untuk menjaga aturan ini.
- Tampilan dot di chart dan pengiriman notifikasi ke HP adalah 2 hal
  yang independen (bisa dot mati tapi notif tetap jalan).

====================================================================
2. STRUKTUR FILE / ARSITEKTUR
====================================================================

MultiPatternScanner.mq5              <- file utama, HANYA "wiring"
  (tidak berisi logika pattern, cuma daftar include + event handler
  OnInit/OnDeinit/OnTimer/OnCalculate + registry pattern)

Include/MultiPatternScanner/
  Settings.mqh        -> semua input UMUM (bukan spesifik 1 pattern):
                          jumlah history, on/off notif, on/off dot,
                          ukuran/jarak dot, interval scan, timeframe
                          yang dipindai, filter EMA global.
  PatternBase.mqh      -> class dasar CPatternDetector - JANGAN diubah
                          kecuali memang mau mengubah struktur dasar
                          SEMUA pattern sekaligus.
  Globals.mqh          -> semua variable & struct global yang dipakai
                          bersama modul lain (state runtime).
  Patterns/
    Engulfing.mqh      -> pattern Engulfing (class CEngulfing)
    ICT.mqh            -> pattern ICT sweep+rejection (class CICT)
    Marobozu.mqh       -> pattern Marobozu (class CMarobozu)
    SameCandle.mqh     -> pattern Same Candle (class CSameCandle)
  EmaFilter.mqh         -> semua logika filter EMA (handle indikator,
                          fungsi ApplyEmaFilter).
  Drawing.mqh           -> semua yang berhubungan dengan gambar dot di
                          chart (CreateSignalDot, mapping ke
                          OBJPROP_TIMEFRAMES).
  Utils.mqh             -> helper: daftar timeframe aktif, dedup
                          sinyal (numerik + binary search), guard
                          notifikasi lintas-instance, pruning data
                          lama.
  Scanner.mqh           -> MESIN SCAN UTAMA: loop semua TF x semua
                          pattern, terapkan dedup + filter EMA,
                          gambar dot, gabungkan & kirim notifikasi.

Alasan modular seperti ini: menambah pattern baru cukup 1 file baru
di folder Patterns/ + 1 baris #include + 1 baris registrasi di
InitDetectors() - tidak perlu sentuh file lain sama sekali.

====================================================================
3. ALUR KERJA UTAMA
====================================================================

OnInit()
  1. Cek apakah ini reload karena ganti timeframe chart saja (bukan
     ganti symbol/parameter) - kalau ya, dot yang sudah ada TIDAK
     dihapus (dot nempel ke waktu+harga chart, bukan ke timeframe).
     Kalau bukan (symbol beda / parameter berubah), semua object
     "MPS_*" dihapus dan g_seenKeys direset total.
  2. ValidateSettings() - clamp InpDotSize (1-5) dan InpEMAPeriod
     (>=1) ke rentang wajar.
  3. BuildTimeframeList() - bangun g_timeframes[] dari
     InpUseM5/M15/M30/H1/H4/D1, reset g_lastBarsSeen ke -1 (paksa
     full rescan pertama jalan).
  4. InitDetectors() - buat instance semua pattern yang terdaftar.
  5. InitEmaHandles() - buat handle indikator EMA per timeframe
     (kalau InpEMAFilterOn aktif).
  6. g_initialScanDone = false (SENGAJA, lihat bagian 9 - Warmup).
  7. ScanRange(1, InpHistoryBars, true) - full scan history SEKALI,
     dot digambar seperti biasa tapi NOTIFIKASI TIDAK DIKIRIM (karena
     g_initialScanDone masih false).
  8. EventSetTimer(InpFastScanSec) - mulai timer periodik.

OnTimer() - dipanggil tiap InpFastScanSec detik:
  - Selama g_initialScanDone == false: masih tahap "warmup" (lihat
    bagian 9), scan terus tapi notif tetap tidak aktif, sampai
    history dipastikan stabil.
  - Setelah g_initialScanDone == true:
    - Tiap kelipatan InpFullRescanEvery x InpFastScanSec detik: full
      rescan (ScanRange 1..InpHistoryBars) + PruneSeenKeys() (buang
      entry dedup/klaim lama yang sudah di luar jangkauan).
    - Selain itu: scan cepat (ScanRange 1..5) - cukup untuk menangkap
      candle yang baru saja closed.
  - ChartRedraw() di akhir supaya dot langsung terlihat.

OnDeinit(reason)
  - Simpan reason (dipakai OnInit berikutnya untuk tahu apakah ini
    ganti-timeframe biasa atau reload total).
  - Matikan timer, lepas semua detector & handle EMA.
  - Kalau reason == REASON_REMOVE (indikator benar-benar dicabut dari
    chart oleh user), semua dot "MPS_*" dihapus.

OnCalculate()
  - Tidak dipakai untuk logika (indikator ini murni event-driven lewat
    OnTimer, bukan re-render tiap tick) - cuma return rates_total.

====================================================================
4. MESIN SCAN (Scanner.mqh) - DETAIL LENGKAP
====================================================================

ScanRange(shiftFrom, shiftTo, isFullRescan):
  Untuk setiap timeframe aktif (g_timeframes[]):
    - Skip kalau jumlah bar timeframe itu belum cukup
      (bars < shiftTo + 2).
    - Kalau isFullRescan=true DAN jumlah bar timeframe ini SAMA PERSIS
      dengan hasil rescan terakhir (g_lastBarsSeen), skip total -
      hasil pasti sama karena pattern cuma pakai candle yang sudah
      closed (tidak repaint). Ini optimasi performa utama untuk
      pemakaian jangka panjang.
    - Untuk setiap shift dari shiftFrom..shiftTo (1 shift = 1 candle):
        a. Kumpulkan SEMUA pattern yang trigger di candle (tf, shift)
           ini dulu (firedNames[], firedDirs[]) SEBELUM kirim
           notifikasi apa pun - supaya kalau >1 pattern nyala
           bareng di arah yang sama, jadi 1 notifikasi gabungan
           "Multi Trigger", bukan dikirim terpisah per pattern.
        b. Untuk tiap detector aktif:
           - Panggil Check(symbol, tf, shift, detail) -> dir
             (1=Buy, -1=Sell, 0=tidak ada sinyal).
           - Kalau dir==0, lanjut ke detector berikutnya.
           - Dedup DULU (SeenKeyCheckAndAdd) - kalau kombinasi
             (candle+tf+index pattern+arah) ini SUDAH PERNAH diproses
             sebelumnya, skip (tidak digambar dot lagi, tidak
             dihitung notif lagi). Urutan ini SENGAJA sebelum filter
             EMA (lihat bagian 7).
           - Filter EMA (ApplyEmaFilter) - DILEWATI SAMA SEKALI kalau
             detector punya m_skipEmaFilter=true (Same Candle).
           - Kalau InpShowDot=true: gambar dot (lihat bagian 12).
           - Simpan nama+arah ke firedNames[]/firedDirs[].
        c. Kalau ada yang fired (firedCount>0) DAN InpNotifyOn=true
           DAN g_initialScanDone=true: panggil NotifyFiredPatterns()
           untuk kirim notifikasi HP (bisa digabung jadi 1 pesan per
           arah, lihat bagian 11).
    - Kalau isFullRescan: catat jumlah bar timeframe ini ke
      g_lastBarsSeen[] (dipakai optimasi skip di atas & dipakai
      warmup untuk deteksi "history masih nambah atau tidak").

Catatan performa: shift dimulai dari 1 (bukan 0) karena candle di
shift=0 masih "berjalan"/belum closed - semua pattern sengaja hanya
mengevaluasi candle yang sudah pasti closed supaya tidak repaint.

====================================================================
5. SEMUA INPUT / PENGATURAN
====================================================================

=== PENGATURAN UMUM (Settings.mqh) ===
InpHistoryBars      (default 500)  - jumlah bar history yang dipindai
                                     per timeframe. Dipakai sebagai
                                     batas atas shift di ScanRange &
                                     acuan cutoff pruning dedup.
InpNotifyOn         (default true) - master on/off kirim push
                                     notification ke HP.
InpShowDot          (default true) - on/off TAMPILAN dot di chart.
                                     false = chart kosong sama sekali,
                                     TAPI notifikasi HP tetap jalan
                                     normal (2 hal independen).
InpDotSize          (default 2)    - ukuran dot, di-clamp 1-5.
InpDotDistance      (default 0.3)  - jarak dot dari candle, relatif
                                     terhadap tinggi candle (High-Low)
                                     candle itu sendiri. 0.1=dekat,
                                     1.0=jauh.
InpFastScanSec      (default 5)    - interval scan cepat (detik) yang
                                     menangkap candle baru closed.
InpFullRescanEvery  (default 60)   - full rescan history dijalankan
                                     tiap N x InpFastScanSec detik
                                     (default 60x5=300 detik/5 menit).

=== TIMEFRAME YANG DI-SCAN (Settings.mqh) ===
InpUseM5   (default true)
InpUseM15  (default false)
InpUseM30  (default true)
InpUseH1   (default true)
InpUseH4   (default true)
InpUseD1   (default true)

=== FILTER EMA - GLOBAL (Settings.mqh) ===
InpEMAFilterOn (default false)      - master on/off filter EMA.
InpEMAPeriod   (default 20)         - periode EMA, di-clamp >=1.
InpEMAMethod   (default MODE_EMA)   - metode MA.
InpEMAPrice    (default PRICE_CLOSE)- harga yang dipakai EMA.
Aturan: BUY valid jika Close candle sinyal > EMA; SELL valid jika
Close candle sinyal < EMA. Berlaku untuk Engulfing, ICT, dan Marobozu
(TIDAK berlaku untuk Same Candle - lihat bagian 5.4).

=== ENGULFING (Patterns/Engulfing.mqh) ===
InpEngulfingOn        (default true)
InpEngulfingColor     (default clrRed)
InpEngulfingMinRange  (default 300.0) - range minimal (poin)
InpEngulfingMaxRange  (default 800.0) - range maksimal (poin)
InpEngulfingMinBodyPct(default 40.0)  - body minimal (%)
InpEngulfingMaxBodyPct(default 100.0) - body maksimal (%)

=== ICT (Patterns/ICT.mqh) ===
InpICTOn                (default true)
InpICTColor             (default clrYellow)
InpICTSweepLookbackBars (default 5)     - N candle ke belakang untuk
                                          cari swing low/high
InpICTMinRange   (default 300.0) - range minimal (poin)
InpICTMaxRange   (default 800.0) - range maksimal (poin)
InpICTMinBodyPct (default 40.0)  - body minimal (%)
InpICTMaxBodyPct (default 100.0) - body maksimal (%)

=== MAROBOZU (Patterns/Marobozu.mqh) - setting berdiri sendiri ===
InpMarobozuOn               (default true)
InpMarobozuColor            (default clrLime)
InpMarobozuLookbackBars     (default 10)  - jumlah candle sebelumnya
                                           untuk pembanding rata-rata
                                           range.
InpMarobozuRangeMultiplier  (default 1.5) - range candle sinyal harus
                                           >= X kali rata-rata range N
                                           candle sebelumnya.
InpMarobozuMinBodyPct       (default 90.0)- body minimal (%) dari
                                           High-Low candle sinyal.
Catatan: SENGAJA TIDAK ada filter poin absolut (Min/MaxRange) seperti
Engulfing/ICT - Marobozu butuh "candle besar RELATIF terhadap kondisi
market saat ini", bukan ambang poin tetap.

=== SAME CANDLE (Patterns/SameCandle.mqh) - setting paling minimal ===
InpSameCandleOn    (default true)
InpSameCandleColor (default clrOrange)
InpSameCandleMin   (default 3) - minimal jumlah candle berturut-turut
                                 warna sama supaya dianggap sinyal.
Catatan: TIDAK ADA input filter lain (tidak ada body%, tidak ada
range/ketinggian) - sengaja, sesuai desain (lihat bagian 5.4).

====================================================================
6. SEMUA PATTERN - ATURAN DETEKSI LENGKAP
====================================================================

--------------------------------------------------------------------
6.1 ENGULFING (CEngulfing, file Patterns/Engulfing.mqh)
--------------------------------------------------------------------
Disamakan persis dengan EA RCS (RCS_IsBullishEngulfing /
RCS_IsBearishEngulfing).

C1 = candle di shift (candle sinyal, sudah closed)
C2 = candle di shift+1 (candle sebelumnya)

BUY  jika: C2 bearish, C1 bullish, DAN Close(C1) >= High(C2)
           (C1 harus "menelan" seluruh candle C2 termasuk ekornya,
           bukan cuma body-nya).
SELL jika: C2 bullish, C1 bearish, DAN Close(C1) <= Low(C2)

Lalu difilter oleh:
  riskRange   = Buy: Close(C1)-Low(C1) ; Sell: High(C1)-Close(C1)
  rangePoints = riskRange / point simbol
  bodyPct     = |Close(C1)-Open(C1)| / (High(C1)-Low(C1)) * 100
  Ditolak kalau rangePoints di luar [InpEngulfingMinRange,
  InpEngulfingMaxRange] ATAU bodyPct di luar [InpEngulfingMinBodyPct,
  InpEngulfingMaxBodyPct].

Ikut filter EMA global (tidak set m_skipEmaFilter).
Dot: normal, 1 dot per sinyal, tidak ada mekanisme dotFollowsLatest.

--------------------------------------------------------------------
6.2 ICT (CICT, file Patterns/ICT.mqh)
--------------------------------------------------------------------
Disamakan persis dengan EA RCS (RCS_IsBullishICT/RCS_IsBearishICT) -
liquidity sweep + rejection.

BUY jika:
  - C2 bearish, C1 bullish
  - Low(C1) menembus ke bawah swing-low dari InpICTSweepLookbackBars
    candle sebelumnya (candle shift+1 s.d. shift+lookback) -> "sweep"
  - LALU Close(C1) > High(C2) -> "rejection" (ditolak balik ke atas)

SELL jika:
  - C2 bullish, C1 bearish
  - High(C1) menembus ke atas swing-high dari N candle sebelumnya
  - LALU Close(C1) < Low(C2) -> rejection ke bawah

Filter range & body: rumus SAMA PERSIS dengan Engulfing (riskRange,
rangePoints, bodyPct) tapi pakai input sendiri (InpICTMinRange,
InpICTMaxRange, InpICTMinBodyPct, InpICTMaxBodyPct - variable
terpisah dari Engulfing, walau modelnya sama).

Ikut filter EMA global. Dot: normal (sama seperti Engulfing).

--------------------------------------------------------------------
6.3 MAROBOZU (CMarobozu, file Patterns/Marobozu.mqh)
--------------------------------------------------------------------
Candle body besar & ekor kecil, DAN range-nya jauh lebih besar dari
rata-rata candle sebelumnya (candle breakout/momentum).

C1 = candle di shift. Arah: bull jika Close>Open, bear jika Close<Open
(persis doji ditolak).

Filter 1 - body% (ekor kecil):
  fullRange1 = High(C1)-Low(C1)
  bodyPct    = |Close(C1)-Open(C1)| / fullRange1 * 100
  Ditolak kalau bodyPct < InpMarobozuMinBodyPct (default 90%).

Filter 2 - range relatif terhadap rata-rata N candle sebelumnya:
  riskRange = Buy: Close(C1)-Low(C1) ; Sell: High(C1)-Close(C1)
              (rumus SAMA seperti Engulfing/ICT, dipakai juga untuk
              angka "H xxx" di notifikasi HP)
  avgRange  = rata-rata (High-Low) POLOS dari InpMarobozuLookbackBars
              candle SEBELUMNYA (shift+1 s.d. shift+lookback) - PAKAI
              High-Low PENUH, BUKAN Close-Low/High-Close, karena
              candle-candle sebelumnya arahnya bisa campur naik-turun,
              jadi ukuran "besar-kecil" yang adil ya High-Low penuh
              (kalau dipaksa searah, candle bearish besar bisa
              terhitung kecil gara-gara Close-nya memang dekat Low,
              bikin rata-rata jadi bias/kekecilan).
  Ditolak kalau riskRange < avgRange * InpMarobozuRangeMultiplier
  (default 1.5x).

SENGAJA TIDAK ADA filter poin absolut (beda dari Engulfing/ICT) -
setting Marobozu berdiri sendiri di grup input sendiri.

Ikut filter EMA global (m_skipEmaFilter TIDAK di-set, default false).
Dot: normal, 1 dot per sinyal (tidak dotFollowsLatest).

--------------------------------------------------------------------
6.4 SAME CANDLE (CSameCandle, file Patterns/SameCandle.mqh)
--------------------------------------------------------------------
Menghitung rentetan candle BERTURUT-TURUT warna sama (momentum
beruntun) - pattern paling sederhana, sengaja tanpa filter tambahan
apa pun selain warna.

Constructor set 2 flag khusus:
  m_skipEmaFilter    = true  -> kebal filter EMA global sepenuhnya,
                                apa pun InpEMAFilterOn.
  m_dotFollowsLatest = true  -> dot cuma boleh ADA SATU per rentetan
                                yang masih berjalan (lihat bagian 12).

Aturan Check(symbol, tf, shift, detail):
  1. C1 = candle di shift. Kalau doji (Close==Open persis), return 0
     (rentetan putus total di titik ini, bukan cuma "berhenti
     nambah").
  2. dir = 1 (bull) jika Close>Open, -1 (bear) jika Close<Open.
  3. PENGECEKAN "UJUNG RENTETAN" (fix bug v2.19 - PENTING):
     Kalau shift>1, cek candle SETELAHNYA (shift-1, yaitu candle yang
     LEBIH BARU dan sudah closed). Kalau warnanya SAMA dengan C1,
     berarti candle di 'shift' ini BUKAN ujung/candle terbaru dari
     rentetannya (rentetan itu "milik" shift-1, bukan di sini) ->
     return 0. TANPA cek ini, 1 rentetan panjang (misal 6 candle)
     akan dianggap BEBERAPA sinyal terpisah sekaligus dalam 1x scan
     (lihat bagian 15 - riwayat bug ini).
  4. Hitung mundur (shift+1, shift+2, dst) selama warnanya PERSIS
     sama dengan C1. Doji atau warna lawan memutus hitungan (streak
     berhenti, tidak reset ke pattern lain, cuma berhenti hitung).
  5. Kalau streak < InpSameCandleMin (default 3), return 0.
  6. return dir, dengan detail = angka streak (string), dipakai buat
     notifikasi HP menampilkan "Same Candle 5" dst (bukan cuma "Same
     Candle" polos).

Perilaku penting yang disepakati:
  - TIDAK ADA filter body%/range/ketinggian sama sekali - candle
    sekecil apa pun tetap dihitung asal warna konsisten.
  - TIDAK terpengaruh EMA on/off sama sekali.
  - Begitu rentetan capai minimum, SETIAP candle tambahan yang masih
    meneruskan warna sama tetap dianggap sinyal baru sendiri (jadi
    rentetan 3,4,5,6,... semua kirim notifikasi masing-masing, bukan
    cuma sekali di awal) - ini otomatis terjadi karena tiap candle
    baru = shift/waktu baru = key dedup baru.
  - Dot HANYA ada di candle TERAKHIR/TERBARU rentetan yang masih
    berjalan (lihat bagian 12 - dotFollowsLatest), BUKAN di candle
    pertama rentetan.

====================================================================
7. SISTEM DEDUP SINYAL (ANTI NOTIF DOBEL) - Utils.mqh
====================================================================

Setiap kombinasi (waktu candle, timeframe, index pattern, arah)
dikompres jadi 1 angka ulong (MakeSeenKey), disimpan di array
g_seenKeys[] yang SELALU terurut menaik, dicek pakai binary search
(SeenKeyLowerBound/SeenKeyCheckAndAdd) - O(log n), jauh lebih ringan
dibanding versi lama yang bandingkan string satu-satu (O(n)).

Urutan penting (bug v2.15 yang diperbaiki): dedup dicatat SEBELUM
filter EMA diterapkan, BUKAN sesudahnya. Kalau dicatat sesudah EMA,
sinyal yang gagal filter EMA tidak akan pernah tercatat "selesai
diproses" - dihitung ulang setiap scan selama-lamanya, dan berisiko
hasilnya beda-beda antar percobaan kalau state buffer EMA berubah di
antara pengecekan. Sekarang: sekali kombinasi candle+pattern+arah
dicek, itu FINAL, tidak dicek ulang lagi apa pun hasilnya.

PruneSeenKeys() - dipanggil tiap full rescan berkala (InpFullRescanEvery)
- membuang entry g_seenKeys yang candle-nya sudah lebih tua dari
jangkauan scan (InpHistoryBars + margin 20), supaya memori & waktu
binary search tidak membesar terus kalau indikator dipasang berbulan-
bulan.

BUG UTAMA yang jadi pemicu awal seluruh perbaikan (v2.15): versi lama
menghitung batas "aman dibuang" pakai asumsi market jalan NONSTOP
(PeriodSeconds(tf) * InpHistoryBars, detik kalender biasa). Padahal
forex/gold libur weekend, jadi InpHistoryBars candle ke belakang itu
menjangkau LEBIH JAUH di kalender asli daripada estimasi lama - entry
yang MASIH terjangkau full rescan bisa kebuang duluan, lalu dianggap
"sinyal baru" lagi -> NOTIF DOBEL. Fix: cutoff sekarang diambil dari
waktu candle ASLI lewat iTime() (bar ke InpHistoryBars+20 di tiap
timeframe, ambil yang PALING TUA di antara semua TF aktif) - otomatis
benar walau ada libur weekend/holiday.

====================================================================
8. FILTER EMA (EmaFilter.mqh)
====================================================================

InitEmaHandles() - buat 1 handle iMA per timeframe aktif (kalau
InpEMAFilterOn=true), disimpan di g_emaHandles[] (struct SEmaHandle:
tf, period, handle).

ApplyEmaFilter(tf, shift, dir):
  - return true (lolos) langsung kalau InpEMAFilterOn=false.
  - return true kalau handle gagal dibuat (tidak memblokir sinyal
    gara-gara error teknis).
  - return true kalau buffer EMA belum siap (CopyBuffer gagal) -
    SENGAJA diloloskan tanpa filter untuk saat itu, supaya sinyal
    valid tidak hilang diam-diam gara-gara data belum siap (biasanya
    tepat setelah OnInit) - full rescan berikutnya otomatis pakai
    data yang sudah siap.
  - Aturan sebenarnya: BUY valid jika Close(C1) > EMA; SELL valid
    jika Close(C1) < EMA.

Filter ini berlaku untuk SEMUA pattern KECUALI yang punya
m_skipEmaFilter=true (saat ini hanya Same Candle).

====================================================================
9. MEKANISME "WARMUP" / TUNGGU HISTORY STABIL
====================================================================

Masalah yang diperbaiki (v2.16): MT5 kadang belum selesai men-download
history candle tepat saat indikator baru dipasang/di-reload (terutama
timeframe yang belum pernah dibuka sebelumnya di terminal itu). Kalau
notifikasi langsung aktif setelah 1x scan awal, history yang "menyusul"
beberapa detik/menit kemudian akan ikut dianggap sinyal baru semua ->
notif nembak beruntun ke HP.

Solusi - state machine di OnTimer():
  - g_initialScanDone mulai dari false (di-set di OnInit, TIDAK
    langsung true setelah scan pertama).
  - Selama false: tiap tick OnTimer, bandingkan g_lastBarsSeen SEBELUM
    dan SESUDAH ScanRange(full rescan) dijalankan.
    - Kalau jumlah bar di SEMUA timeframe TIDAK ADA yang berubah,
      g_warmupStableRounds++ ; kalau ADA yang berubah, direset ke 0.
    - g_warmupTicks++ tiap tick (tanpa syarat).
  - g_initialScanDone di-set true kalau:
      g_warmupStableRounds >= 2  (2x berturut-turut TIDAK ada bar
        baru sama sekali di semua TF -> history dianggap sudah
        lengkap/stabil)
      ATAU
      g_warmupTicks >= maxWarmupTicks (batas maksimal ~120 detik /
        InpFastScanSec, jaga-jaga supaya tidak diam selamanya kalau
        ada broker/simbol yang bar-nya jarang benar-benar stabil).
  - Selama tahap ini: dot TETAP digambar seperti biasa (supaya user
    bisa lihat histori trigger di chart), TAPI notifikasi HP TIDAK
    PERNAH terkirim (dijamin oleh pengecekan g_initialScanDone di
    Scanner.mqh, bukan cuma di sini).

====================================================================
10. GUARD NOTIFIKASI LINTAS-INSTANCE (Utils.mqh)
====================================================================

Skenario yang dijaga: kalau indikator ini suatu saat kepasang lebih
dari 1x untuk simbol yang sama (misal chart M15 & H1 sama-sama
XAUUSD, dua-duanya dipasangi indikator ini) - tiap instance scan
timeframe yang sama & bisa nemu sinyal identik, masing-masing kirim
notif sendiri -> dobel dari sudut pandang user walau sebenarnya "1
trigger" yang sama. g_seenKeys cuma hidup di memori 1 instance jadi
tidak bisa mencegah ini sendirian.

Mekanisme: pakai Global Variable bawaan terminal MT5 (di-share oleh
SEMUA chart/indikator/EA di terminal yang sama) sebagai "klaim" -
instance yang PERTAMA sampai ke sinyal tsb yang berhak kirim
notifnya, instance lain otomatis skip.

  MakeNotifyKey(candleTime, tf, dir) -> ulong, klaim per
    CANDLE+TIMEFRAME+ARAH SAJA (tanpa index pattern) - karena sejak
    v2.15 notif beberapa pattern yang nyala bareng di candle & arah
    sama sudah digabung jadi 1 pesan "Multi Trigger", jadi cukup 1
    klaim per pesan yang benar-benar terkirim.
  GlobalNotifyKeyName(key) -> nama Global Variable:
    "MPS_NOTIFY_<SYMBOL>_<angka key>"
  ClaimNotifyKey(key, candleTime) -> true kalau instance ini yang
    berhak kirim (belum ada yang klaim, GlobalVariableSet dipanggil
    dengan value = candleTime, BUKAN waktu klaim, supaya
    PruneGlobalNotifyKeys bisa pakai cutoff yang sama persis dengan
    g_seenKeys); false kalau sudah diklaim instance lain -> JANGAN
    kirim notif.
  PruneGlobalNotifyKeys(cutoff) -> dipanggil bareng PruneSeenKeys(),
    buang entry Global Variable milik simbol ini yang candle-nya
    sudah di luar jangkauan scan.

Catatan: sesuai konfirmasi user, saat ini cuma dipasang di 1 chart
per simbol - mekanisme ini murni jaga-jaga/defensif kalau suatu saat
dipasang di lebih dari 1 chart.

====================================================================
11. FORMAT NOTIFIKASI HP
====================================================================

Fungsi: SendGroupedNotification() di Scanner.mqh.

Format pesan:
  "<TF> | <Nama Pattern[+Pattern lain]> <Buy/Sell> | <HH:MM> | H <angka> | <SYMBOL>"

Contoh 1 pattern:
  "M30 | Engulfing Sell | 10:30 | H 432 | XAUUSD"

Contoh gabungan >1 pattern nyala bareng di candle+arah sama:
  "H4 | Multi Trigger (Engulfing+ICT) Buy | 14:00 | H 415 | XAUUSD"

Contoh Same Candle (dengan angka rentetan dari 'detail'):
  "M15 | Same Candle 5 Sell | 09:15 | H 210 | XAUUSD"

Komponen:
  <TF>       = TfToShortString(tf) - "M5"/"M15"/"M30"/"H1"/"H4"/"D1"
  <Nama>     = nama pattern (+ detail kalau ada, misal "Same Candle
               5"), atau "Multi Trigger (A+B)" kalau >1 pattern fired
               di candle & arah yang sama.
  <Buy/Sell> = arah dikapitalisasi
  <HH:MM>    = waktu candle sinyal (TimeToString TIME_MINUTES)
  H <angka>  = "ketinggian trigger" dalam poin:
               Buy = (Close-Low)/point, Sell = (High-Close)/point,
               dibulatkan (MathRound) - rumus SAMA PERSIS dengan
               riskRange yang dipakai filter InpXxxMinRange/MaxRange
               di pattern, jadi angkanya langsung bisa dibandingkan
               ke setting filter itu.
  <SYMBOL>   = _Symbol

BUY dan SELL di candle yang sama (kasus sangat jarang - 2 pattern
saling bertentangan arah di 1 candle) tetap dikirim sebagai 2 pesan
terpisah, TIDAK digabung jadi 1 pesan yang membingungkan.

Notifikasi hanya benar-benar terkirim kalau SEMUA syarat ini true:
  - InpNotifyOn = true
  - g_initialScanDone = true (bukan tahap warmup)
  - ClaimNotifyKey() berhasil (belum diklaim instance lain)

====================================================================
12. SISTEM DOT DI CHART (Drawing.mqh + logika di Scanner.mqh)
====================================================================

CreateSignalDot(name, time, price, color, tooltip, tf):
  - Object OBJ_ARROW, arrow code 159 (wingdings filled circle).
  - OBJPROP_TIMEFRAMES di-set sesuai tf sinyal (lewat TfToObjFlag) -
    dot TETAP dibuat untuk semua sinyal apa pun timeframe-nya, tapi
    otomatis DISEMBUNYIKAN oleh MT5 sendiri saat chart tidak sedang
    di timeframe itu (bukan tidak digambar sama sekali) - jadi
    ganti-ganti TF di chart yang sama tidak akan membuat dot dari TF
    lain hilang permanen.
  - Posisi harga: basePrice (Low untuk Buy, High untuk Sell) +/-
    rangeOffset, di mana rangeOffset = (High-Low candle itu) x
    InpDotDistance (fallback 50 poin kalau range candle 0).
  - Tooltip berisi nama pattern (+ detail), arah, timeframe, dan
    waktu candle.
  - Kalau object dengan nama sama sudah ada, tidak dibuat ulang
    (ObjectFind check di awal fungsi).

Penamaan object: "MPS_<NamaPatternPolos>_<TF>_<waktu candle>_<BUY/SELL>"
(pakai nama pattern POLOS, bukan yang sudah ada detail-nya, supaya
stabil walau detail berubah-ubah, misal Same Candle beda rentetan tapi
tetap 1 keluarga nama).

MEKANISME KHUSUS m_dotFollowsLatest (dipakai Same Candle):
  Tujuan: 1 rentetan yang sedang berjalan hanya boleh punya SATU dot
  yang terlihat (di candle terbaru rentetan itu), bukan menumpuk 1 dot
  per candle sepanjang rentetan.
  Cara kerja: SEBELUM menggambar dot baru di candle 'shift', cek dulu
  apakah ada dot dari pattern+arah yang SAMA di candle SEBELUMNYA
  (shift+1, yaitu candle 1 langkah lebih tua/duluan closed). Kalau ada,
  dot lama itu DIHAPUS dulu (ObjectDelete) sebelum dot baru digambar -
  supaya yang terlihat cuma 1, selalu di candle paling akhir rentetan
  yang masih berjalan. Kalau tidak ada dot di situ (misal ini candle
  PERTAMA yang baru saja mencapai minimum rentetan), penghapusan ini
  otomatis tidak melakukan apa-apa (aman, tidak error).

  PENTING (dikonfirmasi lewat bug v2.19): mekanisme "hapus dot lama"
  ini SAJA TIDAK CUKUP untuk mencegah banyak dot muncul sekaligus -
  itu cuma menangani kasus rentetan yang TUMBUH SATU-SATU secara
  real-time (tiap candle baru closed memperpanjang rentetan yang
  sudah ada). Kasus "1x scan menemukan rentetan yang SUDAH LENGKAP
  dari awal" (misal saat initial history scan atau full rescan)
  butuh perbaikan TERPISAH di Check()-nya sendiri (lihat bagian 6.4,
  poin 3 - "pengecekan ujung rentetan") - tanpa itu, banyak shift
  berbeda dalam 1 rentetan panjang akan SAMA-SAMA lolos jadi sinyal
  valid dalam SATU KALI scan, dan mekanisme hapus-dot-lama ini tidak
  sempat jalan di antara mereka (semuanya diproses dalam 1 loop yang
  sama, bukan giliran candle real-time yang terpisah).

====================================================================
13. VARIABLE GLOBAL (STATE) - DAFTAR LENGKAP (Globals.mqh)
====================================================================

detectors[]            CPatternDetector* - daftar semua instance
                        pattern aktif (diisi InitDetectors()).
g_timeframes[]          ENUM_TIMEFRAMES - daftar TF yang sedang aktif
                        dipindai (dari input on/off, dibangun ulang
                        tiap OnInit).
g_initialScanDone       bool - false selama tahap warmup (lihat
                        bagian 9), notifikasi HP TIDAK PERNAH
                        terkirim selama ini masih false.
g_timerTicks            int - penghitung tick OnTimer (dipakai untuk
                        interval full rescan berkala).
g_lastDeinitReason      int - reason OnDeinit terakhir, dipakai
                        OnInit berikutnya untuk tahu apakah reload
                        ini cuma ganti timeframe chart.
g_lastSymbol            string - symbol chart terakhir, dipakai
                        deteksi symbolChanged di OnInit.
g_warmupStableRounds    int - penghitung berapa kali BERTURUT-TURUT
                        tidak ada bar baru di semua TF (tahap
                        warmup).
g_warmupTicks           int - penghitung total tick selama tahap
                        warmup (untuk batas maksimal jaga-jaga).
g_dotSize               int - InpDotSize yang sudah di-clamp 1-5.
g_emaPeriod             int - InpEMAPeriod yang sudah di-clamp >=1.
g_seenKeys[]             ulong - dedup key, SELALU terurut menaik
                        (lihat bagian 7).
g_lastBarsSeen[]         int - jumlah bar per timeframe saat full
                        rescan terakhir (untuk skip rescan yang tidak
                        perlu & deteksi warmup stabil).
g_emaHandles[]           SEmaHandle{tf, period, handle} - handle
                        indikator EMA per timeframe.

====================================================================
14. CARA MENAMBAH PATTERN BARU
====================================================================

1. Buat file baru di Include/MultiPatternScanner/Patterns/, misal
   "OrderBlock.mqh". Isi class turunan CPatternDetector, override:
     virtual int Check(const string symbol, const ENUM_TIMEFRAMES tf,
                        const int shift, string &detail) override
   Return 1=BUY, -1=SELL, 0=tidak ada sinyal. Parameter 'detail'
   opsional - isi kalau mau nitip teks tambahan ke notifikasi HP
   (lihat SameCandle.mqh sebagai contoh, dipakai untuk angka
   rentetan).
2. Taruh 2 input minimal (on/off + warna) khusus pattern itu di file
   yang sama, contoh:
     input group "=== INDIKATOR: NAMA BARU ==="
     input bool  InpNamaBaruOn    = true;
     input color InpNamaBaruColor = clrXxx;
   Kalau butuh filter tambahan, buat grup input terpisah khusus
   pattern itu (JANGAN dicampur dengan input pattern lain, walau
   modelnya mirip - lihat filosofi Marobozu punya grup sendiri
   walau memakai rumus riskRange yang sama dengan Engulfing/ICT).
3. Tambahkan 1 baris #include di MultiPatternScanner.mq5 (di bawah
   include pattern lain).
4. Daftarkan instance-nya di InitDetectors() (juga di
   MultiPatternScanner.mq5):
     sz = ArraySize(detectors); ArrayResize(detectors, sz + 1);
     detectors[sz] = new CNamaBaru(InpNamaBaruColor, InpNamaBaruOn);
5. Selesai - tidak perlu sentuh file/pattern lain sama sekali.

Flag opsional yang bisa di-set di constructor pattern baru (lihat
PatternBase.mqh):
  m_skipEmaFilter    = true  -> pattern ini kebal filter EMA global,
                                apa pun InpEMAFilterOn.
  m_dotFollowsLatest = true  -> dot pattern ini cuma boleh ada SATU
                                per "rentetan" candle berturut-turut
                                yang sama (lihat bagian 12). PENTING:
                                kalau pattern baru ini juga berbasis
                                "rentetan" seperti Same Candle, WAJIB
                                juga menambahkan pengecekan "ujung
                                rentetan" sendiri di dalam Check()
                                (lihat bagian 6.4 poin 3) - flag ini
                                SAJA tidak cukup untuk mencegah banyak
                                dot/sinyal muncul sekaligus saat 1x
                                scan menemukan rentetan yang sudah
                                lengkap.

====================================================================
15. RIWAYAT VERSI (CHANGELOG RINGKAS)
====================================================================

v2.10 - Perbaikan performa & bug awal: dot semua TF (bukan cuma TF
        chart aktif), dedup numerik+binary search (ganti dari string
        O(n)), skip full rescan kalau bar belum berubah, filter EMA
        tidak lagi diam-diam buang sinyal saat buffer belum siap,
        clamp InpDotSize/InpEMAPeriod, logging kegagalan
        SendNotification/ObjectCreate.

v2.15 - Perbaikan notifikasi dobel ("1 trigger 1 info"):
        - BUG UTAMA: PruneSeenKeys pakai asumsi market nonstop (detik
          kalender), padahal ada libur weekend -> entry dedup yang
          masih relevan kebuang duluan -> notif terkirim ulang. Fix:
          cutoff pakai waktu candle asli (iTime).
        - Urutan dedup dipindah ke SEBELUM filter EMA.
        - >1 pattern nyala bareng di candle+arah sama digabung jadi 1
          notifikasi "Multi Trigger".
        - Guard notifikasi lintas-instance (Global Variable).
        - Notifikasi HP menampilkan ketinggian trigger (H xxx poin).
        - Input baru InpShowDot (dot on/off independen dari notif).

v2.16 - Perbaikan notif dobel saat baru dipasang/reload: history MT5
        kadang belum lengkap ke-download saat itu juga -> tahap
        "senyap" (dot jalan, notif belum aktif) diperpanjang sampai
        jumlah bar semua timeframe berhenti nambah 2x scan
        berturut-turut (state machine warmup di OnTimer), bukan cuma
        1x scan sinkron di OnInit.

v2.17 - 2 pattern baru ditambahkan: Marobozu (body besar + range
        relatif terhadap rata-rata N candle sebelumnya, setting
        sendiri) dan Same Candle (rentetan candle warna sama, tanpa
        filter body/range). PatternBase.mqh menambah parameter
        'detail' opsional di Check() untuk pattern menitip info
        tambahan ke notifikasi HP.

v2.18 - Penyesuaian Same Candle: dot dibatasi 1 per rentetan yang
        masih berjalan (dot lama dihapus saat rentetan bertambah
        panjang), Same Candle dibuat kebal filter EMA global.
        PatternBase.mqh menambah flag m_skipEmaFilter &
        m_dotFollowsLatest.

v2.19 - Perbaikan bug: dot Same Candle masih muncul LEBIH DARI 1
        dalam 1 rentetan yang sama (mekanisme hapus-dot-lama dari
        v2.18 ternyata tidak cukup, karena tidak menangani kasus 1x
        scan menemukan rentetan yang sudah lengkap dari awal). Fix:
        Check() di SameCandle.mqh sekarang memverifikasi 'shift'
        benar-benar ujung/candle terbaru rentetannya sebelum
        dianggap sinyal valid (lihat bagian 6.4 poin 3 & bagian 12).

====================================================================
16. BATASAN & CATATAN PENTING
====================================================================

- Tidak ada compiler MQL5/MetaEditor yang tersedia di lingkungan
  pengembangan ini - semua perbaikan diverifikasi lewat review kode
  manual, pengecekan keseimbangan kurung ({ } dan ( )), dan simulasi
  logika manual (bukan dijalankan sungguhan). SELALU compile-test di
  MetaEditor sebelum dipakai live, dan laporkan kalau ada error
  compile atau perilaku yang tidak sesuai dokumen ini.
- Semua pattern hanya mengevaluasi candle yang SUDAH CLOSED (shift
  mulai dari 1, bukan 0) - tidak ada repainting.
- Guard lintas-instance (bagian 10) murni pencegahan jaga-jaga; sejak
  awal pengembangan dikonfirmasi indikator ini hanya dipasang di 1
  chart per simbol.
- Same Candle adalah SATU-SATUNYA pattern yang kebal filter EMA
  global dan tidak punya filter body/range - pattern lain (Engulfing,
  ICT, Marobozu) semuanya tunduk pada filter EMA global kalau
  InpEMAFilterOn=true.
- InpHistoryBars menentukan jangkauan bar yang dipindai PER
  TIMEFRAME saat full rescan, bukan jumlah sinyal - kalau mau lebih
  ringan/performa lebih baik, kecilkan angka ini (misal dari 500 ke
  25x lebih kecil sesuai yang pernah didiskusikan), dengan konsekuensi
  histori trigger yang bisa dilihat di chart saat baru dipasang jadi
  lebih pendek.

====================================================================
AKHIR DOKUMEN
====================================================================
