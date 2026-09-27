# Startup Guide — Resuming the fish-feeder project after a reboot

Use this whenever the machine was turned off and you want to pick the project back up.
Everything runs locally on this Mac (Intel, Homebrew at `/usr/local`).

---

## Yang perlu jalan

Hanya **dua** hal:

1. **Aplikasi platform** — broker MQTT + database SQLite + dashboard, semuanya di dalam satu
   proses Python (`dashboard/run.py`).
2. **Simulator device** (`sim.js`) — nanti diganti ESP32.

Tidak ada mosquitto, tidak ada MySQL, tidak ada service yang perlu di-start lebih dulu.

---

## Quick reference (semua perintah, berurutan)

```bash
# Terminal 1 — platform
cd /Users/macbookpro/Documents/TA-UPH/dashboard
pipenv install          # hanya pertama kali / setelah Pipfile berubah
pipenv shell
python run.py           # → http://localhost:8501

# Terminal 2 — simulator (butuh Node v22)
nvm use 22
node /Users/macbookpro/Documents/TA-UPH/sim.js
```

---

## Step-by-step

### Step 1 — Jalankan platform (terminal 1)

```bash
cd /Users/macbookpro/Documents/TA-UPH/dashboard
pipenv install
pipenv shell
python run.py
```

Yang diharapkan di log:

```
[feeder] broker tertanam berjalan di 0.0.0.0:1883
[feeder] worker terhubung & subscribe: feeder/+/telemetry  feeder/+/ack  feeder/+/status
[feeder] runtime siap — broker: embedded (0.0.0.0:1883), db: .../dashboard/feeder.db
[feeder] platform siap — broker: embedded (0.0.0.0:1883)
```

Dashboard: **http://localhost:8501**

> Kalau port 1883 ternyata sudah dipakai (mis. mosquitto jalan sebagai service), aplikasi
> menulis `port 1883 sudah terpakai — memakai broker yang sudah jalan` dan memakai broker itu.
> Untuk mode tertanam penuh: `brew services stop mosquitto`.

### Step 2 — Jalankan simulator (terminal 2)

`sim.js` memuat library `mqtt` dari path Node **v22.23.2** yang di-hardcode, jadi ia harus
jalan di Node v22 (default sistem v24).

```bash
nvm use 22
node /Users/macbookpro/Documents/TA-UPH/sim.js
```

Output yang diharapkan (± 3 detik):

```
[sim] starting — broker mqtt://localhost:1883
[sim] CONNECTED as feeder01
[sim] SUBSCRIBED to feeder/feeder01/command
[sim] TX telemetry {"device":"feeder01","state":"idle","feed_level_pct":80,...}
```

### Step 3 — Verifikasi

Buka dashboard → tab **Status** (sisa pakan bergerak tiap 3 detik) dan **Live**.

Atau lewat CLI:

```bash
cd /Users/macbookpro/Documents/TA-UPH
sqlite3 -header -column dashboard/feeder.db "SELECT * FROM v_device_status;"
```

Uji tombol pakan manual:

```bash
cd dashboard
pipenv run python cli.py manual_feed feeder01 '{"portions":2}'
```

Cek hasilnya di `commands` / `feeding_logs` (status berubah `sent` → `success` setelah ack).

---

## Shutting down (clean)

`Ctrl+C` di kedua terminal. Tidak ada service yang perlu dimatikan.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `pipenv: command not found` | Pipenv belum terpasang: `pip3 install --user pipenv`. |
| Dashboard "terputus ⏳" di sidebar | Broker tidak jalan. Cek log terminal 1; pastikan tidak ada proses lain yang memegang port 1883. |
| `port 1883 sudah terpakai` | Berarti ada mosquitto/broker lain. Itu **tidak masalah** — aplikasi memakainya. Untuk mode tertanam: `brew services stop mosquitto`. |
| `sim.js` crash `Cannot find module ...node-red/.../mqtt` | Node versi salah. Jalankan dengan `nvm use 22`, atau langsung `~/.nvm/versions/node/v22.23.2/bin/node sim.js`. |
| `nvm: command not found` | nvm di-install lewat shell — buka terminal baru (atau `source ~/.nvm/nvm.sh`). |
| Data lama/aneh di dashboard | Reset: `rm -f dashboard/feeder.db*` lalu start ulang (skema + seed dibuat otomatis). |
| Perintah nyangkut `sent` | Device tidak membalas. Setelah 30 detik aplikasi menandainya `timeout` (sweep tiap 10 detik). |

---

## Where things live

| Item | Location |
|------|----------|
| Aplikasi (broker + DB + UI) | `/Users/macbookpro/Documents/TA-UPH/dashboard/` |
| Entry point | `dashboard/run.py` |
| Konfigurasi | `dashboard/.env` (contoh: `dashboard/.env.example`) |
| Database SQLite | `dashboard/feeder.db` (dibuat otomatis) |
| Skema database | `database/schema.sql` |
| Simulator | `/Users/macbookpro/Documents/TA-UPH/sim.js` |
| Node-RED flow | `/Users/macbookpro/Documents/TA-UPH/flows.json` (backup: `.flows.json.backup`) |
| Dokumen | `MQTT_FOUNDATION_PLAN.md`, `DEVICE_PROTOCOL.md`, `DATABASE_PLAN.md`, `CHEATSHEET.md` |

---

## Update log

- **2026-09-16** — Initial version. Steps: broker → Node v22 → simulator → Node-RED → verify.
- **2026-09-27** — Backend Node + MySQL digantikan satu aplikasi Python: broker MQTT tertanam
  (amqtt) + SQLite tertanam + dashboard Streamlit. Mulai sekarang hanya 2 terminal
  (`python run.py` dan `sim.js`), tanpa service eksternal.
