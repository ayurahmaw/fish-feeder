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

### Deploy ke Streamlit Community Cloud

Cloud menjalankan `streamlit run <main file>` dari root repo, bukan `run.py`
(jadi broker/worker baru menyala saat halaman pertama dibuka — tetap berfungsi).

- Main file path: **`dashboard/app.py`**
- Python: **3.12–3.14**
- Dependensi: `requirements.txt` di root repo (bukan `Pipfile`)
- Konfigurasi: panel **Secrets** (contoh: `.streamlit/secrets.toml.example`),
  karena `.env` tidak ikut ter-deploy
- Broker: `EMBED_BROKER="false"` + `MQTT_URL` publik/ber-auth, dan
  `MQTT_TOPIC_PREFIX="feeder-ayurahmaw"` (samakan dengan firmware/simulator)
- Riwayat DB: filesystem Cloud sementara — gunakan **Data & backup** di sidebar
  untuk mengunduh/memulihkan `feeder.db`

Detail langkah ada di README root bagian *Deploy ke Streamlit Community Cloud*.

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
pipenv run python cli.py servo_test feeder01 '{"angle":90}'   # 0 atau 90 derajat
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

## Halaman

| Halaman | Isi |
|---|---|
| **Status** | Level hopper, empat metric (jarak, state, koneksi, terakhir terlihat), jadwal berikutnya, aktivitas pakan terakhir, aksi cepat |
| **Live** | Grafik telemetry 1/6/24 jam + ambang, daftar pesan MQTT terbaru (filter + jeda) |
| **Notifikasi** | Ringkasan belum dibaca/peringatan/kritis, filter, tandai dibaca per item atau semua |
| **Riwayat** | Riwayat pakan 7 hari terakhir, ringkasan sukses/gagal/porsi, filter status |
| **Jadwal** | Tambah/ubah/hapus jadwal, aktif–nonaktif, status sinkronisasi mengikuti status device, kirim `set_schedule` |
| **Kontrol** | `manual_feed` (dengan konfirmasi), `get_state`, `set_threshold`, `set_rtc`, tes servo `servo_test` (0°/90°), log perintah |

Halaman Status dan Live menyegarkan diri tiap 2 detik (`st.fragment`); halaman
lain diperbarui saat berinteraksi.

## Tampilan & bahasa

- **Tema**: `.streamlit/config.toml` memakai palet prototipe (kanvas `#f4f7f6`,
  aksen `#087f70`, sidebar navy `#0c2927`, font DM Sans + Manrope).
- **Bahasa**: toggle **ID / EN** di sidebar; default Bahasa Indonesia. Semua
  teks UI ada di `i18n.py`.
- **Logo**: `assets/brand.svg`. Sentuhan visual tambahan (kartu, gradasi hero)
  ada di `assets/theme.css` dengan selector berbasis `key`.
- Grafik memakai Altair (sudah termasuk di Streamlit), bukan komponen
  tambahan.

## Database

File SQLite dibuat otomatis dari `../database/schema.sql` saat pertama kali
start. Untuk melihat isinya:

```bash
sqlite3 feeder.db "SELECT * FROM v_device_status;"
sqlite3 feeder.db "SELECT type, severity, message, created_at FROM notifications ORDER BY created_at DESC LIMIT 5;"
```

## Struktur

```
app.py           # router + sidebar/topbar + tema
app_pages/       # status, live, alerts, history, schedules, control
actions.py       # dialog konfirmasi pakan + helper kirim perintah
data.py          # query baca ber-cache (ttl 2-5 s)
ui.py            # badge, metric card, hopper, grafik, format waktu
i18n.py          # kamus ID/EN
assets/          # brand.svg, theme.css
```
