# Audit & Implementation Plan: Scanner State Management

## Hasil Audit (Critical Issues Ditemukan)

### 1. Masalah "Amnesia" State saat Restart (Critical)
Sistem saat ini menyimpan `seen_triggers`, `active_triggers`, dan `last_candle_time` **hanya di dalam RAM (Memory)**. 
Ketika script mati (dihentikan manual, crash, atau direstart oleh watchdog), semua data state ini **hilang**.

**Dampaknya:**
Saat scanner menyala kembali, ia akan melakukan *scan* dan menemukan pattern yang ada di candle saat ini. Karena memori `seen_triggers` kosong, scanner menganggap pattern ini **BARU (🆕)**, padahal sebelum restart mungkin pattern ini sudah terdeteksi dan berstatus **AKTIF (🔄)**.
Akibatnya:
- Spam notifikasi "baru" (🆕) ke grup WA setiap kali sistem di-restart.
- Duplikasi insert data ke database Supabase (`indicator_triggers`).

### 2. Duplikasi Data di Supabase
Karena amnesia di atas, insert ke tabel `indicator_triggers` bisa terjadi berulang untuk *candle* dan *pattern* yang sama persis jika terjadi restart.

---

## Solusi & Perbaikan (Implementation Plan)

Untuk membuat sistem *resilient* (kebal terhadap restart), kita harus **mem-persist (menyimpan) state ke file lokal** (misal `scanner_state.json`).

### 1. Modifikasi `scanner/engine.py`

#### A. Tambahkan Manajemen State File
Di method `__init__`, definisikan path file state (misalnya `scanner_state.json` di folder `scanner/`).
Panggil method `_load_state()` untuk mengisi `seen_triggers`, `active_triggers`, dan `last_candle_time` dari file (jika ada).

#### B. Method `_load_state()` dan `_save_state()`
- **`_load_state()`**: Membaca file JSON, memuat data dictionary. Perlu diperhatikan bahwa dictionary key di JSON selalu string, namun di Python `candle_ts` mungkin integer. Karena key kita berbentuk string (seperti `XAUUSD_M5_1712839200`), ini tidak masalah. 
- **`_save_state()`**: Menyimpan ketiga dictionary tersebut ke dalam file `scanner_state.json`.

#### C. Simpan State di Akhir Siklus
Di dalam loop `run_forever()`, setelah proses pengiriman WA dan `_cleanup_old_data()`, panggil `self._save_state()` agar state terbaru selalu tersimpan ke disk sebelum siklus berikutnya (atau sebelum program mati mendadak).

### 2. Modifikasi Supabase Insert (Opsional/Saran)
Sebaiknya menggunakan metode `.upsert()` jika Supabase mendukung (bergantung pada konfig primary/unique key tabel `indicator_triggers`). Namun, dengan state lokal yang persisten, duplikasi di-Supabase akan otomatis terhindari karena data tidak akan lolos pengecekan `seen_triggers`. Jadi fokus utama kita adalah memperbaiki state lokal.

---

## Alur Kerja Baru

1. **Sistem Start**: `engine.py` memuat `scanner_state.json`.
2. **Scan**: Scanner menemukan `XAUUSD M15 -> Engulfing`.
3. **Pengecekan**: Scanner mengecek `seen_triggers`. Karena state berhasil diload dari sesi sebelumnya, scanner tahu bahwa ini bukan pattern baru.
4. **Hasil**: Tidak ada spam notifikasi "Baru", dan trigger dipertahankan sebagai **AKTIF (🔄)**.

## Open Questions

> [!IMPORTANT]
> **Q1**: Apakah Anda setuju state disimpan ke file `scanner_state.json` di dalam folder `indicatorInfo/triggerInfo`? File ini akan otomatis diperbarui setiap kali scanner mendeteksi perubahan atau membersihkan data lama (sekitar setiap 5 detik).

> [!IMPORTANT]
> **Q2**: Jika Anda setuju, saya akan langsung menerapkan perbaikan ini ke dalam `scanner/engine.py`. Silakan berikan *Approve* (Proceed) pada artifact ini.
