Udah gue cross-check langsung ke source code lu (`trade_monitor.py`, `main.py`, `candle_fetcher.py`, `candle_repo.py`). Diagnosa lu **sebagian besar benar**, tapi ada 2 detail teknis yang perlu dikoreksi dulu biar fix-nya tepat sasaran.

## Koreksi atas temuan lu

**1. `min_interval_sec = 10` BUKAN penyebab utama snapshot pertama kosong.**

Cek logic-nya: `should_snap` default `True`, dan cuma jadi kondisional kalau `last_snap` udah ada isinya. Di snapshot PERTAMA per ticket, `info.get("latest_snapshot_time")` masih `None` → `should_snap = True` langsung, gak nunggu 10 detik.

Yang gue temu di `main.py` baris 336: `POLL_INTERVAL = 1` detik (default). Jadi `check_closed_trades()` dipanggil tiap ~1 detik. Root cause sebenernya:

```python
if positions is not None and len(positions) > 0:
    info["status"] = "ACTIVE"
    save_tracked_trades(data)
    ...
    continue   # ← INI masalahnya
```

Begitu status PENDING→ACTIVE kedetek, kode langsung `continue` ke ticket berikutnya — **gak sempat ambil snapshot di pass yang sama**. Snapshot pertama baru kesempatan diambil di pass BERIKUTNYA (~1 detik kemudian). Kalau trade fill lalu closed dalam window <1-2 detik itu (scalp super cepat / slippage ekstrem), snapshot beneran nol — tapi window-nya ~1-2 detik, bukan 10 detik kayak dugaan lu.

**2. `info["entry_time"]` (JSON tracker) TIDAK mempengaruhi kolom "Entry Time" di dashboard.**

Cek baris ~684 di `trade_monitor.py`, `analytics_data["entry_time"]` diambil dari variabel lokal `entry_time` yang dihitung dari `mt5.history_deals_get()` (deal `DEAL_ENTRY_IN`) — **independen** dari `info["entry_time"]` di JSON tracker. Jadi row `#773xxx` yang "Entry Time = —" di screenshot lu itu bukan gara-gara coupling ini. Kemungkinan besar itu trade lama yang closed sebelum bot sempat catat deal entry-nya dengan benar (data legacy), sesuai dugaan lu juga.

**3. Kabar bagus:** gue cek `main.py` baris 192, tabel `candles` **direkam terus-menerus** tiap candle baru close, independen dari sinyal trading. Ini artinya fallback pakai candle OHLC (usulan lu poin 4) **layak dan malah berpotensi LEBIH akurat** dari live polling — karena OHLC nangkep high/low sebenarnya dalam 1 candle, sementara polling tiap 1-3 detik masih bisa miss extreme di antara sample.

---

## Step by step fix (prioritas)

### Step 1 — Tambah snapshot instan saat order fill (fix utama, prioritas tertinggi)

File: `mt5_client/trade_monitor.py`. Cari blok ini (di dalam `if status == "PENDING":`):

```python
            positions = mt5.positions_get(ticket=ticket)  # type: ignore
            if positions is not None and len(positions) > 0:
                # ORDER TERSENTUH (FILLED)!
                print(f"🎯 PENDING ORDER TERSENTUH: #{ticket} ({info['symbol']}) | Sesi: {session_str}")
                info["status"] = "ACTIVE"
                # Simpan perubahan status ke JSON
                save_tracked_trades(data)
                
                # Kirim log ke Supabase agar WA bot men-trigger notifikasi
                try:
                    supabase = get_supabase()
                    log_data = {
                        "ticket_id": ticket,
                        "symbol": info['symbol'],
                        "mode": info['mode'],
                        "message": f"🔥 LIMIT ORDER TERSENTUH! Posisi {info['mode']} aktif sekarang.",
                        "op_price": info['op_price'],
                        "sl_price": info['sl_price'],
                        "tp_price": info['tp_price'],
                        "trading_session": session_str
                    }
                    supabase.table("trade_active_logs").insert(log_data).execute()
                except Exception as ex:
                    print(f"⚠️ Gagal menyimpan log aktif ke Supabase: {ex}")
                    
                continue
```

Tambahkan blok baru **persis sebelum `continue`** (jangan ganti apapun yang udah ada, cuma nambah):

```python
                except Exception as ex:
                    print(f"⚠️ Gagal menyimpan log aktif ke Supabase: {ex}")

                # --- SNAPSHOT INSTAN saat order baru fill (jangan tunggu poll berikutnya) ---
                try:
                    pos0 = positions[0]
                    entry_price0 = getattr(pos0, "price_open", None) or info.get("op_price")
                    current_price0 = getattr(pos0, "price_current", None) or entry_price0
                    current_profit0 = float(getattr(pos0, "profit", 0.0) or 0.0)
                    volume_lot0 = float(getattr(pos0, "volume", 0.0) or 0.0)
                    now_dt0 = datetime.now(timezone.utc)

                    floating_pct0 = 0.0
                    try:
                        if entry_price0 and float(entry_price0) != 0:
                            if info.get("mode") == "BUY":
                                floating_pct0 = (float(current_price0) - float(entry_price0)) / float(entry_price0) * 100.0
                            else:
                                floating_pct0 = (float(entry_price0) - float(current_price0)) / float(entry_price0) * 100.0
                    except:
                        floating_pct0 = 0.0

                    symbol_info0 = mt5.symbol_info(info["symbol"])  # type: ignore
                    sb_payload0 = {
                        "ticket_id": ticket,
                        "symbol": info["symbol"],
                        "timeframe": info["tf"],
                        "mode": info["mode"],
                        "trigger_type": info.get("trigger_type") or "Engulfing",
                        "tf_execute": info.get("tf", "M5"),
                        "tf_monitor": info.get("tf_monitor", "M15"),
                        "snapshot_time": now_dt0.isoformat(),
                        "floating_profit_usd": current_profit0,
                        "floating_pct_from_entry": floating_pct0,
                        "volume_lot": volume_lot0,
                        "distance_price_units": abs(float(current_price0) - float(entry_price0)) if current_price0 and entry_price0 else None,
                        "trigger_tf_list": json.dumps(info.get("tf_list", [info.get("tf", "M5")])),
                        "entry_price": float(entry_price0) if entry_price0 is not None else None,
                        "current_price": float(current_price0) if current_price0 is not None else None,
                        "sl_price": float(info.get("sl_price") or 0.0),
                        "tp_price": float(info.get("tp_price") or 0.0),
                        "phase": "BEFORE_PROFIT",
                        "digits": int(getattr(symbol_info0, 'digits', 0) or 0) if symbol_info0 else None,
                        "point": float(getattr(symbol_info0, 'point', 0.0) or 0.0) if symbol_info0 else None,
                        "tick_size": float(getattr(symbol_info0, 'trade_tick_size', 0.0) or 0.0) if symbol_info0 else None,
                        "tick_value": float(getattr(symbol_info0, 'trade_tick_value', 0.0) or 0.0) if symbol_info0 else None,
                    }
                    supabase.table("trade_floating_snapshots").insert(sb_payload0).execute()
                    info["latest_snapshot_time"] = now_dt0.isoformat()
                    save_tracked_trades(data)
                except Exception as ex:
                    print(f"⚠️ Gagal insert snapshot instan untuk #{ticket}: {ex}")
                # -------------------------------------------------------------------------

                continue
```

Ini jamin **minimal 1 row selalu ada** begitu order fill, walau langsung closed sepersekian detik kemudian.

### Step 2 — Turunin throttle interval (pelengkap Step 1)

Cari baris:
```python
min_interval_sec = 10
```
Ganti:
```python
min_interval_sec = 3
```

### Step 3 — Frontend: bedain "data gap" vs "gak pernah minus"

File: `TradePerOpTable.tsx`. Di `fetchFloatSummary`, tambah query kedua buat tau ticket mana yang PUNYA snapshot sama sekali (regardless floating value):

```typescript
const fetchFloatSummary = async (ticketIds: number[]) => {
  try {
    // Query 1: yang udah ada (floating negatif saja)
    const { data, error: err } = await supabase
      .from('trade_floating_snapshots')
      .select('ticket_id,floating_profit_usd,floating_pct_from_entry,entry_price,current_price,point')
      .in('ticket_id', ticketIds)
      .lt('floating_profit_usd', 0);
    if (err) throw err;

    // Query 2 (BARU): semua ticket yg PUNYA snapshot, gak peduli nilai floating-nya
    const { data: allSnaps, error: allErr } = await supabase
      .from('trade_floating_snapshots')
      .select('ticket_id')
      .in('ticket_id', ticketIds);
    if (allErr) throw allErr;

    const sampled = new Set((allSnaps ?? []).map((r: any) => r.ticket_id as number));
    setSampledTickets(sampled);

    // ... sisa logic map floating tetap sama seperti sebelumnya
```

Tambah state baru di atas komponen:
```typescript
const [sampledTickets, setSampledTickets] = useState<Set<number>>(new Set());
```

Lalu di cell "Max Float (USD)" ganti:
```tsx
// SEBELUM:
{hasFloat ? (
  <span className="text-orange-400">-{fmtMoney(row.max_float_usd)}</span>
) : (
  <span className="text-slate-600 text-xs">no data</span>
)}

// SESUDAH:
{hasFloat ? (
  <span className="text-orange-400">-{fmtMoney(row.max_float_usd)}</span>
) : sampledTickets.has(row.ticket_id) ? (
  <span className="text-emerald-500 text-xs" title="Ada snapshot, tapi floating gak pernah minus">selalu profit</span>
) : (
  <span className="text-slate-600 text-xs" title="Belum sempat ke-sample (trade closed instan / data lama)">data gap</span>
)}
```

### Step 4 (opsional, buat backfill data lama) — candle-based fallback

Ini yang paling berguna buat ticket lama kayak `#773xxx` yang emang gak pernah ke-sample. Karena `candles` table (lihat `main.py` baris 192) direkam terus-menerus independen dari sinyal, kita bisa hitung ulang worst floating dari OHLC candle di rentang `entry_time`–`exit_time`. Mau gue buatin script backfill-nya (`database/backfill_floating_from_candles.py`, ngikutin pola yang udah ada di `backfill_session.py`)?