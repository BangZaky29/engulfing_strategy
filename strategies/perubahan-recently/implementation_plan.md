# Rencana Implementasi: Lot Size per Mata Uang & Fixed $8 Target Profit

Fitur ini akan mengubah cara kalkulasi lot size dan Take Profit (TP). Lot size akan dapat dikonfigurasi per mata uang (symbol), dan TP akan dikalkulasi secara dinamis agar selalu menargetkan profit tepat $8 (atau sesuai konfigurasi) terlepas dari jarak SL. Aturan OP dan SL tidak akan diubah.

## User Review Required

> [!WARNING]
> **Perubahan Cara Kalkulasi TP**
> Sebelumnya TP dihitung berdasarkan jarak SL (misal RR 1:1, maka TP sama jauhnya dengan SL). Dengan perubahan ini, TP murni dihitung dari ukuran lot untuk mencapai target $8. Artinya:
> - Jika Lot besar, jarak TP akan sangat dekat.
> - Jika Lot kecil, jarak TP akan jauh.
> **Mohon konfirmasi bahwa perubahan fundamental perhitungan TP ini sudah sesuai harapan Anda.**

> [!IMPORTANT]
> **Format .env Baru**
> Anda bisa mengatur Lot Size setiap Pair menggunakan `LOT_<SYMBOL>=<VALUE>`. Contoh yang bisa Anda tambahkan ke file `.env`:
> ```env
> LOT_XAUUSD=0.01
> LOT_BTCUSD=0.1
> LOT_USTEC=0.01
> EXECUTION_TARGET_PROFIT_USD=8.0
> ```
> *(Jika `LOT_<SYMBOL>` tidak diatur, sistem akan menggunakan `EXECUTION_LOT_SIZE` sebagai default fallback)*.

## Open Questions

1. Jika ternyata harga SL tersentuh sebelum TP $8, kerugian (loss) akan bervariasi bergantung pada jarak SL dan ukuran Lot yang Anda set. Apakah Anda sudah memahami risiko ini dan tetap ingin melanjutkan skema TP $8?
2. Pada broker MT5 Anda, apa nama persis untuk mata uang BTC dan NASDAQ? (Misal: BTCUSD, Bitcoin, atau yang lain? Dan untuk Nasdaq: USTEC, US100, atau NASDAQ?). Nanti Anda harus menulis konfigurasi sesuai dengan nama pairs yang ada di MT5 (contoh `LOT_USTEC=0.01`).

## Proposed Changes

### Configuration
Update konfigurasi untuk mendukung metode pembacaan lot dinamis per symbol dan target profit tetap ($8).

#### [MODIFY] [execution_config.py](file:///C:/codingVibes/mt5/engulfing/config/execution_config.py)
- Tambahkan fungsi `get_lot_size(symbol)` yang akan mengecek nilai `LOT_{symbol}` di environment variable sebelum fallback ke `EXECUTION_LOT_SIZE`.
- Tambahkan konfigurasi parameter baru `target_profit_usd` dengan nilai default `8.0`.

### Core Signal Detection (Payload & Notifikasi)
Kalkulasi TP harus dilakukan pada saat mendeteksi sinyal agar bot WhatsApp / Telegram langsung menampilkan harga TP yang benar ($8), dan tidak rancu dengan RR.

#### [MODIFY] [detector.py](file:///C:/codingVibes/mt5/engulfing/strategies/engulfing/detector.py)
- Hitung harga `tp_price` berdasarkan target $8 menggunakan rumus tick value dan lot spesifik dari simbol tersebut.
- Ambil informasi `trade_tick_value` dan `trade_tick_size` dari instance `symbol_info` MT5.
- Rumus: `ticks_needed = target_profit_usd / (tick_value * lot_size)` lalu `tp_distance = ticks_needed * tick_size`.
- Update nilai `tp_price` dalam kamus `signal` dan ubah informasi `rr_ratio` menjadi rasio riil terhadap $8 atau cukup kosongkan.
- Pastikan perubahan ini diteruskan ke `notes` agar terbaca dengan benar di notifikasi.

### MT5 Execution Logic
Eksekusi order yang sesungguhnya dikirim ke MT5 juga harus memakai lot size per-symbol dan memverifikasi jarak TP.

#### [MODIFY] [execution.py](file:///C:/codingVibes/mt5/engulfing/mt5_client/execution.py)
- Ganti semua pemakaian `exec_cfg.lot_size` menjadi `exec_cfg.get_lot_size(symbol)` sehingga `mt5.order_send` memakai lot size spesifik.
- Hapus perhitungan lawas `_get_min_profit_distance` yang memodifikasi TP secara RR dan ubah perhitungan total TP logic agar mengikuti perhitungan absolut Target Profit USD ($8).

## Verification Plan

### Manual Verification
- Tambahkan setting lot pada `.env` contoh: `LOT_XAUUSD=0.05`. 
- Saat sinyal Engulfing terdeteksi, amati output console atau notifikasi WhatsApp; pastikan `Entry`, `SL` normal, tetapi TP telah di-adjust sesuai formula perhitungan $8 target.
- Pada Terminal MT5, buka jendela Trade untuk melihat apakah Lot Size yang diaplikasikan sesuai. Evaluasi jika Margin mencukupi saat jarak TP menjadi lebih jauh karena lot size diperkecil.
