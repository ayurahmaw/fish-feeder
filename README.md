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
- Tidak ada `packages.txt` — app tidak butuh paket sistem, dan Cloud
  memperlakukan setiap baris file itu sebagai nama paket apt (komentar pun
  dianggap paket).

Langkah:

1. Push repo ke GitHub.
2. Buka <https://share.streamlit.io> → **New app** → pilih repo & branch `main`.
3. **Main file path**: `dashboard/app.py`.
4. **Advanced settings** → Python **3.12–3.14** (3.14 cocok dengan lock lokal).
5. **Secrets** — tempel isi `.streamlit/secrets.toml.example` (lihat catatan).
6. **Deploy**.

Catatan Cloud:

- **Broker**: `EMBED_BROKER="false"`, `MQTT_URL="mqtt://broker.hivemq.com:1883"`,
  `MQTT_TOPIC_PREFIX="feeder-ayurahmaw"`. Device **tidak** connect ke URL Streamlit
  — Cloud tidak bisa menerima koneksi MQTT masuk, jadi app dan device bertemu di
  broker yang sama.
- `sim.js` dan firmware memakai broker + prefix yang sama secara default. Kalau
  prefix diganti, ubah juga `MQTT_TOPIC_PREFIX` di Cloud secrets dan `TOPIC_PREFIX`
  di `firmware/esp32_feeder/config.h`.
- **Keamanan**: broker publik `broker.hivemq.com` bersifat anonim. Untuk demo yang
  lebih aman pakai broker ber-auth + TLS (mis. HiveMQ Cloud free): isi
  `MQTT_URL="mqtts://<cluster>:8883"`, `MQTT_USERNAME`, `MQTT_PASSWORD`,
  `MQTT_TLS="true"` di Cloud; di firmware isi `MQTT_PORT 8883`, `MQTT_USE_TLS 1`,
  `MQTT_USER`, `MQTT_PASS` pada `secrets.h`.
- **Data**: filesystem Cloud sementara. Buka sidebar **Data & backup** →
  **Unduh database** sebelum redeploy, lalu unggah file `.db` untuk memulihkan
  riwayat. Tanpa restore, `feeder.db` dibuat ulang dan di-seed setiap restart.

## Docs

**`CONTEXT.md` is the single source of truth** — the full PRD: requirements (FR/NFR), MQTT
protocol contract, database design, all flowcharts/sequence diagrams, traceability matrix,
timeline, risks, and operational commands.

| File | Purpose |
|------|---------|
| **`CONTEXT.md`** | The complete PRD (requirements + design + flows + ops) |
| `dashboard/README.md` | How the app is put together and how to run it |
| `database/schema.sql` · `database/example_queries.sql` | Executable schema + example queries |
| **`docs/design-report/`** | The full design document (LaTeX → PDF) and all diagram assets |

### Design report — `docs/design-report/`

A standalone design document for the whole system: hardware, firmware, MQTT contract,
database and dashboard, with 22 figures and 26 tables. Indonesian prose, English
diagram labels. Built from source, not exported from a word processor.

```
docs/design-report/
├── out/laporan-desain-sistem.pdf     ← read this (59 pp, cover + TOC)
├── out/lampiran-desain-sistem.pdf    ← appendix mode (55 pp, figures A.1, B.1, …)
├── main-standalone.tex               ← entry point: full document
├── main-appendix.tex                 ← entry point: appendix numbering, no cover
├── report-body.tex                   ← shared body, used by both entry points
├── preamble/{packages,colors,facts,macros}.tex
├── chapters/01-pendahuluan … 09-catatan-asumsi.tex
├── assets/diagrams/src/*.mmd         ← Mermaid sources (flowcharts, sequences, ER)
├── assets/diagrams/svg/*.svg         ← rendered, drag into Word/Slides/Docs
├── assets/diagrams/pdf/*.pdf         ← rendered, what LaTeX includes
├── assets/tikz/*.tex                 ← TikZ/Circuitikz sources
├── assets/tikz/pdf/*.pdf             ← rendered, drag into Word/Slides/Docs
├── assets/tikz/png/*.png             ← 1600 px previews
├── bin/{bootstrap-tools,render-diagrams,build,verify-facts}.sh
├── Makefile · BUILD_NOTES.md · FACTS.md
```

Every diagram is editable at its source (`.mmd` or `.tex`) and every rendered asset is
committed — no build folder to reproduce before you can see a picture.

| Figure | Where |
|---|---|
| Hardware block diagram, schematic/wiring, pin assignment | `assets/tikz/` (Bab 3) |
| Firmware: complete flow, gate state machine, timing, MQTT lifecycle, scheduled feed | `assets/tikz/fw-flow-overview.tex` + `assets/diagrams/src/fw-*` (Bab 4) |
| Website: page flow, bootstrap, command lifecycle, 6 sequences, broker choice | `assets/diagrams/src/web-*` (Bab 5) |
| Database: ER diagram + relational schema with PK/FK | `assets/diagrams/src/db-er.mmd` + `assets/tikz/db-relational-schema.tex` (Bab 7) |
| End-to-end: topology and full sequence | `assets/diagrams/src/e2e-*` (Bab 2, 8) |

Rebuild it:

```bash
cd docs/design-report
make tools      # once: TinyTeX (user-level, no sudo) + mermaid-cli
make            # render diagrams → build both PDFs → verify facts
```

`make` needs network only for the one-time `make tools`. `bin/verify-facts.sh` fails the
build when a pin, timing or calibration value in the document drifts from
`firmware/esp32_feeder/config.h`, so the text cannot silently disagree with the code.

The former docs (`STARTUP_GUIDE.md`, `DEVICE_PROTOCOL.md`, `DATABASE_PLAN.md`, `CHEATSHEET.md`,
`MQTT_FOUNDATION_PLAN.md`, `dashboard/*FLOWCHART*.md`) are archived stubs pointing into `CONTEXT.md`.

## Environment notes

- Intel Mac (i7-8569U), macOS, Homebrew at `/usr/local`
- Python 3.14 with Pipenv (see `dashboard/Pipfile`); Streamlit + amqtt + paho-mqtt + pandas
- Node: system v24, but `sim.js` runs under Node **v22.23.2** (nvm)
- Docker not required
- Ports: 1883 (MQTT broker, in-app) and 8501 (dashboard)
