# MQTT Foundation Plan — ESP32 Aquaponic Autofeeder

Goal of this phase: stand up a local MQTT server + a simulator (Node-RED), and verify
bidirectional publish/subscribe — proving the ESP32 communication layer at the protocol
level before designing the full message schema.

---

## Phase 0 — Reference architecture

Everything runs on the local machine (macOS now, Linux later). The real ESP32 (later)
connects over the WiFi router to the machine's LAN IP.

```
[ESP32 autofeeder] ──WiFi──┐
[node-RED simulator] ─────┤
[your platform/dashboard] ─┴──► Mosquitto Broker (:1883) ◄── Node-RED editor (:1880)
```

---

## Phase 1 — Install & run MQTT broker (Mosquitto)

### Prerequisite: update Homebrew (BLOCKED currently)

**Symptom**

```
Error: openssl@3: undefined method `compatibility_version' for class Formulary::FormulaNamespace...
```

**Root cause**

Homebrew 4.3.24 (mid-2025) vs. current Homebrew formula API (Sep 2026).
The new API added a `compatibility_version` metadata field to every formula; brew 4.3.24
does not know it, so it crashes while loading ANY formula (`openssl@3` here). This affects
every `brew install`, not just mosquitto. Updating brew is a prerequisite for this whole phase.

**Fix**

```bash
brew update
brew install mosquitto
```

Fallbacks if `brew update` errors:

1. `brew update-reset` then retry `brew install mosquitto`.
2. Re-run the official installer (upgrades brew in place):

   ```bash
   sh -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

3. Broker-only fallback (no brew): official mosquitto.org macOS `.pkg`.
4. Everything-in-one fallback: `node-red-contrib-aedes` embeds an MQTT broker inside
   Node-RED — zero external dependencies, handy for pure-simulator dev.

### Broker setup (after install works)

- Config: `/usr/local/etc/mosquitto/mosquitto.conf` (Linux later: `/etc/mosquitto/`)
- Default config already listens on `:1883` with anonymous local access — no edits needed
- Install also provides CLI clients `mosquitto_pub` / `mosquitto_sub` for verification
- Start (auto-restarts on boot):

  ```bash
  brew services start mosquitto
  ```

- Verify listening:

  ```bash
  lsof -iTCP:1883 -sTCP:LISTEN
  ```

---

## Phase 2 — Install Node-RED as the device simulator

- Node-RED 4.x officially supports Node 18/20/22 (local env has Node v24 — may warn).
  If it fails to run, switch with nvm and reinstall:

  ```bash
  nvm install 22 && nvm use 22
  npm install -g node-red
  ```

- Start the server:

  ```bash
  node-red
  ```

- Editor: http://localhost:1880
- The `mqtt in` / `mqtt out` nodes ship with the core palette — no extra plugin needed
- Nodes used to simulate the ESP32: `inject`, `mqtt out`, `mqtt in`, `debug`

---

## Phase 3 — Verify bidirectional publish/subscribe

| Test | Sender | Receiver | Outcome |
|------|--------|----------|---------|
| A | `mosquitto_sub -t 'feeder/test/#'` | `mosquitto_pub` from terminal | Broker alive, CLI works |
| B | Node-RED `inject` → `mqtt out` | `mosquitto_sub` | Simulator → platform direction |
| C | `mosquitto_pub` | Node-RED `mqtt in` → `debug` | Platform → simulator direction |
| D | `mqtt in` → Function → `mqtt out` in Node-RED | debug pane | Full simulated round-trip |

Passing all four proves the ESP32 communication layer at the protocol level.

---

## Phase 4 — (Roadmap, AFTER comm is verified) MQTT topic & message design

### Topic tree (device-side namespace; `feeder01` = device ID)

```
feeder/feeder01/state       device → platform  full state snapshot (schedule, RTC, feed level)
feeder/feeder01/telemetry   device → platform  periodic status ticks
feeder/feeder01/status      LWT: online/offline (RTC / connectivity recovery hooks)
feeder/feeder01/command     platform → device  all commands (manual feed, set schedule, sync RTC)
feeder/feeder01/ack         device → platform  command acknowledgement
```

### Message = JSON, every command carries `command_id` for ack matching

Command (platform → device):

```json
{ "command_id": "f3a9", "type": "manual_feed", "payload": { "portions": 2 }, "timestamp": "2026-09-16T10:00:00+07:00" }
```

Ack (device → platform):

```json
{ "command_id": "f3a9", "result": "ok", "message": "feeding", "timestamp": "..." }
```

Command types: `manual_feed`, `set_schedule`, `get_state`, `set_rtc` (drives the auto
RTC-recovery feature). Future features slot in as new `type` values — no broker/design changes needed.

---

## Success criteria for this session

- Mosquitto broker running on `:1883`
- Node-RED running on `:1880`
- Verification Tests A–D all pass
- (Phase 4 design documented for later implementation)

---

## Environment notes

- Machine: Intel Mac (i7-8569U), macOS
- Homebrew: 4.3.24 at `/usr/local` (needs update — see Phase 1)
- Node v24.21.0, npm 11.19.0, Python 3.14.3, nvm present
- Docker: NOT installed (not required — brew/npm covers everything)
- Ports 1883 and 1880 confirmed free