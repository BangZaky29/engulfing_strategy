====================================================================
RCS_EA_MT5 (Reversal Candle System) - BLUE PRINT ALUR LOGIKA & INPUT
====================================================================

STRUKTUR FILE
-------------
RCS_EA_MT5.mq5   : entry point (OnInit/OnTick/OnTimer/OnTradeTransaction),
                    state machine Phase, Freeze/Unfreeze, deteksi manual OP.
RCS/Config.mqh   : semua input parameter, variabel global, helper hitung
                    harga/lot/profit, ledger deal, TradeOpen(), CloseAllOrders().
RCS/Trigger.mqh  : deteksi pola candle (Engulfing/ICT) + semua filter + hitung
                    level OP1/OP2/OP3.
RCS/Engine.mqh   : eksekusi OP1/OP2/OP3, cek TP, cek SL, transisi ke Freeze.
RCS/Notif.mqh    : semua teks notifikasi HP + estimasi USD di tiap notif.
RCS/Guard.mqh    : cek izin trading (AlgoTrading ON, akun/symbol diizinkan).
RCS/Log.mqh      : tulis CSV (signal, eksekusi, survey MAE/MFE) + jurnal Print.
RCS/Visual.mqh   : gambar titik sinyal di chart.

STATE MACHINE (Phase)
----------------------
PHASE_IDLE   -> menunggu candle baru yang lolos semua filter trigger.
PHASE_OP1    -> OP1 sudah/segera terbuka, memantau TP / OP2 / OP3 / SL.
PHASE_FREEZE -> hedge sudah terkunci (net exposure ~0) ATAU manual OP
                terdeteksi, menunggu SEMUA posisi/order di symbol ini
                ditutup manual sebelum EA aktif cari trigger lagi.

ALUR DETEKSI TRIGGER (Trigger.mqh, dicek 1x per candle SignalTF baru)
-----------------------------------------------------------------------
1. Pola candle C1 vs C2: Engulfing (C1 harus "menelan" full range C2
   termasuk ekor) dan/atau ICT (liquidity sweep N candle sebelumnya via
   ICTSweepLookbackBars + rejection candle, minimal setara ketat Engulfing).
   Kalau dua-duanya valid bersamaan -> nama trigger "Multi".
2. Filter yang harus lolos SEMUA: Range risiko candle (Close-Low utk
   bullish / High-Close utk bearish) di antara MinTriggerRange-MaxTriggerRange;
   Body% candle di antara MinBodyPercent-MaxBodyPercent; Spread saat ini
   <= MaxSpreadPoints (jika UseSpreadFilter); EMA Pullback Filter (Open C1
   di sisi benar & <= MaxOpenDistanceToEMA_Points dari EMA, Close C1 wajib
   sudah nembus ke sisi benar, opsional filter slope EMA).
3. Kalau gagal -> notif/CSV "Skip" + alasan detail. Kalau valid -> Phase
   ke PHASE_OP1, level OP1/OP2/OP3 dihitung dari Close C1 +/- persentase
   riskRange (EntryPercent/OP2Percent/OP3Percent), notif Trigger dikirim.

EKSEKUSI OP1 (Engine_OnTick)
-----------------------------
- Mode INSTANT_ZERO: langsung entry market di harga Close C1 begitu trigger
  valid (dengan slip filter MaxInstantZeroSlipPoints).
- Mode PERCENT: tunggu harga menyentuh trg_OP1_Level (+ toleransi opsional
  EntryTolerancePoint), lalu entry dengan slip filter MaxTargetSlipPoints.
- TP1 dihitung dari OP1_OpenPrice: TP_MODE_PERCENT (persen jarak OP1-OP2)
  atau TP_MODE_USD (target profit USD tetap, dikonversi ke jarak harga).

OP2Mode (pilih salah satu, menentukan seluruh perilaku setelah OP1)
----------------------------------------------------------------------
- HEDGE         : begitu harga sentuh level OP2, buka posisi LAWAN arah
                  (lot LotSizeOP2) -> Phase FREEZE, snapshot floating
                  (rcs_freezeStartFloatingUSD) & waktu (rcs_freezeStartTime
                  = waktu deal hedge itu sendiri, bukan TimeCurrent()
                  belakangan). Eksekusi UNCONDITIONAL, tanpa slip filter
                  (satu-satunya proteksi OP1 di mode ini).
- SL            : level OP2 = Stop Loss OP1. Dicoba SL real ke broker
                  atomic saat entry; kalau ditolak, fallback pantau &
                  close manual software tiap tick (Engine_CheckSoftwareSL).
- HEDGE_REENTRY : mode 3-OP. OP2 re-entry SEARAH di level lama (OP2Percent)
                  -> target ganti ke TP2 (basis jarak OP1-OP2, dari harga
                  rata2 OP1+OP2 kalau TP2Mode=USD). Kalau harga terus lawan
                  sampai OP3Percent -> OP3Mode menentukan:
                    * HEDGE : buka lawan arah, lot = OP1+OP2 terisi -> FREEZE
                              (perilaku sama seperti OP2Mode=HEDGE di atas).
                    * SL    : langsung tutup SEMUA posisi, TIDAK Freeze,
                              cooldown OP3CooldownCandles, EA lanjut cari
                              trigger baru.

PENUTUPAN POSISI (selain lewat Freeze)
-----------------------------------------
- TP kena (Engine_CheckTP) atau posisi "hilang" tanpa EA yang menutup
  sendiri (Engine_HandleVanishedPosition - broker SL/SO otomatis atau
  user close manual) -> hitung profit via LastClosedProfitLBCGroupUSD()
  (jumlah per POSITION ID OP1/OP2/OP3 dari ledger deal / History, akurat
  komisi & imun soal waktu) -> notif Result -> cooldown SLCooldownCandles
  kalau closenya krn SL/SO -> Phase kembali IDLE.

FREEZE -> UNFREEZE & "HASIL RECOVERY"
----------------------------------------
Freeze dianggap "isHedgeFreeze" kalau bukan dari manual OP DAN OP2Mode-nya
HEDGE/HEDGE_REENTRY. Begitu semua posisi/order di symbol ini closed:
  profit = LastClosedProfitLBCGroupUSD()                    [akurat per
         + RCS_SumClosedProfitSinceExcludingTickets(         posisi OP1/
             sejak rcs_freezeStartTime,                      OP2/OP3, imun
             exclude ticket OP1/OP2/OP3)                     waktu]
                                                              [+ deal manual
                                                               LAIN selama
                                                               freeze, tanpa
                                                               dobel-hitung]
  Hasil Recovery = profit - rcs_freezeStartFloatingUSD (floating snapshot
  persis saat hedge terkunci penuh).
Kalau Freeze dari manual OP (bukan hedge EA) -> tidak ada angka recovery
yang dihitung/ditampilkan.

NOTIFIKASI & LOGGING
----------------------
Semua notif HP (Trigger/Skip/Open Posisi/Freeze/Result/Unfreeze) tampilkan
proyeksi/estimasi USD (jarak harga x tick value x lot) untuk field yang
belum terjadi, dan angka REAL (dari History/ledger) untuk hasil final.
Toggle per kategori: HP_Notif_Trigger/Skip/OpenPosisi/Result/FreezeInfo/Guard.
CSV log 3 jenis (per Symbol+TF): Signal (tiap evaluasi candle), Execution
(tiap OP dibuka), Survey (1 baris per trade selesai, isi MAE/MFE analysis).

INPUT UTAMA (per grup, RCS/Config.mqh)
------------------------------------------
VISUAL/HISTORY DOTS      : tampilan titik sinyal di chart.
TRIGGER PATTERN          : UseTrigger_Engulfing/ICT, ICTSweepLookbackBars.
EMA PULLBACK FILTER      : UseEMAPullbackFilter, EMAPeriod,
                            MaxOpenDistanceToEMA_Points, slope opsional.
SPREAD FILTER            : UseSpreadFilter, MaxSpreadPoints.
BODY FILTER               : MinBodyPercent, MaxBodyPercent.
TRIGGER RANGE FILTER     : MinTriggerRange, MaxTriggerRange.
OP1 (ENTRY)               : OP1EntryMode, EntryPercent, TPMode, TP_Percent/
                            TP_USD, LotSizeOP1, MagicOP1.
OP2                       : OP2Mode, OP2Percent, SLCooldownCandles,
                            TP2Mode, TP2_Percent/TP2_USD, LotSizeOP2, MagicOP2.
OP3 (khusus HEDGE_REENTRY): OP3Mode, OP3Percent, OP3CooldownCandles, MagicOP3.
EXECUTION CONTROL         : slip filter (Target & Instant-Zero).
TRIGGER AGE / RE-TRIGGER  : ModeManajemenTrigger, MaxTriggerAge.
SLIPPAGE                  : Slippage (poin, ke broker).
NOTIFIKASI HP              : toggle per kategori notif.
CSV LOG                    : UseCSVLog, CSVLogFileNamePrefix.

CATATAN VERSI "MASTER" (RCS_EA_MASTER)
------------------------------------------
Salinan proyek ini dengan RCS/Trigger.mqh dikosongkan total (jadi stub
kontrak kosong: RCS_CheckTrigger() selalu return false, RCS_DrawHistoryDots()
kosong) - semua file lain (Config/Engine/Notif/Guard/Log/Visual/main .mq5)
byte-identical dengan RCS_EA_MT5. Tujuannya: "mesin" eksekusi OP1/OP2/OP3/
Freeze-Recovery dijadikan modul stabil yang bisa digabung dengan trigger
pattern lain (mis. Marubozu) di kemudian hari tanpa menyentuh logika mesin.
====================================================================
