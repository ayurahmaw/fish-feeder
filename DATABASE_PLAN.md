# Database Plan — MySQL untuk Sistem Pakan Otomatis (feeder_db)

> Rencana desain database MySQL untuk menyimpan data MQTT sistem pemberian pakan
> (ESP32 Aquaponic Autofeeder). Mengacu pada protokol di `MQTT_FOUNDATION_PLAN.md`.

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
| Pengukuran pakan | **Jarak sensor ultrasonik ke permukaan pakan (cm)** — disimpan mentah di `telemetry.distance_cm` |
| Konversi ke persen | `pct = (empty_cm − distance_cm) / (empty_cm − full_cm) × 100`, dibatasi 0–100; kalibrasi disimpan di `devices.sensor_full_cm` & `devices.sensor_empty_cm` |
| Satuan porsi | `portions` (jumlah porsi), konsisten dengan payload `manual_feed` MQTT yang ada |
| Jadwal | **Berlaku setiap hari** (tanpa kolom hari) — cukup `feed_time` + `portions` + `is_active` |
| Versi MySQL | **MySQL 8.0+** (butuh JSON, window function untuk view) |
| Storage engine | InnoDB, charset `utf8mb4` |

## 3. Skema — 6 Tabel

### 3.1 `devices` — perangkat + konfigurasi (Fitur 1 & 3)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INT UNSIGNED PK AI | |
| `device_code` | VARCHAR(64) UNIQUE | Kode unik = bagian topik MQTT (mis. `feeder01`) |
| `name` | VARCHAR(100) | Nama tampilan |
| `location` | VARCHAR(100) NULL | Lokasi penempatan |
| `sensor_full_cm` | DECIMAL(6,2) | Jarak sensor saat hopper **penuh** (kalibrasi) |
| `sensor_empty_cm` | DECIMAL(6,2) | Jarak sensor saat hopper **kosong** (kalibrasi) |
| `low_feed_threshold_pct` | TINYINT UNSIGNED | **Ambang notifikasi pakan menipis (%)** — default 20, bisa dikonfigurasi |
| `is_online` | TINYINT(1) | Dari topik `status` (LWT/birth) |
| `last_seen_at` | DATETIME(3) NULL | Terakhir telemetry/status diterima |
| `created_at` / `updated_at` | DATETIME(3) | Otomatis |

Constraint: `CHECK (sensor_full_cm < sensor_empty_cm)`.

### 3.2 `telemetry` — time-series level pakan (Fitur 1)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | BIGINT UNSIGNED PK AI | |
| `device_id` | FK → devices | ON DELETE CASCADE |
| `distance_cm` | DECIMAL(6,2) | **Raw jarak ultrasonik** dari MQTT |
| `feed_level_pct` | DECIMAL(5,2) NULL | Persen sisa pakan (dari device atau konversi backend) |
| `state` | VARCHAR(32) NULL | `idle` / `feeding` / `error` |
| `recorded_at` | DATETIME(3) | Waktu masuk (default `CURRENT_TIMESTAMP(3)`) |

Index: `(device_id, recorded_at)`.

### 3.3 `schedules` — jadwal pakan, berlaku tiap hari (Fitur 4)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INT UNSIGNED PK AI | |
| `device_id` | FK → devices | |
| `name` | VARCHAR(100) | Mis. "Pakan Pagi" |
| `feed_time` | TIME | Jam pemberian (mis. `07:00:00`) |
| `portions` | INT UNSIGNED | Porsi per eksekusi, default 1 |
| `is_active` | TINYINT(1) | Aktif/nonaktif |
| `created_at` / `updated_at` | DATETIME(3) | Otomatis |

Index: `(device_id, is_active, feed_time)`.

### 3.4 `commands` — log perintah MQTT keluar (Fitur 5, korelasi ack)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | INT UNSIGNED PK AI | |
| `command_id` | VARCHAR(64) UNIQUE | ID dari payload JSON (korelasi dengan `ack`) |
| `device_id` | FK → devices | |
| `type` | ENUM | `manual_feed`, `set_schedule`, `set_threshold`, `set_rtc`, `get_state` |
| `payload` | JSON | Payload perintah apa adanya |
| `status` | ENUM | `pending` → `sent` → `success` / `failed` / `timeout` |
| `result_message` | VARCHAR(255) NULL | Pesan `message` dari ack |
| `created_at` | DATETIME(3) | |
| `acked_at` | DATETIME(3) NULL | Diisi saat ack diterima |

Index: `(device_id, created_at)`.

### 3.5 `feeding_logs` — history pemberian pakan (Fitur 2 & 6)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | BIGINT UNSIGNED PK AI | |
| `device_id` | FK → devices | |
| `command_id` | VARCHAR(64) NULL | Korelasi dengan `commands`/ack; NULL jika device eksekusi jadwal mandiri |
| `trigger_type` | ENUM | `manual` / `scheduled` |
| `schedule_id` | FK → schedules NULL | Diisi jika trigger = `scheduled` |
| `portions` | INT UNSIGNED | Porsi yang diberikan |
| `status` | ENUM | `pending` / `success` / `failed` |
| `message` | VARCHAR(255) NULL | Pesan ack dari device |
| `distance_before_cm` / `distance_after_cm` | DECIMAL(6,2) NULL | Jarak sensor sebelum/sesudah |
| `feed_level_before_pct` / `feed_level_after_pct` | DECIMAL(5,2) NULL | Persen sebelum/sesudah |
| `requested_at` | DATETIME(3) | Waktu perintah/jadwal |
| `completed_at` | DATETIME(3) NULL | Diisi saat selesai (ack) |

Index: `(device_id, requested_at)`, `(status)`.

### 3.6 `notifications` — alert (Fitur 3)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | BIGINT UNSIGNED PK AI | |
| `device_id` | FK → devices | |
| `type` | ENUM | `feed_low`, `feed_empty`, `feed_failed`, `device_offline` |
| `severity` | ENUM | `info` / `warning` / `critical` |
| `title` | VARCHAR(150) NULL | |
| `message` | VARCHAR(255) | |
| `feed_level_pct` | DECIMAL(5,2) NULL | Level pakan saat alert |
| `is_read` | TINYINT(1) | Default 0 |
| `created_at` | DATETIME(3) | |

Index: `(device_id, is_read, created_at)`.

> **Anti-spam alert (logika backend):** sebelum INSERT, cek notifikasi `type` yang sama
> pada device yang sama yang belum "selesai" (mis. level belum naik lagi di atas threshold
> untuk `feed_low`) — agar tidak berulang tiap telemetry masuk.

## 4. View `v_device_status`

Gabungan device + telemetry terbaru (window function `ROW_NUMBER`) + flag status:

- `feed_level_pct` — **persentase sisa pakan** (Fitur 1)
- `is_empty` — 1 jika persen ≤ 0 (pakan habis)
- `is_low` — 1 jika 0 < persen ≤ `low_feed_threshold_pct` (pakan menipis)

## 5. Seed Data Awal

- Device `feeder01` — "Feeder Kolam 1", kalibrasi `full=5 cm`, `empty=25 cm`, threshold 20%
- 2 jadwal contoh: **Pakan Pagi 07:00** (2 porsi), **Pakan Sore 17:00** (2 porsi)

## 6. Contoh Query per Fitur

1. **Sisa pakan:** `SELECT device_code, feed_level_pct, is_low, is_empty FROM v_device_status;`
2. **Status pemberian terakhir:** `SELECT ... FROM feeding_logs ORDER BY requested_at DESC LIMIT 1;`
3. **Notifikasi aktif:** `SELECT * FROM notifications WHERE is_read = 0 ORDER BY created_at DESC;`
4. **Jadwal aktif:** `SELECT name, feed_time, portions FROM schedules WHERE device_id = ? AND is_active = 1 ORDER BY feed_time;`
5. **Manual feed (transaksi):** INSERT `commands` (status `pending`) + INSERT `feeding_logs` (trigger `manual`, status `pending`) → saat ack diterima, UPDATE keduanya menjadi `success`/`failed` + `completed_at`/`acked_at`.
6. **History:** `SELECT fl.*, s.name AS schedule_name FROM feeding_logs fl LEFT JOIN schedules s ON s.id = fl.schedule_id WHERE fl.requested_at BETWEEN ? AND ? ORDER BY fl.requested_at DESC;`

## 7. Alur Integrasi Backend (MQTT → DB)

| Pesan MQTT | Aksi DB |
|---|---|
| `telemetry` masuk | INSERT `telemetry` + UPDATE `devices.last_seen_at` → evaluasi threshold → INSERT `notifications` bila perlu |
| `status` online/offline | UPDATE `devices.is_online` (+ notif `device_offline` saat offline) |
| Command dikirim | INSERT `commands` (status `sent` setelah publish); jika `manual_feed` juga INSERT `feeding_logs` (`pending`) |
| `ack` masuk | UPDATE `commands` + `feeding_logs` berdasarkan `command_id`; gagal → INSERT notif `feed_failed` |

## 8. File yang Dihasilkan & Cara Import

| File | Isi |
|---|---|
| `database/schema.sql` | CREATE DATABASE + 6 tabel + view + seed data |
| `database/example_queries.sql` | Contoh query per fitur |

Import (MySQL belum terpasang di Mac ini — pasang via Homebrew bila perlu):

```bash
brew install mysql && brew services start mysql
mysql -u root -p < database/schema.sql
mysql -u root -p feeder_db < database/example_queries.sql   # opsional, hanya contoh
```

Verifikasi cepat:

```bash
mysql -u root -p -e "USE feeder_db; SHOW TABLES; SELECT * FROM v_device_status;"
```
