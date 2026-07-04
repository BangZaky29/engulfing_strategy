# TODO - perubahan OP (SL/TP percent tail & TP berbasis distance)

- [x] 1) Implementasi `ExecutionConfig.calculate_sl_price()` dan `ExecutionConfig.calculate_tp_price()` sesuai planning (persentase tail/ekor + TP = OP-SL distance * tp_pct).

- [ ] 2) Integrasikan SL/TP baru ke `mt5_client/execution.py` untuk kasus BUY/SELL (dan pattern bearish_engulfing) dengan prioritas payload sinyal: `signal['sl_price']`/`signal['tp_price']` jika sudah ada, kalau tidak hitung pakai konfigurasi.
- [ ] 3) Cari apakah `detector.py` juga harus mengirim `sl_price`/`tp_price` berbasis persentase tail; jika saat ini tidak ada, tetap gunakan fallback yang dihitung di `execution.py`.
- [ ] 4) Update/penyesuaian konfigurasi: tambahkan field `sl_pct` dan `tp_pct` pada `ExecutionConfig` dengan default dari env (atau fallback ke nilai saat ini `EXECUTION_SL_RING_PCT`/`EXECUTION_TP_PCT_B` yang relevan).
- [x] 5) Jalankan testing khusus `engulfing/tests/test_sl_tp_percentages.py` untuk memastikan test pass.

- [ ] 6) Jika test tidak pass, perbaiki rumus/edge-case (BUY/SELL, rounding).

