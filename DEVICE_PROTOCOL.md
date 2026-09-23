# Device Protocol — Kontrak MQTT untuk Firmware ESP32

> Referensi backend/dashboard: `MQTT_FOUNDATION_PLAN.md`, `DATABASE_PLAN.md`.
> Dokumen ini = "apa yang harus dilakukan device". Sudah tervalidasi E2E dengan
> `sim.js` + backend + database.

## 1. Koneksi

| Parameter | Nilai | Catatan |
|---|---|---|
| Broker | `mqtt://<IP-Mac-anda>:1883` | Mosquitto di Mac |
| ClientId | `feeder01` | **Harus unik & stabil** — jangan dipakai 2 proses (bug nyata: sesi saling tendang) |
| Keepalive | 60 s | |
| LWT (Will) | topic `feeder/feeder01/status`, payload `offline`, **retain=true** | Otomatis terpublish broker saat device mati |
| Saat connect | publish `online` ke `feeder/feeder01/status`, **retain=true** (birth) | Lalu subscribe command |

**Publish oleh device (3 topic):**

| Topic | Kapan | Format |
|---|---|---|
| `feeder/feeder01/status` | connect (birth) + LWT | string `online` / `offline` (bukan JSON) |
| `feeder/feeder01/telemetry` | periodik 10–30 s | JSON (lihat §2) |
| `feeder/feeder01/ack` | **wajib** balas tiap command | JSON (lihat §4) |

**Subscribe oleh device (1 topic):**

| Topic | Isi |
|---|---|
| `feeder/feeder01/command` | JSON perintah dari backend/dashboard (lihat §3) |

## 2. Payload Telemetry (device → platform)

Format target firmware (jarak mentah dari sensor ultrasonik — backend yang
menghitung persen dari kalibrasi di database):

```json
{
  "device": "feeder01",
  "state": "idle",
  "distance_cm": 12.5,
  "ts": "2026-09-23T13:00:00Z"
}
```

| Field | Wajib | Keterangan |
|---|---|---|
| `device` | ya | device_code (harus sama dengan clientId) |
| `state` | ya | `idle` / `feeding` / `error` |
| `distance_cm` | target utama | jarak sensor ke permukaan pakan (cm). Persen dihitung backend: `(empty_cm − distance) / (empty_cm − full_cm) × 100` |
| `feed_level_pct` | alternatif | boleh menggantikan `distance_cm` jika firmware sudah hitung sendiri persen |
| `ts` | opsional | ISO-8601; DB pakai waktu terima jika tidak ada |

Backend juga menerima format lama `{ "level": 50 }` (Node-RED) — kompatibel.

## 3. Payload Command (platform → device, device SUBSCRIBE)

```json
{
  "command_id": "cmd-ed239f2b-f305-46e6-8998-4fa7a4492986",
  "type": "manual_feed",
  "payload": { "portions": 2 },
  "timestamp": "2026-09-23T13:50:18Z"
}
```

| `type` | `payload` | Aksi device |
|---|---|---|
| `manual_feed` | `{ "portions": 2 }` | Jalankan servo × porsi, lalu ACK |
| `set_schedule` | `{ "schedules": [ { "id": 1, "feed_time": "07:00:00", "portions": 2 } ] }` | Simpan ke NVS/RTC, ACK |
| `set_threshold` | `{ "threshold_pct": 25 }` | Simpan, ACK |
| `set_rtc` | `{ "datetime": "2026-09-23T13:00:00" }` | Set RTC internal, ACK |
| `get_state` | `{}` | Balas state lengkap via ACK |

## 4. Payload Ack (device → platform, WAJIB untuk setiap command)

```json
{
  "command_id": "cmd-ed239f2b-f305-46e6-8998-4fa7a4492986",
  "result": "ok",
  "message": "feeding 2 portions",
  "ts": "2026-09-23T13:50:19Z"
}
```

Aturan:
- **`command_id` di-echo sama persis** — ini kunci korelasi di database.
- `result`: `"ok"` = sukses; nilai lain (`"error_low_level"`, `"error_servo"`, dst) = gagal
  → backend mencatat `failed` + membuat notifikasi `feed_failed`.
- **Tanpa ack dalam 30 detik** → backend menandai command `timeout`
  dan feeding_log `failed` (sudah otomatis).
- Ack dikirim meskipun perintah gagal dieksekusi (result error), bukan diam.

## 5. Sequence Diagram

### 5.1 Startup & Telemetry + Alert

```mermaid
sequenceDiagram
    participant D as ESP32 (feeder01)
    participant B as Mosquitto Broker
    participant P as Backend (Node.js)
    participant DB as MySQL feeder_db

    D->>B: CONNECT (clientId=feeder01, LWT offline)
    D->>B: PUBLISH status "online" (retain)
    B-->>P: status "online"
    P->>DB: devices.is_online=1 + tutup alert offline
    D->>B: SUBSCRIBE feeder/feeder01/command

    loop tiap 10-30 detik
        D->>B: PUBLISH telemetry {distance_cm, state}
        B-->>P: telemetry
        P->>DB: INSERT telemetry + hitung persen (kalibrasi)
        alt persen <= threshold
            P->>DB: INSERT notifications feed_low/feed_empty (anti-spam)
        else persen sehat
            P->>DB: tutup alert feed_low/feed_empty yang terbuka
        end
    end
```

### 5.2 Manual Feed (sukses)

```mermaid
sequenceDiagram
    participant U as User (Dashboard/CLI)
    participant P as Backend
    participant DB as MySQL
    participant B as Broker
    participant D as ESP32

    U->>P: minta feed manual (2 porsi)
    P->>DB: INSERT commands (sent) + feeding_logs (pending)
    P->>B: PUBLISH command {command_id, manual_feed, {portions:2}}
    B-->>D: command
    D->>D: buka servo 2 porsi
    D->>B: PUBLISH telemetry {state:"feeding"} (opsional)
    D->>B: PUBLISH ack {command_id sama, result:"ok"}
    B-->>P: ack
    P->>DB: commands -> success, feeding_logs -> success + level after
    P-->>U: status: berhasil
```

### 5.3 Gagal / Timeout / Device Mati

```mermaid
sequenceDiagram
    participant P as Backend
    participant DB as MySQL
    participant B as Broker
    participant D as ESP32

    alt ack result != ok
        D->>B: ack {result:"error_servo"}
        P->>DB: commands -> failed + notifikasi feed_failed (critical)
    else tidak ada ack 30 detik
        P->>DB: commands -> timeout, feeding_logs -> failed
    else device mati/putus (LWT)
        B-->>P: status "offline" (retained, otomatis dari broker)
        P->>DB: devices.is_online=0 + notifikasi device_offline
    end
```

## 6. Checklist Firmware ESP32

- [ ] ClientId unik + stabil (`feeder01`)
- [ ] Birth `online` (retain) + LWT `offline` (retain) di topic `status`
- [ ] Subscribe `feeder/feeder01/command`
- [ ] Publish telemetry periodik dengan `distance_cm`
- [ ] **Echo `command_id`** di setiap ack, kirim untuk sukses MAUPUN gagal
- [ ] State `feeding` saat motor jalan
- [ ] Reconnect otomatis + publish birth ulang saat sambungan kembali
