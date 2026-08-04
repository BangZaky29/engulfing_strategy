# Analisis Konfigurasi Parameter Input (EA/Trading Bot)

Berikut adalah hasil ekstraksi dari gambar konfigurasi input parameter yang Anda berikan:

| Variable | Value |
| :--- | :--- |
| SignalTF | 5 Minutes |
| **=== VISUAL ===** | |
| ShowOnlySignalTF | true |
| DrawSignalDots | true |
| SignalOffsetPoints | 2500 |
| TextOffsetPoints | 1000 |
| BuyDotColor | Lime |
| SellDotColor | Red |
| DotArrowCode | 159 |
| DotWidth | 3 |
| TextColor | White |
| TextFontSize | 8 |
| **=== HISTORY DOTS (saat EA di-attach) ===** | |
| DrawHistoryOnAttach | true |
| HistoryTriggerCount - jumlah sinyal valid TERAKHIR yang mau dit | 10 |
| HistoryMaxBarsScan - batas scan candle ke belakang, biar tidak | 3000 |
| **=== TRIGGER PATTERN ===** | |
| DebugFilters | false |
| UseTrigger_Engulfing | true |
| UseTrigger_ICT | true |
| ICTSweepLookbackBars | 2 |
| **=== EMA PULLBACK FILTER (single TF = SignalTF) ===** | |
| UseEMAPullbackFilter | true |
| EMAPeriod | 20 |
| MaxOpenDistanceToEMA_Points | 2000 |
| UseEMASlopeFilter | false |
| EMASlopeLookbackBars | 3 |
| MinEMASlopePoints | 10 |
| **=== SPREAD FILTER ===** | |
| UseSpreadFilter | true |
| MaxSpreadPoints | 750 |
| **=== BODY FILTER (hindari doji di candle trigger) ===** | |
| MinBodyPercent | 50.0 |
| MaxBodyPercent | 100.0 |
| **=== TRIGGER RANGE FILTER ===** | |
| MinTriggerRange | 350.0 |
| MaxTriggerRange | 20000.0 |
| **=== OP1 (ENTRY) ===** | |
| OP1EntryMode | OP1_MODE_INSTANT_ZERO |
| EntryPercent | 15.0 |
| UseEntryTolerance | false |
| EntryTolerancePoint | 200.0 |
| TPMode | TP_MODE_PERCENT |
| TP_Percent | 50.0 |
| TP_USD | 5.0 |
| LotSizeOP1 | 0.01 |
| MagicOP1 | 221160935 |
| **=== OP2 ===** | |
| OP2Mode | OP2 re-entry SEARAH di level lama, hedge beneran digeser ke OP3 |
| OP2Percent - level OP2 (Hedge ATAU re-entry searah, tergantung | 50.0 |
| SLCooldownCandles - hanya dipakai saat OP2Mode = SL (2-OP, buka | 1 |
| TP2Mode | TP_MODE_PERCENT |
| TP2_Percent | 100.0 |
| TP2_USD | 5.0 |
| LotSizeOP2 - hanya dipakai saat OP2Mode = HEDGE atau HEDGE_REEN | 0.01 |
| MagicOP2 | 221160936 |
| **=== OP3 (khusus OP2Mode = HEDGE_REENTRY) ===** | |
| OP3Mode | OP3_MODE_HEDGE |
| OP3Percent - level hedge/SL beneran | 110.0 |
| OP3CooldownCandles - hanya dipakai saat OP3Mode = SL | 1 |
| MagicOP3 | 221160937 |
| **=== EXECUTION CONTROL ===** | |
| UseMaxTargetSlipFilter | true |
| MaxTargetSlipPoints | 350.0 |
| UseInstantZeroSlipFilter | true |
| MaxInstantZeroSlipPoints | 350.0 |
| ModeManajemenTrigger | TRIGGER_RETRIGGER_SEBELUM_OP1 |
| MaxTriggerAge | 2 |
| **=== SLIPPAGE ===** | |
| Slippage | 50 |
| **=== NOTIFIKASI HP ===** | |
| HP_Notif_Trigger | false |
| HP_Notif_Skip | true |
| HP_Notif_OpenPosisi | true |
| HP_Notif_Result | true |
| HP_Notif_FreezeInfo | true |
| HP_Notif_Guard | false |
| **=== CSV LOG ===** | |
| UseCSVLog | true |
| CSVLogFileNamePrefix | RCS_Log_NAS100 |
| **=== HOUSEKEEPING ===** | |
| ClearObjectsOnInit | true |