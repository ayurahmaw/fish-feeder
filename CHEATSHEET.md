# Cheat Sheet Harian — Sistem Pakan Otomatis (feeder_db + backend)

> Referensi cepat operasional sehari-hari. Detail lengkap: `DATABASE_PLAN.md` (desain DB),
> `MQTT_FOUNDATION_PLAN.md` (protokol), `STARTUP_GUIDE.md` (setup dari nol).

## Start (3 terminal, atau tambahkan `&` untuk background)

```bash
# 1. Broker MQTT (sekali, berjalan sebagai service)
brew services start mosquitto

# 2. Backend — jembatan MQTT -> MySQL
node backend/index.js

# 3. Simulator device (ganti ESP32 nanti)
node sim.js
```

## Tombol pakan manual

```bash
node backend/send-command.js manual_feed feeder01 '{"portions":2}'
```

Contoh perintah lain:

```bash
node backend/send-command.js get_state feeder01
node backend/send-command.js set_threshold feeder01 '{"threshold_pct":25}'
```

## Stop

```bash
pkill -f "node index.js" ; pkill -f "node sim.js"
# broker (opsional, biarkan saja kalau sering dipakai)
brew services stop mosquitto
```

## Pantau data

```bash
# Status semua feeder: sisa pakan, online, flag alert
mysql -u feeder_app -pfeeder_dev_123 feeder_db -e "SELECT * FROM v_device_status;"

# Notifikasi/alert terbaru
mysql -u feeder_app -pfeeder_dev_123 feeder_db \
  -e "SELECT type, severity, message, created_at FROM notifications ORDER BY created_at DESC LIMIT 5;"

# History pemberian pakan
mysql -u feeder_app -pfeeder_dev_123 feeder_db \
  -e "SELECT requested_at, trigger_type, portions, status, message FROM feeding_logs ORDER BY requested_at DESC LIMIT 10;"

# Jadwal aktif
mysql -u feeder_app -pfeeder_dev_123 feeder_db \
  -e "SELECT name, feed_time, portions, is_active FROM schedules WHERE is_active = 1 ORDER BY feed_time;"
```

> Login mysql lain: root pakai `mysql -u root -p`, aplikasi pakai user `feeder_app`
> (password dev: `feeder_dev_123` — lihat `database/app_user.sql`).

## Konfigurasi umum

| Kegiatan | Perintah |
|---|---|
| Ubah threshold alert pakan menipis | `UPDATE devices SET low_feed_threshold_pct = 25 WHERE device_code = 'feeder01';` |
| Kalibrasi ulang sensor ultrasonik | `UPDATE devices SET sensor_full_cm = 5.00, sensor_empty_cm = 30.00 WHERE device_code = 'feeder01';` |
| Tambah jadwal pakan | `INSERT INTO schedules (device_id, name, feed_time, portions) VALUES (1, 'Pakan Malam', '21:00:00', 1);` |
| Log backend & simulator | `tail -f /var/folders/45/s3djh8_57hl4q328tvj_96h80000gn/T/opencode/backend.log` |

## Topik MQTT (referensi cepat)

| Topik | Arah | Isi |
|---|---|---|
| `feeder/<device>/telemetry` | device → platform | `{ "distance_cm": 10, "state": "idle" }` |
| `feeder/<device>/status` | device → platform | `online` / `offline` (retained) |
| `feeder/<device>/command` | platform → device | `{ "command_id": "...", "type": "manual_feed", "payload": { "portions": 2 } }` |
| `feeder/<device>/ack` | device → platform | `{ "command_id": "...", "result": "ok", "message": "feeding" }` |

## Reset total (kalau data uji mau dibuang)

```bash
mysql -u root -p -e "DROP DATABASE feeder_db;"
mysql -u root -p < database/schema.sql            # tabel + view + seed + user aplikasi
mysql -u root -p feeder_db < database/example_queries.sql   # opsional: data contoh
```
