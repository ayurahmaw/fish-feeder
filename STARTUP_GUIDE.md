# Startup Guide — Resuming the fish-feeder project after a reboot

Use this whenever the machine was turned off and you want to pick the project back up.
Everything runs locally on this Mac (Intel, Homebrew at `/usr/local`).
Duration ≈ 2 minutes.

---

## Quick reference (all commands, in order)

```bash
# 1. Broker
brew services list | grep mosquitto        # if "stopped" → next line
brew services start mosquitto
lsof -iTCP:1883 -sTCP:LISTEN               # expect "mosquitto ... LISTEN"

# 2. Simulator needs Node v22 (nvm)
nvm use 22                                 # must print v22.x

# 3. Simulator (separate terminal)
node /Users/macbookpro/Documents/TA-UPH/sim.js

# 4. Node-RED (separate terminal)
node-red                                  # editor → http://localhost:1880
```

---

## Step-by-step

### Step 1 — Start the MQTT broker (Mosquitto)

The broker is installed as a Homebrew service, so it may already be running after boot.
Do not assume — always verify:

```bash
brew services start mosquitto    # safe to run even if already started
lsof -iTCP:1883 -sTCP:LISTEN     # should list "mosquitto ... LISTEN" on port 1883
```

If port 1883 is not listening, see Troubleshooting below.

### Step 2 — Switch Node to v22 (required for the simulator)

`sim.js` loads the `mqtt` library from a hardcoded Node **v22.23.2** path, so the
simulator only runs under Node v22. The system default is Node v24 — wrong version here.

```bash
nvm use 22     # expect: Now using node v22.x.x
```

### Step 3 — Start the simulator (one terminal)

```bash
node /Users/macbookpro/Documents/TA-UPH/sim.js
```

Expected output after ~3 s:

```
[sim] starting — broker mqtt://localhost:1883
[sim] CONNECTED as nodered-sim
[sim] SUBSCRIBED ...
[sim] TX telemetry {...}
```

Leave this terminal open.

### Step 4 — Start Node-RED (another terminal)

Node-RED is the visual flow editor / alternate simulator.

```bash
node-red
```

- Editor UI: **http://localhost:1880**
- The flow lives in `/Users/macbookpro/Documents/TA-UPH/flows.json`
- `mqtt in` / `mqtt out` nodes connect to `localhost:1883`, client id `nodered-sim`

(Optional) Node-RED 4.x officially supports Node 18/20/22. If it warns under Node 24,
run it under `nvm use 22` instead of the system default.

### Step 5 — Verify everything is talking

Quick round-trip check from a third terminal:

```bash
# watch the feed
mosquitto_sub -t 'feeder/#' -v &

# force a manual feed → simulator acks it
mosquitto_pub -t 'feeder/nodered-sim/command' -m '{"command_id":"t1","type":"manual_feed","payload":{"portions":2}}'
```

You should see the simulator print the ack `{"result":"ok","message":"feeding 2 portions"}`.
Also check the Node-RED debug pane on `http://localhost:1880`.

---

## Shutting down (clean)

Optional — you can also just turn the machine off; brew services auto-start on boot.

```bash
brew services stop mosquitto
# Ctrl+C in the sim.js and node-red terminals
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `lsof` shows nothing on 1883 | Broker isn't running: re-run `brew services start mosquitto`, then `lsof -iTCP:1883 -sTCP:LISTEN`. |
| `nvm: command not found` | nvm is shell-installed — reopen the terminal (or `source ~/.nvm/nvm.sh`). |
| `sim.js` crashes with `Cannot find module ...node-red/.../mqtt` | Wrong Node version or Node-RED global install changed. Reinstall: `npm install -g node-red` under the v22 that path references. |
| `sim.js` crashes with `T.commandese` / `text2010` is not defined | Known latent typos in `sim.js` (lines 49/67) — fix them to `T.command` / `text`. |
| `brew` errors about `compatibility_version` | Homebrew too old for the formula API. See Phase 1 of `MQTT_FOUNDATION_PLAN.md` (`brew update-reset` / re-run official installer). |

---

## Where things live

| Item | Location |
|------|----------|
| Broker config | `/usr/local/etc/mosquitto/mosquitto.conf` |
| Node-RED flow | `/Users/macbookpro/Documents/TA-UPH/flows.json` (backup: `.flows.json.backup`) |
| Simulator | `/Users/macbookpro/Documents/TA-UPH/sim.js` |
| Project docs | `/Users/macbookpro/Documents/TA-UPH/MQTT_FOUNDATION_PLAN.md` |

---

## Update log

- **2026-09-16** — Initial version. Steps: broker → Node v22 → simulator → Node-RED → verify.