# esp32_feeder — ESP32 firmware for the autofeeder

Arduino IDE sketch for the ESP32-WROOM-32 DevKit V1 (30-pin) side of the aquaponic autofeeder.
It implements the device contract in `CONTEXT.md` §10 and talks to the Streamlit platform's
embedded MQTT broker.

## Libraries (Arduino IDE → Library Manager)

| Library | Author | Version |
|---|---|---|
| `PubSubClient` | Nick O'Leary | 2.8+ |
| `ArduinoJson` | Benoit Blanchon | **7.x** |
| `RTClib` | Adafruit | 2.1+ |
| `LiquidCrystal I2C` | Frank de Brabander | 1.1+ |
| `ESP32Servo` | Kevin Harrington / John K. Bennett | 0.13+ |

Board core: **esp32 by Espressif** (Boards Manager URL
`https://espressif.github.io/arduino-esp32/package_esp32_index.json`), then select
**Tools → Board → ESP32 Dev Module**.

## Wiring

| Module | Module pin | Goes to | Note |
|---|---|---|---|
| SG90 | signal (orange) | **GPIO 13** | |
| SG90 | VCC (red) | **5 V** (`VIN` or external 5 V) | never 3.3 V; stall current ~700 mA |
| SG90 | GND (brown) | GND | common ground |
| HC-SR04 | VCC | 5 V (`VIN`) | |
| HC-SR04 | TRIG | **GPIO 5** | |
| HC-SR04 | ECHO | **GPIO 18** | **5 V output → resistor divider required** |
| HC-SR04 | GND | GND | |
| LCD1602 (PCF8574) | SDA | **GPIO 21** | 3.3 V VCC |
| LCD1602 (PCF8574) | SCL | **GPIO 22** | address `0x27` or `0x3F`, auto-detected |
| DS3231 | SDA | **GPIO 21** | same bus, address `0x68` |
| DS3231 | SCL | **GPIO 22** | 3.3 V VCC |

ECHO divider: `ECHO —[1 kΩ]—+— GPIO 18`, and `+ —[2 kΩ]— GND`. That drops 5 V to ~3.3 V.

Powering the servo from `VIN` works when the board is on USB, but a moving SG90 can brown out the
ESP32. For a stable prototype use a separate 5 V supply with a shared ground and a 470–1000 µF
capacitor across the servo's VCC/GND.

## Configure

Machine-specific settings (WiFi + broker address) live in `secrets.h`, which is **gitignored**:

```bash
cp secrets.h.example secrets.h
```

```cpp
// secrets.h
#define WIFI_SSID "…"
#define WIFI_PASS "…"
#define MQTT_HOST "broker.hivemq.com"   // deployed app's broker
// Local run instead: the Mac's LAN address (`ipconfig getifaddr en0`)
```

For an authenticated + TLS broker (e.g. HiveMQ Cloud free), also uncomment:

```cpp
#define MQTT_PORT 8883
#define MQTT_USE_TLS 1
#define MQTT_USER "…"
#define MQTT_PASS "…"
```

Everything else stays in `config.h` (pins, calibration, timings), including
`DEVICE_ID_OVERRIDE` — empty derives the id from the MAC (`feeder-64008c`) — and
`TOPIC_PREFIX`, which defaults to `feeder-ayurahmaw`. Keep `TOPIC_PREFIX` equal to the app's
`MQTT_TOPIC_PREFIX` secret. Topic examples in this README use `feeder/`; the sketch publishes
under `feeder-ayurahmaw/` unless you change it.

For a local broker, `MQTT_HOST` must be the Mac's current Wi-Fi address — DHCP changes it (this
machine moved from `.83` to `.85` during setup, which silently breaks the connection). Either
re-check with `ipconfig getifaddr en0` after every reconnect, or give the Mac a DHCP reservation
in the router.

### Device id

By default the id comes from the chip itself, not from the sketch: the last 3 bytes of the STA
MAC, e.g. MAC `20:43:a8:64:00:8c` → device id **`feeder-64008c`**, topics
`feeder/feeder-64008c/…`, MQTT clientId `feeder-64008c`. Two boards flashed with the same binary
get different ids automatically; it survives reflashing, and the dashboard device picker shows it.

The boot log prints it as `[id] device=…`. The platform auto-creates the matching `devices` row on
first contact (`db.ensure_device`), with the default calibration 3/17 cm and threshold 20 %.

If you want to keep an existing device row (its history, schedules and calibration), rename the
row instead of letting a second one appear — `device_id` foreign keys are untouched:

```bash
sqlite3 dashboard/feeder.db \
  "UPDATE devices SET device_code = 'feeder-64008c' WHERE device_code = 'feeder01';"
```

Set `DEVICE_ID_OVERRIDE` to a literal (e.g. `"feeder01"`) to pin the old behaviour.

Keep `HOPPER_FULL_CM` / `HOPPER_EMPTY_CM` in sync with the `devices` row (both ship as 3.0 and
17.0 cm). The dashboard can also be updated to match:

```bash
sqlite3 dashboard/feeder.db \
  "UPDATE devices SET sensor_full_cm = 3.0, sensor_empty_cm = 17.0 WHERE device_code = '<device-id>';"
```

## Flash

1. Open `esp32_feeder.ino` in the Arduino IDE (the whole folder is the sketch).
2. Select the board and the serial port.
3. **Verify**, then **Upload** (hold `BOOT` if it never syncs, tap `EN` to run).
4. Serial monitor at **115200**: `[i2c]` → `[servo]` → `[rtc]` → `[lcd]` → `[wifi] hasil scan` →
   `[mqtt] tersambung, birth online`.

On this board the CH340 bridge does **not** hold 921600 baud: set **Tools → Upload Speed →
115200**. Sync also fails intermittently (`No serial data received`, `termios error`) — just hit
Upload again, it usually syncs on the second or third try.

## What the firmware does

**Publishes**

| Topic | Payload |
|---|---|
| `feeder/<device-id>/status` | `online` (retained birth); LWT `offline` (retained) registered at connect |
| `feeder/<device-id>/telemetry` | `{"device","state","distance_cm","feed_level_pct","ts"}` every 15 s (`distance_cm` omitted when the sensor reading is invalid) |
| `feeder/<device-id>/ack` | `{"command_id","result","message","ts"}` — one for **every** command |
| `feeder/<device-id>/state` | `{"event":"scheduled_feed","portions","feed_time","distance_cm","ts"}` after a local scheduled feed |

**Subscribes** `feeder/<device-id>/command` and ignores everything else (the embedded broker can
deliver retained messages of other topics).

**Command handling**

| `type` | Behaviour | ack |
|---|---|---|
| `manual_feed` | queues `portions` (1–10) on the servo gate | after the last portion: `ok`, `error_busy`, `error_servo`, `error_low_level` |
| `servo_test` | drives the gate to `payload.angle` (only `0` or `90`; a wiring/mechanics check, not gated by the hopper level) | `ok` / `error_bad_payload` / `error_busy` / `error_servo` |
| `set_schedule` | stores up to 8 schedules in NVS, replaces the previous set | `ok` / `error_bad_payload` |
| `set_threshold` | stores `threshold_pct` in NVS | `ok` / `error_bad_payload` |
| `set_rtc` | local wall-clock `YYYY-MM-DDTHH:MM:SS` → DS3231 (falls back to a RAM clock) | `ok` |
| `get_state` | compact JSON snapshot in `message` | `ok` |

A **portion** = open the gate (`PORTION_OPEN_MS`), close it, settle (`SERVO_SETTLE_MS`), then wait
`PORTION_GAP_MS` before the next portion. Tune in `config.h`.

Schedules run **on the device**: once the RTC is valid, each stored `feed_time` fires within the
first 60 seconds of its minute, at most once per calendar day (tracked in NVS), and is skipped when
the hopper reads empty. A completed scheduled feed is reported on the `state` topic so the
dashboard History tab records it as *Terjadwal*.

## Time keeping

- **Boot:** the DS3231 time is used immediately — serial prints `[rtc] waktu boot dari RTC: …`
  and the LCD holds it for 3 s. Without a valid RTC the clock waits for NTP.
- **WiFi connect:** SNTP asks `NTP_SERVER` (`pool.ntp.org`) for UTC. The result is shifted by
  `NTP_UTC_OFFSET_SEC` (default WIB, UTC+7), written to the DS3231 as the backup clock, logged as
  `[ntp] waktu tersinkron: … -> RTC`, and shown on the LCD for 4 s. It re-syncs on every reconnect.
- **Fallback:** if NTP is unreachable the DS3231 (or the RAM clock when it is absent) keeps running,
  so schedules and the dashboard still see time. `set_rtc` from the dashboard overrides until the
  next NTP sync.

## Degraded mode

Every peripheral is optional. With only the ESP32 attached the sketch still connects, publishes
telemetry with `"state":"error"` (no distance), answers every command, and never reboots. Add the
sensors one at a time and reboot to pick them up.

| Missing | Effect |
|---|---|
| HC-SR04 | no `distance_cm`; dashboard level stays unknown; `manual_feed` is allowed (no low-level guard) |
| SG90 | `manual_feed` → `error_servo`; schedules skipped and marked fired for the day |
| DS3231 | `set_rtc` still works but the clock dies on reboot; schedules run only after a `set_rtc` |
| LCD1602 | silent; everything else works |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Serial shows `[mqtt] connect gagal rc=-2` | wrong `MQTT_HOST`, broker not running, or macOS firewall blocking 1883 |
| Dashboard never shows *online* | the derived id differs from the row you expect (check the `[id] device=` line), or `sim.js` is running with the same client id |
| `sim.js` + ESP32 both running | both use clientId `feeder01` → they keep kicking each other; run only one |
| Commands stay `sent` then `timeout` | firmware not subscribed, or the ack was dropped — check serial `[ack]` lines |
| Distance always invalid | ECHO not divided down / TRIG-ECHO swapped / sensor on 3.3 V |
| ESP32 reboots when the servo moves | servo on 3.3 V or weak 5 V — use an external supply with a shared ground |
| LCD blank | backlight pot on the PCF8574 backpack, wrong address (scan prints it), or SDA/SCL swapped |
| Clock resets on power loss | DS3231 backup cell missing or dead (CR2032) |
