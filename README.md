# fish-feeder

ESP32 Aquaponic Autofeeder — a local platform for the MQTT communication layer, storage
and monitoring, running entirely in one Python process before the real ESP32 firmware exists.

## Architecture

```
[ESP32 autofeeder] ──WiFi──┐
[node-RED simulator] ─────┤
[sim.js simulator] ───────┴──►  ┌──────────── dashboard/ (one Streamlit process) ───────────┐
                                │  MQTT broker :1883  →  worker  →  SQLite  →  dashboard :8501 │
                                └──────────────────────────────────────────────────────────────┘
```

- **`dashboard/`** — the whole platform: an embedded MQTT broker (`amqtt`), an MQTT worker that
  ingests device traffic, alert evaluation, ack correlation, the timeout sweeper, an embedded
  SQLite database, and the Streamlit monitoring/control UI.
- **`firmware/esp32_feeder/`** — Arduino IDE sketch for the real device: HC-SR04 level sensing,
  SG90 gate, DS3231 clock, LCD1602 status display, local schedules, full ACK coverage.
- **`sim.js`** — stands in for the ESP32: stable client id, birth/LWT, periodic telemetry,
  feed-level tracking, manual-feed acks.
- **`database/`** — SQLite schema + example queries.
- **Node-RED** — alternative visual simulator (`flows.json`), connects to the same broker.

There is **no external service**: no mosquitto, no MySQL. The broker and the database both run
inside the app process. (If port 1883 is already taken by a mosquitto you have running, the app
detects it and uses that broker instead.)

## MQTT topic tree (device namespace, `<device>` = `devices.device_code`)

The ESP32 derives its device id from its factory MAC (`feeder-64008c`, printing
`[id] device=…` at boot), so several boards can share one binary. `sim.js` still uses the
seeded `feeder01`.

```
feeder/<device>/state       device → platform  device-initiated events (scheduled_feed)
feeder/<device>/telemetry   device → platform  periodic status ticks
feeder/<device>/status      LWT: online/offline (retained)
feeder/<device>/command     platform → device  all commands (manual feed, set schedule, sync RTC)
feeder/<device>/ack         device → platform  command acknowledgement
```

Messages are JSON; every command carries a `command_id` so acks can be matched.
The ESP32 runs the daily schedules itself and reports each execution on `state`, which is how
scheduled feeds reach the History tab (see `CONTEXT.md` §10.6).
Command types: `manual_feed`, `set_schedule`, `set_threshold`, `set_rtc`, `get_state`.
See `CONTEXT.md` §10 for the full contract.

## Quick start

```bash
# 1. Platform (broker + database + dashboard)
cd dashboard
pipenv install
pipenv shell
python run.py                 # → http://localhost:8501

# 2. Simulator, in a second terminal (needs Node v22)
node /Users/macbookpro/Documents/TA-UPH/sim.js
```

Send a command from the CLI:

```bash
cd dashboard
pipenv run python cli.py manual_feed feeder01 '{"portions":2}'
```

Inspect the database directly (plain file, no server):

```bash
sqlite3 dashboard/feeder.db "SELECT * FROM v_device_status;"
```

## Deploy ke Streamlit Community Cloud

Repo ini sudah disiapkan untuk Cloud:

- `requirements.txt` (root) — dependensi. Cloud tidak membaca `Pipfile`.
- `.streamlit/config.toml` (root) — tema, karena Cloud menjalankan app dengan
  CWD di root repo.
- `.streamlit/secrets.toml.example` — daftar secret yang bisa diisi lewat panel
  **Secrets** di Cloud (tanpa `.env`).
- `packages.txt` — kosong; tidak ada paket sistem yang dibutuhkan.

Langkah:

1. Push repo ke GitHub.
2. Buka <https://share.streamlit.io> → **New app** → pilih repo & branch `main`.
3. **Main file path**: `dashboard/app.py`.
4. **Advanced settings** → Python **3.12** atau **3.13** (bukan 3.14).
5. (Opsional) **Secrets** — tempel isi `.streamlit/secrets.toml.example`.
6. **Deploy**.

Catatan Cloud:

- Default `EMBED_BROKER=true` aman: broker berjalan di dalam container dan
  dashboard tetap tampil (data awal `feeder01` di-seed otomatis). Tapi device
  luar **tidak bisa** connect ke broker di dalam Cloud.
- Agar `sim.js` / ESP32 bisa mengirim data, set `EMBED_BROKER="false"` dan arahkan
  `MQTT_URL` ke broker yang bisa diakses publik (mis. `broker.hivemq.com`),
  lalu samakan `MQTT_TOPIC_PREFIX` di device.
- Filesystem Cloud bersifat sementara: `feeder.db` dibuat ulang dan di-seed
  setiap restart/redeploy.

## Docs

**`CONTEXT.md` is the single source of truth** — the full PRD: requirements (FR/NFR), MQTT
protocol contract, database design, all flowcharts/sequence diagrams, traceability matrix,
timeline, risks, and operational commands.

| File | Purpose |
|------|---------|
| **`CONTEXT.md`** | The complete PRD (requirements + design + flows + ops) |
| `dashboard/README.md` | How the app is put together and how to run it |
| `database/schema.sql` · `database/example_queries.sql` | Executable schema + example queries |

The former docs (`STARTUP_GUIDE.md`, `DEVICE_PROTOCOL.md`, `DATABASE_PLAN.md`, `CHEATSHEET.md`,
`MQTT_FOUNDATION_PLAN.md`, `dashboard/*FLOWCHART*.md`) are archived stubs pointing into `CONTEXT.md`.

## Environment notes

- Intel Mac (i7-8569U), macOS, Homebrew at `/usr/local`
- Python 3.14 with Pipenv (see `dashboard/Pipfile`); Streamlit + amqtt + paho-mqtt + pandas
- Node: system v24, but `sim.js` runs under Node **v22.23.2** (nvm)
- Docker not required
- Ports: 1883 (MQTT broker, in-app) and 8501 (dashboard)
