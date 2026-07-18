# Engulfing Strategy Bot

Bot trading otomatis berbasis pola *Engulfing* (Bullish/Bearish) yang memindai market MetaTrader 5 (MT5) dan mengeksekusi order secara *real-time*.

## Struktur Folder (Clean Architecture)

Setelah proses *refactoring*, struktur *source code* dirancang modular agar lebih rapi dan mudah dirawat:

```text
engulfing_strategy/
├── main.py                              # Entry point utama (sangat tipis, panggil app/bot)
├── app/                                 # Orchestrator & Logic Bot Utama
│   ├── __init__.py
│   ├── initializer.py                   # print_banner, print_tfm_trigger_status, execution config
│   ├── tfm_logger.py                    # snapshot logger untuk Filter C (TF Monitor)
│   ├── signal_processor.py              # upsert signal, sinkronisasi antar TF, eksekusi order
│   └── bot.py                           # loop polling utama (scan MT5 & Supabase)
│
├── config/                              # Konfigurasi (.env parser, MT5, execution, filters)
├── database/                            # Repositori database (Supabase clients: Candle, Signal, Stats)
│
├── mt5_client/                          # Koneksi & Interaksi dengan MetaTrader 5
│   ├── __init__.py                      
│   ├── connection.py                    
│   ├── candle_fetcher.py                
│   ├── indicators.py                    
│   ├── error_helper.py                  
│   ├── visualizer.py                    
│   ├── execution/                       # Modul Eksekusi Order
│   │   ├── position_guard.py            # Cek posisi aktif, cancel pending lama
│   │   ├── order_params.py              # Kalkulasi OP price, SL dinamis, dan TP
│   │   ├── order_sender.py              # Kirim payload ke MT5
│   │   └── executor.py                  # Orkestrator eksekusi order (panggil modul di atas)
│   └── trade_monitor/                   # Modul Pemantau Trade
│       ├── tracker_store.py             # Menyimpan log tracking JSON
│       ├── session_utils.py             # Tanggal WIB dan sesi market
│       ├── floating_snapshot.py         # Merekam floating PnL realtime
│       ├── hedge_manager.py             # Logika pembatalan hedge jika expired/TP
│       ├── trigger_analytics.py         # Merekam analytics drawdowns
│       └── closed_trade_handler.py      # Orchestrator pemantauan trade yang sudah close
│
├── strategies/engulfing/                # Logika Pola dan Filter Strategy
│   ├── __init__.py                      
│   ├── signal_builder.py                
│   ├── candle_unpacker.py               
│   ├── strategy_a_runner.py             # Pipeline Evaluasi Filter A (Grade filter)
│   ├── strategy_b_runner.py             # Pipeline Evaluasi Filter B (Pullback, EMA Ring)
│   ├── filter_c_gate.py                 # Filter Gate (TF Monitor) Check
│   ├── detector/                        # Submodul Deteksi Pattern & Evaluasi
│   │   ├── filter_ab_eval.py            
│   │   ├── filter_c_eval.py             
│   │   └── orchestrator.py              # Modul utama detect_engulfing()
│   ├── filters_A/                       # F1 Trigger, F2 Scoring, F3 Pattern
│   ├── filters_B/                       # Trigger B, EMA Ring
│   └── filters_C/                       # TF Monitor & Multi-Timeframe Bias
│       ├── triggers/                    # Detektor Spesifik Pattern
│       │   ├── trigger_utils.py         # Helper range/points/body
│       │   ├── trigger_engulfing.py     # Deteksi Engulfing
│       │   ├── trigger_marubozu.py      # Deteksi Marubozu
│       │   ├── trigger_ict.py           # Deteksi ICT Pattern
│       │   ├── trigger_pinbar.py        # Deteksi Pinbar
│       │   ├── trigger_dominan_break.py # Deteksi Dominan Break
│       │   └── trigger_scanner.py       # Scanner latest trigger dari semua pattern
│       ├── f2_bias_logic.py             
│       ├── f3_ema_utils.py              
│       └── f4_state_manager.py          
│
├── tests/                               # Unit test modules
└── utils/                               # Tools & helper warna console
```

## Menjalankan Bot
```bash
python main.py
```
