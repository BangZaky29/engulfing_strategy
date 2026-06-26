BLUEPRINT FSD - TF_MONITOR MT5

Nama Project:
TF_Monitor

Tujuan:
TF_Monitor adalah indikator MT5 terpisah untuk membaca korelasi H1, M15, dan M5. Indikator ini tidak menggambar object di chart dan tidak melakukan OP. Fungsinya hanya memberi informasi kondisi market melalui Experts dan Push Notification agar user bisa membaca arah utama, konfirmasi, timing entry, freshness trigger, status validitas OP, dan hubungan trigger terhadap EMA.

Struktur File:
MQL5/Indicators/TF_Monitor.mq5
MQL5/Include/TF_Monitor/Config.mqh
MQL5/Include/TF_Monitor/Utils.mqh
MQL5/Include/TF_Monitor/TriggerLogic.mqh
MQL5/Include/TF_Monitor/BiasLogic.mqh
MQL5/Include/TF_Monitor/Notification.mqh

Timeframe Konsep:
H1  = arah utama / bias besar
M15 = konfirmasi arah
M5  = timing eksekusi / trigger masuk
H4 tidak dipakai.

Trigger yang Dipakai:

1. Engulfing
2. Marubozu
3. ICT
4. Pinbar
5. Dominan Break / DB

H1 tidak memakai LBC lagi. H1, M15, dan M5 semuanya memakai aturan trigger yang sama: Engulfing, Marubozu, ICT, Pinbar, dan Dominan Break.

Format Notifikasi:
TF Monitor | STATUS | Buy/Sell/Buy+/Sell+ | H1 ... | M15 ... | M5 ... | Symbol

Contoh:
TF Monitor | VALID | Buy+ | H1 Buy-Multi:Engulfing+DB-4 (2) 09:00 | M15 Buy-Multi:Engulfing+ICT (6) 10:15 | M5 Buy-DB-8 (N) 12:05 (Trend) | XAUUSD

Kolom Arah:
Buy  = H1 Buy, M15 belum searah Buy
Sell = H1 Sell, M15 belum searah Sell
Buy+ = H1 Buy dan M15 Buy
Sell+ = H1 Sell dan M15 Sell

Status Validitas:
Status dihitung dari H1 dan M15 saja. M5 tidak menentukan status, hanya menjadi timing eksekusi.

STRONG:
H1 dan M15 searah, keduanya Trend terhadap EMA, H1 belum tua, M15 masih fresh.
Aksi: OP boleh jika M5 searah. RR 1:2 sampai 1:3.

VALID:
H1 dan M15 searah, kondisi masih layak, tapi tidak sekuat STRONG.
Aksi: OP boleh jika M5 searah. RR 1:1.

EARLY:
H1 dan M15 searah, tapi salah satu masih Rev / reversal awal.
Aksi: OP hanya saat pullback 20% sampai 40%. RR 1:1.

LATE:
H1 dan M15 searah, tetapi H1 sudah terlalu tua / jenuh, contoh H1 age >= 5.
Aksi: No OP baru.

WAIT:
H1 dan M15 belum searah.
Aksi: No OP.

Aturan Eksekusi:
OP tetap berdasarkan M5.
Jika status STRONG / VALID / EARLY, entry hanya dipertimbangkan jika M5 muncul trigger searah dengan kolom Buy+/Sell+.
Jika kolom Sell+ maka cari M5 Sell.
Jika kolom Buy+ maka cari M5 Buy.
Jika status LATE atau WAIT maka tidak OP baru.

Panduan OP / SL / TP:
STRONG = OP M5 searah, SL M15 structure, TP RR 1:2 sampai 1:3.
VALID = OP M5 searah, SL M15 structure atau M5+buffer, TP RR 1:1.
EARLY = OP hanya pullback 20% sampai 40%, SL M5/M15 terdekat, TP RR 1:1.
LATE = No OP baru.
WAIT = No OP.

EMA:
Input UseEMAFilter tetap ada.
Jika UseEMAFilter=true, trigger yang melawan EMA difilter dan tidak muncul. Semua trigger baru yang muncul akan diberi label (Trend).
Jika UseEMAFilter=false, semua trigger tetap muncul. Saat trigger baru atau masih fresh, diberi label:
(Trend) = arah trigger searah EMA
(Rev) = arah trigger melawan EMA
Label Trend/Rev hanya tampil pada state yang tampil sebagai (N).

Freshness / Umur Trigger:
(N) = trigger baru atau masih berada pada candle closed terakhir / masih fresh.
(1), (2), (3), dst = jumlah candle closed setelah candle trigger pada timeframe masing-masing.
Tidak ada tampilan (0); age 0 ditampilkan sebagai (N).
Waktu trigger selalu tampil agar mudah mencari candle di chart.
Contoh:
H1 Buy-Engulfing (N) 09:00 (Trend)
M15 Sell-DB-4 (3) 10:15
M5 Buy-Pinbar (1) 10:45

Dominan Break / DB:
DB adalah trigger break dari candle master.
Candle master boleh bullish atau bearish.
Buy DB = candle close/body break di atas High candle master.
Sell DB = candle close/body break di bawah Low candle master.
Break wajib oleh candle close, bukan wick dan bukan running candle.
Break valid minimal candle ke-3 setelah master.
Jika candle ke-2 sudah break, tidak valid.
Max default DB = 20 candle.
Jika break lebih dari 20 candle, diabaikan.
Format DB:
DB-3, DB-4, DB-8, DB-20
Angka setelah DB adalah candle ke berapa yang melakukan break dari candle master.
Contoh:
H1 Buy-DB-4 (N) 09:00 (Trend)
Artinya candle ke-4 setelah master close break ke atas.

Multi Trigger:
Jika lebih dari satu trigger muncul pada candle yang sama dan searah, maka tampil sebagai Multi.
DB boleh ikut Multi Trigger.
Contoh:
M15 Buy-Multi:Engulfing+DB-4 (N) 10:15 (Trend)
H1 Sell-Multi:ICT+Pinbar+DB-6 (2) 09:00

Notifikasi:
Indikator hanya memberi info melalui Experts dan Push Notification.
Tidak menggambar object di chart.
Notif keluar jika ada perubahan state trigger pada H1, M15, atau M5.
Notif tidak keluar hanya karena angka umur candle bertambah.
Jika trigger yang sama muncul lagi di candle baru, tetap dianggap event baru karena waktu candle ikut dibandingkan.

Setting Awal Disarankan:
MonitorTimerSeconds = 3
TriggerLookbackBars = 200
NotifyOnFirstLoad = false
PushOnFirstLoad = false
PrintLoadStatus = false
UseEMAFilter = false untuk testing data lengkap
UseEMAFilter = true jika ingin hanya sinyal searah EMA
EnablePushNotification = true
PrintToExperts = true
UseMultiTrigger = true
DominanBreakMinCandles = 3
DominanBreakMaxCandles = 20
DominanBreakBufferPoints = 0

Catatan:
TF Monitor adalah alat baca market dan panduan decision. Entry awal tetap boleh memakai EA LBC. TF Monitor terutama membantu membaca korelasi H1-M15-M5, validitas arah, serta timing M5 untuk OP atau penyelesaian hedge manual.
