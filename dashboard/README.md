# Feeder Platform (Streamlit)

Satu aplikasi Python yang menjalankan **seluruh** platform pakan otomatis:
broker MQTT, database, pengolahan pesan device, alert, dan dashboard-nya.

```
sim.js / ESP32 ──┐
                 ├──► broker MQTT :1883 ──► worker ──► SQLite (feeder.db)
Node-RED ────────┘        (di dalam app)      │
                                              └──► dashboard :8501
```

Tidak ada service eksternal: broker ditanam dengan `amqtt`, database memakai
SQLite bawaan Python. Yang perlu jalan di luar aplikasi hanya sisi device
(`sim.js` sekarang, ESP32 nanti).

## Menjalankan

```bash
cd dashboard

pipenv install          # sekali saja
pipenv shell
python run.py           # → http://localhost:8501
```

Lalu di terminal lain jalankan device simulator (butuh Node v22):

```bash
node /Users/macbookpro/Documents/TA-UPH/sim.js
```

`run.py` menyalakan broker + worker dulu, baru menyerahkan prosesnya ke
Streamlit — jadi `sim.js` bisa langsung connect tanpa menunggu browser dibuka.
`streamlit run app.py` juga bisa, tapi dengan cara itu platform baru menyala
saat halaman pertama kali dibuka.

## Kirim perintah dari CLI

```bash
pipenv run python cli.py manual_feed feeder01 '{"portions":2}'
pipenv run python cli.py get_state feeder01
pipenv run python cli.py set_threshold feeder01 '{"threshold_pct":25}'
```

Aplikasi Streamlit harus sedang berjalan (dialah yang menjalankan broker dan
memproses ack).

## Konfigurasi

Semua lewat environment variable / `.env` — lihat `.env.example`.
Yang penting:

| Variabel | Arti |
|---|---|
| `EMBED_BROKER` | `true` (default) = broker dijalankan di dalam app. `false` = pakai broker eksternal di `MQTT_URL`. |
| `MQTT_URL` | Alamat broker. Kalau port `1883` sudah dipakai (mis. mosquitto jalan), app otomatis memakai broker yang sudah ada itu. |
| `DB_PATH` | Lokasi file SQLite (default `dashboard/feeder.db`). |
| `COMMAND_TIMEOUT_SEC` | Perintah tanpa ack selama ini ditandai `timeout`. |

## Tab

| Tab | Isi |
|---|---|
| **Status** | Sisa pakan (%), jarak sensor, state, online, plus badge alert |
| **Live** | Grafik telemetry + daftar pesan MQTT terbaru |
| **Alerts** | Notifikasi (`feed_low`, `feed_empty`, `feed_failed`, `device_offline`) |
| **History** | Riwayat pemberian pakan |
| **Schedules** | Lihat / tambah / aktif-nonaktif jadwal, kirim `set_schedule` |
| **Control** | Pakan manual, `get_state`, `set_threshold`, `set_rtc` |

## Database

File SQLite dibuat otomatis dari `../database/schema.sql` saat pertama kali
start. Untuk melihat isinya:

```bash
sqlite3 feeder.db "SELECT * FROM v_device_status;"
sqlite3 feeder.db "SELECT type, severity, message, created_at FROM notifications ORDER BY created_at DESC LIMIT 5;"
```
