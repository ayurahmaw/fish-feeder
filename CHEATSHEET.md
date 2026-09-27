# Cheat Sheet Harian — Sistem Pakan Otomatis (feeder_db + dashboard)

> Referensi cepat operasional sehari-hari. Detail lengkap: `DATABASE_PLAN.md` (desain DB),
> `MQTT_FOUNDATION_PLAN.md` (protokol), `DEVICE_PROTOCOL.md` (kontrak device),
> `STARTUP_GUIDE.md` (setup dari nol), `dashboard/README.md` (aplikasinya).

## Start (2 terminal)

```bash
# 1. Platform — broker MQTT + database + dashboard, semuanya satu proses
cd dashboard
pipenv shell
python run.py                 # → http://localhost:8501

# 2. Simulator device (nanti diganti ESP32) — terminal lain, Node v22
node /Users/macbookpro/Documents/TA-UPH/sim.js
```

Tidak perlu `brew services start mosquitto` dan tidak perlu MySQL: broker MQTT dan database
SQLite sudah berjalan **di dalam** aplikasi. (Kalau port `1883` ternyata sudah dipakai
mosquitto, aplikasi otomatis memakai broker yang sudah jalan itu — terlihat di log startup.)

## Tombol pakan manual

```bash
cd dashboard
pipenv run python cli.py manual_feed feeder01 '{"portions":2}'
```

Contoh perintah lain:

```bash
pipenv run python cli.py get_state feeder01
pipenv run python cli.py set_threshold feeder01 '{"threshold_pct":25}'
```

(`cli.py` butuh aplikasi sedang jalan — dialah yang menjalankan broker dan memproses ack.)

## Stop

`Ctrl+C` di kedua terminal. Tidak ada service yang perlu dimatikan.

## Pantau data (langsung dari file SQLite, tanpa server)

```bash
# Status semua feeder: sisa pakan, online, flag alert
sqlite3 dashboard/feeder.db "SELECT * FROM v_device_status;"

# Notifikasi/alert terbaru
sqlite3 -header -column dashboard/feeder.db \
  "SELECT type, severity, message, created_at FROM notifications ORDER BY created_at DESC LIMIT 5;"

# History pemberian pakan
sqlite3 -header -column dashboard/feeder.db \
  "SELECT requested_at, trigger_type, portions, status, message FROM feeding_logs ORDER BY requested_at DESC LIMIT 10;"

# Jadwal aktif
sqlite3 -header -column dashboard/feeder.db \
  "SELECT name, feed_time, portions, is_active FROM schedules WHERE is_active = 1 ORDER BY feed_time;"

# Pesan MQTT mentah (kolom JSON payload)
sqlite3 -header -column dashboard/feeder.db \
  "SELECT command_id, type, status, created_at FROM commands ORDER BY id DESC LIMIT 5;"
```

## Konfigurasi umum

| Kegiatan | Perintah |
|---|---|
| Ubah threshold alert pakan menipis | `sqlite3 dashboard/feeder.db "UPDATE devices SET low_feed_threshold_pct = 25 WHERE device_code = 'feeder01';"` |
| Kalibrasi ulang sensor ultrasonik | `sqlite3 dashboard/feeder.db "UPDATE devices SET sensor_full_cm = 5.00, sensor_empty_cm = 30.00 WHERE device_code = 'feeder01';"` |
| Tambah jadwal pakan | `sqlite3 dashboard/feeder.db "INSERT INTO schedules (device_id, name, feed_time, portions) SELECT id, 'Pakan Malam', '21:00:00', 1 FROM devices WHERE device_code = 'feeder01';"` |
| Lihat log aplikasi | terminal tempat `python run.py` dijalankan |
| Ubah port broker / pakai broker eksternal | `dashboard/.env` → `EMBED_BROKER`, `BROKER_BIND`, `MQTT_URL` |

> Bisa juga mengubah threshold dari dashboard: tab **Control → set_threshold** (mengubah
> ambang di database sekaligus mengirim perintah ke device).

## Topik MQTT (referensi cepat)

| Topik | Arah | Isi |
|---|---|---|
| `feeder/<device>/telemetry` | device → platform | `{ "distance_cm": 10, "state": "idle" }` |
| `feeder/<device>/status` | device → platform | `online` / `offline` (retained) |
| `feeder/<device>/command` | platform → device | `{ "command_id": "...", "type": "manual_feed", "payload": { "portions": 2 } }` |
| `feeder/<device>/ack` | device → platform | `{ "command_id": "...", "result": "ok", "message": "feeding" }` |

## Reset total (kalau data uji mau dibuang)

```bash
rm -f dashboard/feeder.db dashboard/feeder.db-wal dashboard/feeder.db-shm
# lalu start ulang: skema + seed dibuat otomatis dari database/schema.sql
```
