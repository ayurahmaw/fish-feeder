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
- **`sim.js`** — stands in for the ESP32: stable client id, birth/LWT, periodic telemetry,
  feed-level tracking, manual-feed acks.
- **`database/`** — SQLite schema + example queries.
- **Node-RED** — alternative visual simulator (`flows.json`), connects to the same broker.

There is **no external service**: no mosquitto, no MySQL. The broker and the database both run
inside the app process. (If port 1883 is already taken by a mosquitto you have running, the app
detects it and uses that broker instead.)

## MQTT topic tree (device namespace, `feeder01` = device ID)

```
feeder/<device>/state       device → platform  full state snapshot (schedule, RTC, feed level)
feeder/<device>/telemetry   device → platform  periodic status ticks
feeder/<device>/status      LWT: online/offline (retained)
feeder/<device>/command     platform → device  all commands (manual feed, set schedule, sync RTC)
feeder/<device>/ack         device → platform  command acknowledgement
```

Messages are JSON; every command carries a `command_id` so acks can be matched.
Command types: `manual_feed`, `set_schedule`, `set_threshold`, `set_rtc`, `get_state`.
See `DEVICE_PROTOCOL.md` for the full contract.

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

## Docs

| File | Purpose |
|------|---------|
| `STARTUP_GUIDE.md` | Step-by-step resume after reboot, verification, troubleshooting |
| `DEVICE_PROTOCOL.md` | The contract the ESP32 firmware must implement |
| `DATABASE_PLAN.md` | Database design (tables, view, alert rules) |
| `MQTT_FOUNDATION_PLAN.md` | Phase plan: broker setup, protocol tests, message schema design |
| `CHEATSHEET.md` | Daily operational commands |
| `dashboard/README.md` | How the app is put together and how to run it |

## Environment notes

- Intel Mac (i7-8569U), macOS, Homebrew at `/usr/local`
- Python 3.14 with Pipenv (see `dashboard/Pipfile`); Streamlit + amqtt + paho-mqtt + pandas
- Node: system v24, but `sim.js` runs under Node **v22.23.2** (nvm)
- Docker not required
- Ports: 1883 (MQTT broker, in-app) and 8501 (dashboard)
