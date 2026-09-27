# Database Plan — SQLite untuk Sistem Pakan Otomatis (feeder_db)

> Desain database untuk menyimpan data MQTT sistem pemberian pakan (ESP32 Aquaponic
> Autofeeder). Mengacu pada protokol di `MQTT_FOUNDATION_PLAN.md` / `DEVICE_PROTOCOL.md`.
>
> **Engine: SQLite**, berjalan **di dalam proses aplikasi** (`dashboard/run.py`).
> Tidak ada server MySQL terpisah.

## 1. Konteks Proyek

Topik MQTT yang sudah ada (device namespace, `feeder01` = device ID):

| Topik | Arah | Fungsi |
|---|---|---|
| `feeder/<device>/state` | device → platform | Snapshot state (jadwal, RTC, level pakan) |
| `feeder/<device>/telemetry` | device → platform | Telemetry periodik (`distance_cm`, `state`) |
| `feeder/<device>/status` | device → platform | `online` / `offline` (retained, LWT/birth) |
| `feeder/<device>/command` | platform → device | Semua perintah (JSON + `command_id`) |
| `feeder/<device>/ack` | device → platform | Ack perintah (korelasi via `command_id`) |

## 2. Keputusan Desain

| Aspek | Keputusan |
|---|---|
| Engine | **SQLite** (bawaan Python, tanpa server) — file `dashboard/feeder.db` |
| Kenapa bukan MySQL | MySQL tidak bisa di-embed di proses aplikasi (`libmysqld` dihapus sejak MySQL 8.0), jadi dia harus jadi service terpisah. SQLite bisa jalan di dalam aplikasi. |
| Pengukuran pakan | **Jarak sensor ultrasonik ke permukaan pakan (cm)** — disimpan mentah di `telemetry.distance_cm` |
| Konversi ke persen | `pct = (empty_cm − distance_cm) / (empty_cm − full_cm) × 100`, dibatasi 0–100; kalibrasi disimpan di `devices.sensor_full_cm` & `devices.sensor_empty_cm` |
| Satuan porsi | `portions` (jumlah porsi), konsisten dengan payload `manual_feed` MQTT yang ada |
| Jadwal | **Berlaku setiap hari** (tanpa kolom hari) — cukup `feed_time` + `portions` + `is_active` |
| Waktu | TEXT ISO `YYYY-MM-DD HH:MM:SS.SSS` (presisi milidetik, menggantikan `DATETIME(3)`) |
| Enum | `ENUM(...)` MySQL → `TEXT` + `CHECK (kolom IN (...))` |
| JSON | `JSON` MySQL → `TEXT` + `CHECK (json_valid(kolom))` |
| Konkurensi | `PRAGMA journal_mode=WAL` (pembaca & penulis bisa bersamaan), `busy_timeout=5000`, `foreign_keys=ON` (default SQLite: OFF) |
| Transaksi | Operasi multi-statement (pakan manual, ack, sweep timeout) pakai `BEGIN IMMEDIATE` |

## 3. Skema — 6 Tabel

Definisi lengkap dan seed ada di `database/schema.sql` (dijalankan otomatis saat pertama start).

### 3.1 `devices` — perangkat + konfigurasi (Fitur 1 & 3)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER PK AI | |
| `device_code` | TEXT UNIQUE | Kode unik = bagian topik MQTT (mis. `feeder01`) |
| `name` | TEXT | Nama tampilan |
| `location` | TEXT NULL | Lokasi penempatan |
| `sensor_full_cm` | REAL | Jarak sensor saat hopper **penuh** (kalibrasi) |
| `sensor_empty_cm` | REAL | Jarak sensor saat hopper **kosong** (kalibrasi) |
| `low_feed_threshold_pct` | INTEGER | **Ambang notifikasi pakan menipis (%)** — default 20 |
| `is_online` | INTEGER 0/1 | Dari topik `status` (LWT/birth) |
| `last_seen_at` | TEXT NULL | Terakhir telemetry/status diterima |
| `created_at` / `updated_at` | TEXT | Diisi kode (SQLite tidak punya `ON UPDATE`) |

Constraint: `CHECK (sensor_full_cm < sensor_empty_cm)`.

### 3.2 `telemetry` — time-series level pakan (Fitur 1)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER PK AI | |
| `device_id` | FK → devices | ON DELETE CASCADE |
| `distance_cm` | REAL NULL | **Raw jarak ultrasonik** dari MQTT |
| `feed_level_pct` | REAL NULL | Persen sisa pakan (dari device atau konversi aplikasi) |
| `state` | TEXT NULL | `idle` / `feeding` / `error` |
| `recorded_at` | TEXT | Waktu masuk (default `strftime('%Y-%m-%d %H:%M:%f','now')`) |

Index: `(device_id, recorded_at)`.

### 3.3 `schedules` — jadwal pakan, berlaku tiap hari (Fitur 4)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER PK AI | |
| `device_id` | FK → devices | |
| `name` | TEXT | Mis. "Pakan Pagi" |
| `feed_time` | TEXT | Jam pemberian, `'07:00:00'` |
| `portions` | INTEGER | Porsi per eksekusi, default 1 |
| `is_active` | INTEGER 0/1 | Aktif/nonaktif |
| `created_at` / `updated_at` | TEXT | |

Index: `(device_id, is_active, feed_time)`.

### 3.4 `commands` — log perintah MQTT keluar (Fitur 5, korelasi ack)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER PK AI | |
| `command_id` | TEXT UNIQUE | ID dari payload JSON (korelasi dengan `ack`) |
| `device_id` | FK → devices | |
| `type` | TEXT + CHECK | `manual_feed`, `set_schedule`, `set_threshold`, `set_rtc`, `get_state` |
| `payload` | TEXT + `json_valid` | Payload perintah apa adanya |
| `status` | TEXT + CHECK | `pending` → `sent` → `success` / `failed` / `timeout` |
| `result_message` | TEXT NULL | Pesan `message` dari ack |
| `created_at` | TEXT | |
| `acked_at` | TEXT NULL | Diisi saat ack diterima |

Index: `(device_id, created_at)`.

### 3.5 `feeding_logs` — history pemberian pakan (Fitur 2 & 6)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER PK AI | |
| `device_id` | FK → devices | |
| `command_id` | TEXT NULL | Korelasi dengan `commands`/ack; NULL jika device eksekusi jadwal mandiri |
| `trigger_type` | TEXT + CHECK | `manual` / `scheduled` |
| `schedule_id` | FK → schedules NULL | Diisi jika trigger = `scheduled` |
| `portions` | INTEGER | Porsi yang diberikan |
| `status` | TEXT + CHECK | `pending` / `success` / `failed` |
| `message` | TEXT NULL | Pesan ack dari device |
| `distance_before_cm` / `distance_after_cm` | REAL NULL | Jarak sensor sebelum/sesudah |
| `feed_level_before_pct` / `feed_level_after_pct` | REAL NULL | Persen sebelum/sesudah |
| `requested_at` | TEXT | Waktu perintah/jadwal |
| `completed_at` | TEXT NULL | Diisi saat selesai (ack) |

Index: `(device_id, requested_at)`, `(status)`.

### 3.6 `notifications` — alert (Fitur 3)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INTEGER PK AI | |
| `device_id` | FK → devices | |
| `type` | TEXT + CHECK | `feed_low`, `feed_empty`, `feed_failed`, `device_offline` |
| `severity` | TEXT + CHECK | `info` / `warning` / `critical` |
| `title` | TEXT NULL | |
| `message` | TEXT | |
| `feed_level_pct` | REAL NULL | Level pakan saat alert |
| `is_read` | INTEGER 0/1 | Default 0 |
| `created_at` | TEXT | |

Index: `(device_id, is_read, created_at)`.

> **Anti-spam alert (logika aplikasi, `dashboard/handlers.py`):** sebelum INSERT, cek notifikasi
> `type` yang sama pada device yang sama yang belum "selesai" (mis. level belum naik lagi di atas
> threshold untuk `feed_low`) — agar tidak berulang tiap telemetry masuk.

## 4. View `v_device_status`

Gabungan device + telemetry terbaru (window function `ROW_NUMBER`) + flag status:

- `feed_level_pct` — **persentase sisa pakan** (Fitur 1)
- `is_empty` — 1 jika persen ≤ 0 (pakan habis)
- `is_low` — 1 jika 0 < persen ≤ `low_feed_threshold_pct` (pakan menipis)

## 5. Seed Data Awal

- Device `feeder01` — "Feeder Kolam 1", kalibrasi `full=5 cm`, `empty=25 cm`, threshold 20%
- 2 jadwal contoh: **Pakan Pagi 07:00** (2 porsi), **Pakan Sore 17:00** (2 porsi)

## 6. Contoh Query per Fitur

Semua contoh lengkap ada di `database/example_queries.sql`. Ringkasnya:

1. **Sisa pakan:** `SELECT device_code, feed_level_pct, is_low, is_empty FROM v_device_status;`
2. **Status pemberian terakhir:** `SELECT ... FROM feeding_logs ORDER BY requested_at DESC LIMIT 1;`
3. **Notifikasi aktif:** `SELECT * FROM notifications WHERE is_read = 0 ORDER BY created_at DESC;`
4. **Jadwal aktif:** `SELECT name, feed_time, portions FROM schedules WHERE device_id = ? AND is_active = 1 ORDER BY feed_time;`
5. **Manual feed (transaksi):** INSERT `commands` (status `sent`) + INSERT `feeding_logs` (trigger `manual`, status `pending`) → saat ack diterima, UPDATE keduanya menjadi `success`/`failed` + `completed_at`/`acked_at`.
6. **History:** `SELECT fl.*, s.name AS schedule_name FROM feeding_logs fl LEFT JOIN schedules s ON s.id = fl.schedule_id WHERE fl.requested_at BETWEEN ? AND ? ORDER BY fl.requested_at DESC;`

## 7. Alur Integrasi Aplikasi (MQTT → DB)

| Pesan MQTT | Aksi DB |
|---|---|
| `telemetry` masuk | INSERT `telemetry` + UPDATE `devices.last_seen_at` → evaluasi threshold → INSERT `notifications` bila perlu |
| `status` online/offline | UPDATE `devices.is_online` (+ notif `device_offline` saat offline, tutup saat online) |
| Command dikirim | INSERT `commands` (status `sent` setelah publish); jika `manual_feed` juga INSERT `feeding_logs` (`pending`) |
| `ack` masuk | UPDATE `commands` + `feeding_logs` berdasarkan `command_id`; gagal → INSERT notif `feed_failed` |
| Sweep berkala (10 s) | Command tanpa ack > 30 s → `timeout`, feeding_log → `failed` |

## 8. File yang Dihasilkan & Cara Import

| File | Isi |
|---|---|
| `database/schema.sql` | 6 tabel + view + seed data (SQLite) |
| `database/example_queries.sql` | Contoh query per fitur |

Import manual (normalnya tidak perlu — aplikasi menjalankannya sendiri saat pertama start):

```bash
sqlite3 dashboard/feeder.db < database/schema.sql
sqlite3 dashboard/feeder.db < database/example_queries.sql   # opsional, hanya contoh
```

Verifikasi cepat:

```bash
sqlite3 dashboard/feeder.db "SELECT * FROM v_device_status;"
```
