# fish-feeder

ESP32 Aquaponic Autofeeder — MQTT-based communication layer and local prototype.

This repo holds the protocol foundation phase of the project: a local MQTT broker
(Mosquitto), a Node.js device simulator, and a Node-RED visual flow that together prove
bidirectional publish/subscribe before the real ESP32 firmware is written.

## Architecture

```
[ESP32 autofeeder] ──WiFi──┐
[node-RED simulator] ─────┤
[your platform/dashboard] ─┴──► Mosquitto Broker (:1883) ◄── Node-RED editor (:1880)
```

- **Mosquitto** — MQTT broker on `:1883` (local), handles device ↔ platform traffic
- **`sim.js`** — Node.js simulator that mimics the ESP32: stable client id, command
  subscription, periodic telemetry, feed-level tracking, manual-feed acks
- **Node-RED** — visual flow editor / alternate simulator on `:1880` (flows in `flows.json`)

## MQTT topic tree (device namespace, `feeder01` = device ID)

```
feeder/<device>/state       device → platform  full state snapshot (schedule, RTC, feed level)
feeder/<device>/telemetry   device → platform  periodic status ticks
feeder/<device>/status      LWT: online/offline
feeder/<device>/command     platform → device  all commands (manual feed, set schedule, sync RTC)
feeder/<device>/ack         device → platform  command acknowledgement
```

Messages are JSON; every command carries a `command_id` so acks can be matched.
Command types: `manual_feed`, `set_schedule`, `set_rtc`, `get_state`.

## Quick start

```bash
# 1. Broker (Homebrew service, auto-starts on boot)
brew services start mosquitto
lsof -iTCP:1883 -sTCP:LISTEN

# 2. Simulator needs Node v22 (nvm)
nvm use 22
node /Users/macbookpro/Documents/TA-UPH/sim.js

# 3. Node-RED (separate terminal)
node-red        # editor → http://localhost:1880
```

Verify the round trip from a third terminal:

```bash
mosquitto_sub -t 'feeder/#' -v &
mosquitto_pub -t 'feeder/nodered-sim/command' \
  -m '{"command_id":"t1","type":"manual_feed","payload":{"portions":2}}'
```

Expected: the simulator acks `{"result":"ok","message":"feeding 2 portions"}`.

## Docs

| File | Purpose |
|------|---------|
| `STARTUP_GUIDE.md` | Step-by-step resume after reboot, verification, troubleshooting |
| `MQTT_FOUNDATION_PLAN.md` | Phase plan: broker setup, protocol tests, message schema design |

## Environment notes

- Intel Mac (i7-8569U), macOS, Homebrew at `/usr/local`
- Node: system v24, but `sim.js` runs under Node **v22.23.2** (nvm)
- Docker not required — Homebrew/npm cover everything
- Ports 1883 (MQTT) and 1880 (Node-RED)