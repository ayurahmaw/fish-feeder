# FACTS — nilai acuan untuk semua diagram dan bab

Berkas kerja internal (bukan bagian PDF). Setiap angka di sini sudah diverifikasi terhadap kode.
**Jangan mengarang nilai.** Kalau ragu, buka berkas sumber yang ditunjuk.

Sumber utama:
- `firmware/esp32_feeder/config.h`
- `firmware/esp32_feeder/esp32_feeder.ino`
- `firmware/esp32_feeder/net.cpp`, `hw.cpp`, `protocol.cpp`
- `dashboard/commands.py`, `handlers.py`, `mqtt.py`, `runtime.py`, `db.py`, `config.py`
- `database/schema.sql`

---

## 1. Identitas

| Item | Nilai |
|---|---|
| Firmware | `1.0.0` |
| Papan | ESP32-WROOM-32 DevKit V1, 30 pin |
| Inti Arduino | esp32 3.3.12, FQBN `esp32:esp32:esp32:UploadSpeed=115200`, `-Os` |
| Serial | 115200 baud |
| Prefix topik | `feeder-ayurahmaw` |
| Device id | `<prefix>-<3 byte MAC terakhir>`, contoh `feeder-64008c`; `DEVICE_ID_OVERRIDE` bisa memaksa |
| Device seed di DB | `feeder01` ("Feeder Kolam 1") |
| NVS namespace | `feeder` |

Topik lengkap = `feeder-ayurahmaw/<device_id>/<kind>`.

---

## 2. Pin (config.h)

| Makro | GPIO | Fungsi |
|---|---|---|
| `PIN_SERVO` | 13 | sinyal PWM SG90 |
| `PIN_TRIG` | 5 | trigger HC-SR04 |
| `PIN_ECHO` | 18 | echo HC-SR04 (lewat pembagi 1k/2k) |
| `PIN_SDA` | 21 | I²C SDA (DS3231 + LCD) |
| `PIN_SCL` | 22 | I²C SCL |

I²C: 100 kHz (tidak ada `Wire.setClock()`), alamat DS3231 `0x68`, LCD PCF8574 `0x27` (alternatif `0x3F`).

Pin yang **tidak dipakai**: 2, 4, 12, 14, 15, 16, 17, 19, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39.
Pin **terlarang**: 6–11 (flash SPI), 1/3 (UART0 ke CH340), 0/2/12/15 (boot strapping, 2 = LED onboard),
34–39 (input-only). 20/24/28–31 tidak ada di modul 30 pin.

---

## 3. Kalibrasi (config.h — acuan resmi)

- `HOPPER_FULL_CM` = **3.0**
- `HOPPER_EMPTY_CM` = **17.0**
- `MAX_DISTANCE_CM` = 40.0
- span = 14.0 cm
- `pct = (empty - d) / (empty - full) × 100`, dibatasi 0..100
- contoh: d = 3.0 cm → 100 %; d = 10.0 cm → 50 %; d = 17.0 cm → 0 %

Nilai lama 5.0/25.0 sudah **tidak dipakai** (dimigrasi 2026-11-19).

---

## 4. Timing (config.h)

| Makro | Nilai | Arti |
|---|---|---|
| `PORTION_OPEN_MS` | 1000 ms | gate terbuka per porsi |
| `SERVO_SETTLE_MS` | 300 ms | jeda setelah menutup gate |
| `PORTION_GAP_MS` | 200 ms | jeda antar porsi |
| `TELEMETRY_INTERVAL_MS` | 15000 ms | publish telemetry |
| `SENSOR_INTERVAL_MS` | 2000 ms | sampling HC-SR04 |
| `DISPLAY_INTERVAL_MS` | 500 ms | refresh LCD |
| `DISPLAY_PAGE_MS` | 4000 ms | ganti halaman LCD saat ada error |
| `MQTT_RETRY_MS` | 5000 ms | jeda percobaan connect |
| keepalive MQTT | 60 s | `setKeepAlive(60)` |
| socket timeout | 10 s | |
| `SCHEDULE_WINDOW_SEC` | 60 s | jendela eksekusi jadwal |
| `MAX_SCHEDULES` | 8 | |
| NTP min epoch | 1600000000 | |
| offset NTP | +25200 s (UTC+7, WIB) | |

Siklus per porsi = 1000 + 300 = **1300 ms**, plus 200 ms antar porsi.
N porsi ≈ N×1300 + (N−1)×200 ms → 1 porsi 1300 ms, 2 porsi 2800 ms, 10 porsi 14800 ms.

Servo: 50 Hz, pulsa 500–2400 µs, 0° = tutup, 90° = buka. SG90 stall ≈ 700 mA @ 5 V.

---

## 5. Buffer & NVS

- `MQTT_BUFFER_SIZE` = 1024 B
- `COMMAND_QUEUE_SIZE` = 4 (ring buffer, satu perintah di-pop per iterasi `loop()`)
- Reserve JSON: telemetry 256 B, state 256 B, ack 512 B
- `DEFAULT_THRESHOLD_PCT` = 20
- NVS keys: `threshold` (Int), `fireDate` (UInt, `y*10000+mo*100+d`), `fireMask` (UInt bitmask),
  `schedules` (String JSON array)

---

## 6. State machine gate (esp32_feeder.ino)

`enum FeedPhase { FEED_IDLE, FEED_OPEN, FEED_CLOSING, FEED_GAP }`

| Dari | Ke | Kondisi | Aksi |
|---|---|---|---|
| IDLE | OPEN | `feedStart()` dipanggil, `phase==IDLE`, servo siap | `servoOpen()`, `phaseAt=now` |
| OPEN | CLOSING | `now-phaseAt >= 1000` | `servoClose()`, `phaseAt=now` |
| CLOSING | GAP | `now-phaseAt >= 300` dan `--jobRemaining > 0` | `phaseAt=now` |
| CLOSING | IDLE | `now-phaseAt >= 300` dan `jobRemaining == 0` | `finishFeed()` |
| GAP | OPEN | `now-phaseAt >= 200` | `servoOpen()`, `phaseAt=now` |

`finishFeed()`: servo close → ukur jarak → kalau dijadwalkan, publish `state` (`scheduled_feed`) lalu
telemetry; kalau manual, publish telemetry lalu ack.

---

## 7. Main loop (tanpa `delay()`)

```
setup():
  Serial.begin(115200) — delay 300 ms
  hw::begin(): I2C scan, TRIG/ECHO, servo attach (closed), DS3231 probe, LCD probe 0x27→0x3F
  proto::begin(): NVS load threshold, fireDate, fireMask, schedules
  net::begin(): WiFi STA, device id dari MAC, hostname, scan, client.setServer, buffer 1024,
                keepAlive 60, socketTimeout 10, callback
  splash LCD 3000 ms, ukur jarak

loop():
  net::tick()
  (rising edge MQTT)  -> publishTelemetry()
  (rising edge WiFi)  -> ntpStart()
  commandTick()  1 perintah per iterasi
  ntpTick()
  feedTick()
  sensorTick()   2000 ms
  scheduleTick() 1000 ms
  telemetryTick() 15000 ms
  displayTick()  500 ms
```

---

## 8. Topik & payload

| Kind | Arah | Retain | QoS | Payload |
|---|---|---|---|---|
| `status` | device → platform | **ya** | 0 | string `online` (birth) / `offline` (LWT) |
| `telemetry` | device → platform | tidak | 0 | JSON |
| `ack` | device → platform | tidak | 0 | JSON |
| `state` | device → platform | tidak | 0 | JSON (`scheduled_feed`) |
| `command` | platform → device | tidak | 1 (subscribe) | JSON |

telemetry:
```json
{"device":"feeder-64008c","state":"idle","distance_cm":10.0,"feed_level_pct":50,"ts":"2026-11-19T13:00:00"}
```
`state` ∈ `idle|feeding|error` (`error` bila jarak invalid). Field dihilangkan bila tidak diketahui.

ack:
```json
{"command_id":"cmd-…","result":"ok","message":"feeding 2 portions","ts":"…"}
```
`result`: `ok`, `error_bad_payload`, `error_busy`, `error_servo`, `error_low_level`, `error_unknown_type`.

state:
```json
{"event":"scheduled_feed","device":"…","portions":2,"feed_time":"07:00:00","distance_cm":14.8,"ts":"…"}
```

command:
```json
{"command_id":"cmd-…","type":"manual_feed","payload":{"portions":2},"timestamp":"…"}
```

Tipe command dan ack yang diharapkan:

| type | payload | guard (urutan) | ack sukses |
|---|---|---|---|
| `servo_test` | `{"angle":0\|90}` | angle≠0/90 → `error_bad_payload`; sibuk → `error_busy`; servo mati → `error_servo` | `ok`, "servo 90 deg" |
| `manual_feed` | `{"portions":1..10}` | sibuk → `error_busy`; servo mati → `error_servo`; level 0 → `error_low_level` | `ok` setelah porsi terakhir |
| `set_schedule` | `{"schedules":[…]}` | parse gagal → `error_bad_payload` | `ok`, "schedules stored: N" |
| `set_threshold` | `{"threshold_pct":0..100}` | di luar 0..100 → `error_bad_payload` | `ok`, "threshold N%" |
| `set_rtc` | `{"datetime":"YYYY-MM-DDTHH:MM:SS"}` | parse gagal → `error_bad_payload` | `ok`, "rtc set" |
| `get_state` | `{}` | — | `ok` + snapshot JSON di `message` |

Firmware mengabaikan semua pesan yang topiknya bukan `command` (broker tertanam bisa mengirim
retained milik topik lain).

---

## 9. Platform (dashboard)

Thread: main Streamlit, `amqtt-broker` (daemon, asyncio), paho network thread, `timeout-sweeper`.

| Parameter | Nilai |
|---|---|
| broker bind | `0.0.0.0:1883`, anonim |
| mode broker | `embedded` / `existing` (port 1883 sudah dipakai) / `external` (`EMBED_BROKER=false`) |
| `COMMAND_TIMEOUT_SEC` | 30 s |
| `SWEEP_INTERVAL_MS` | 10 000 ms |
| `DEVICE_OFFLINE_SEC` | 45 s |
| `LIVE_TAIL_SIZE` | 200 |
| client id worker | `feeder-dashboard` |
| subscribe | `<prefix>/+/telemetry`, `+/ack`, `+/status`, `+/state` |
| publish | `<prefix>/<device>/command` QoS 1 |
| Streamlit | 1.64.0 lokal, minimum 1.50 |
| Python | 3.14 |

6 halaman: `status`, `live`, `alerts`, `history`, `schedules`, `control`.

Alur perintah:
`actions.client_command` → `commands.send_command` → `BEGIN IMMEDIATE` (`INSERT commands` status `sent`,
`INSERT feeding_logs` pending untuk `manual_feed`) → publish QoS 1 → ack masuk →
`handlers.handle_ack` → `db.apply_ack` → `command success/failed`; tanpa ack 30 s → sweeper
menandai `timeout`.

Alert (`handlers.evaluate_feed_alerts`): `pct <= 0` → `feed_empty` (critical);
`0 < pct <= threshold` → `feed_low` (warning); selain itu keduanya ditutup. Anti-spam:
`has_open_notification` sebelum insert.

---

## 10. Basis data (schema.sql)

6 tabel: `devices`, `telemetry`, `schedules`, `commands`, `feeding_logs`, `notifications`.
1 view: `v_device_status`. 6 index eksplisit. 2 UNIQUE (autoindex): `devices.device_code`,
`commands.command_id`.

Kardinalitas:
- `devices` 1 : N `telemetry` (CASCADE)
- `devices` 1 : N `schedules` (CASCADE)
- `devices` 1 : N `commands` (CASCADE)
- `devices` 1 : N `feeding_logs` (CASCADE)
- `devices` 1 : N `notifications` (CASCADE)
- `schedules` 1 : 0..N `feeding_logs` (`schedule_id`, SET NULL) — **selalu NULL saat runtime**
- `commands` 1 : 0..1 `feeding_logs` via `command_id` — **tanpa FK**, korelasi di aplikasi
- `devices` 1 : 1 `v_device_status`

Status perintah: `pending` → `sent` → `success` / `failed` / `timeout` (`pending` tidak pernah ditulis).
Status feeding_log: `pending` → `success` / `failed`.

Temuan (untuk Bab 9, jangan "diperbaiki"):
1. `devices.low_feed_threshold_pct` disimpan & dilaporkan `get_state`, tetapi firmware tidak pernah
   memakainya untuk memicu alert lokal; hanya `feedPct == 0` yang memblokir pemberian pakan.
2. `feeding_logs.schedule_id` tidak pernah diisi (`insert_scheduled_feeding_log` menulis NULL).
3. `commands.status = 'pending'` ada di CHECK dan sweep, tetapi `insert_command` selalu menulis `sent`.
4. `DEVICE_OFFLINE_SEC` (45 s) ada karena broker tertanam tidak menutup sesi client yang diam.

---

## 11. Peringatan penulisan

- Label di dalam diagram: **English**.
- Prosa bab: **Bahasa Indonesia**; istilah teknis tetap English.
- Angka kalibrasi wajib 3.0 / 17.0. `bin/verify-facts.sh` menggagalkan build kalau ada 5.00/25.00.
- Nama makro LaTeX hanya boleh huruf (tidak ada `\I2cClock`; gunakan `\IicClock`).
