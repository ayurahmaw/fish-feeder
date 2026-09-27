-- ============================================================================
-- feeder_db — SQLite schema untuk Sistem Pakan Otomatis (ESP32 Autofeeder)
-- Desain lengkap: lihat DATABASE_PLAN.md
-- Protokol MQTT : lihat MQTT_FOUNDATION_PLAN.md / DEVICE_PROTOCOL.md
--
-- Engine  : SQLite 3.35+ (butuh window function untuk view v_device_status)
-- File    : dashboard/feeder.db — dibuat otomatis oleh aplikasi saat start
-- Import  : sqlite3 dashboard/feeder.db < database/schema.sql
--
-- Catatan: database ini berjalan DI DALAM proses aplikasi (tidak ada server
-- MySQL terpisah). ENUM MySQL -> CHECK, JSON -> TEXT + json_valid(),
-- DATETIME(3) -> TEXT dengan presisi milidetik.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. devices — daftar perangkat feeder + konfigurasi (Fitur 1 & 3)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devices (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  device_code            TEXT    NOT NULL UNIQUE,  -- kode unik = bagian topik MQTT, mis. feeder01
  name                   TEXT    NOT NULL,         -- nama tampilan
  location               TEXT,                     -- lokasi penempatan
  sensor_full_cm         REAL    NOT NULL DEFAULT 5.00,   -- jarak sensor saat hopper PENUH (kalibrasi)
  sensor_empty_cm        REAL    NOT NULL DEFAULT 25.00,  -- jarak sensor saat hopper KOSONG (kalibrasi)
  low_feed_threshold_pct INTEGER NOT NULL DEFAULT 20
                                 CHECK (low_feed_threshold_pct BETWEEN 0 AND 100),
  is_online              INTEGER NOT NULL DEFAULT 0 CHECK (is_online IN (0, 1)),
  last_seen_at           TEXT,
  created_at             TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
  updated_at             TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
  CHECK (sensor_full_cm < sensor_empty_cm)
);

-- ----------------------------------------------------------------------------
-- 2. telemetry — time-series level pakan (Fitur 1)
--    Sumber: feeder/<device>/telemetry
--    Konversi jarak -> persen (oleh aplikasi):
--      pct = (empty_cm - distance_cm) / (empty_cm - full_cm) * 100  (batasi 0..100)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telemetry (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id      INTEGER NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  distance_cm    REAL,   -- RAW jarak ultrasonik (NULL jika device hanya kirim persen)
  feed_level_pct REAL,   -- persen sisa pakan (hasil konversi / dari device)
  state          TEXT,   -- idle / feeding / error
  recorded_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
  ON telemetry (device_id, recorded_at);

-- ----------------------------------------------------------------------------
-- 3. schedules — jadwal pakan, berlaku setiap hari (Fitur 4)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedules (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id  INTEGER NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  name       TEXT    NOT NULL DEFAULT 'Jadwal Pakan',
  feed_time  TEXT    NOT NULL,          -- jam pemberian, mis. '07:00:00'
  portions   INTEGER NOT NULL DEFAULT 1,
  is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
  updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_schedules_device_active
  ON schedules (device_id, is_active, feed_time);

-- ----------------------------------------------------------------------------
-- 4. commands — log perintah MQTT keluar (Fitur 5, korelasi ack)
--    Sumber: feeder/<device>/command (kiriman) dan feeder/<device>/ack (balasan)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS commands (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  command_id     TEXT    NOT NULL UNIQUE,  -- ID dari payload JSON, korelasi dengan ack
  device_id      INTEGER NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  type           TEXT    NOT NULL
                 CHECK (type IN ('manual_feed', 'set_schedule', 'set_threshold', 'set_rtc', 'get_state')),
  payload        TEXT    NOT NULL CHECK (json_valid(payload)),
  status         TEXT    NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'sent', 'success', 'failed', 'timeout')),
  result_message TEXT,                     -- pesan "message" dari ack
  created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
  acked_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_commands_device_time
  ON commands (device_id, created_at);

-- ----------------------------------------------------------------------------
-- 5. feeding_logs — history pemberian pakan (Fitur 2 & 6)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feeding_logs (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id             INTEGER NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  command_id            TEXT,      -- korelasi commands/ack; NULL jika device eksekusi jadwal mandiri
  trigger_type          TEXT    NOT NULL CHECK (trigger_type IN ('manual', 'scheduled')),
  schedule_id           INTEGER REFERENCES schedules (id) ON DELETE SET NULL,
  portions              INTEGER NOT NULL DEFAULT 1,
  status                TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'success', 'failed')),
  message               TEXT,
  distance_before_cm    REAL,
  distance_after_cm     REAL,
  feed_level_before_pct REAL,
  feed_level_after_pct  REAL,
  requested_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
  completed_at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_feeding_device_time
  ON feeding_logs (device_id, requested_at);
CREATE INDEX IF NOT EXISTS idx_feeding_status
  ON feeding_logs (status);

-- ----------------------------------------------------------------------------
-- 6. notifications — alert (Fitur 3)
--    Anti-spam (logika aplikasi): sebelum INSERT, cek notifikasi type sama pada
--    device sama yang masih terbuka, agar tidak berulang tiap telemetry.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id      INTEGER NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
  type           TEXT    NOT NULL
                 CHECK (type IN ('feed_low', 'feed_empty', 'feed_failed', 'device_offline')),
  severity       TEXT    NOT NULL DEFAULT 'warning'
                 CHECK (severity IN ('info', 'warning', 'critical')),
  title          TEXT,
  message        TEXT    NOT NULL,
  feed_level_pct REAL,                     -- level pakan saat alert
  is_read        INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
  created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_notifications_device
  ON notifications (device_id, is_read, created_at);

-- ----------------------------------------------------------------------------
-- 7. View v_device_status — sisa pakan terbaru per device (Fitur 1 & 3)
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_device_status;

CREATE VIEW v_device_status AS
WITH latest AS (
  SELECT t.device_id,
         t.distance_cm,
         t.feed_level_pct,
         t.state,
         t.recorded_at,
         ROW_NUMBER() OVER (
           PARTITION BY t.device_id ORDER BY t.recorded_at DESC, t.id DESC
         ) AS rn
  FROM telemetry t
)
SELECT
  d.id                       AS device_id,
  d.device_code,
  d.name,
  d.location,
  d.sensor_full_cm,
  d.sensor_empty_cm,
  d.low_feed_threshold_pct,
  d.is_online,
  d.last_seen_at,
  l.distance_cm,
  l.feed_level_pct,
  l.state,
  l.recorded_at              AS measured_at,
  CASE
    WHEN l.feed_level_pct IS NULL THEN NULL
    WHEN l.feed_level_pct <= 0    THEN 1
    ELSE 0
  END                        AS is_empty,
  CASE
    WHEN l.feed_level_pct IS NULL THEN 0
    WHEN l.feed_level_pct <= 0    THEN 0
    WHEN l.feed_level_pct <= d.low_feed_threshold_pct THEN 1
    ELSE 0
  END                        AS is_low
FROM devices d
LEFT JOIN latest l ON l.device_id = d.id AND l.rn = 1;

-- ----------------------------------------------------------------------------
-- 8. Seed data awal
-- ----------------------------------------------------------------------------
INSERT OR IGNORE INTO devices
  (device_code, name, location, sensor_full_cm, sensor_empty_cm, low_feed_threshold_pct)
VALUES
  ('feeder01', 'Feeder Kolam 1', 'Kolam utama', 5.00, 25.00, 20);

INSERT INTO schedules (device_id, name, feed_time, portions, is_active)
SELECT d.id, 'Pakan Pagi', '07:00:00', 2, 1
FROM devices d
WHERE d.device_code = 'feeder01'
  AND NOT EXISTS (
    SELECT 1 FROM schedules s WHERE s.device_id = d.id AND s.feed_time = '07:00:00'
  );

INSERT INTO schedules (device_id, name, feed_time, portions, is_active)
SELECT d.id, 'Pakan Sore', '17:00:00', 2, 1
FROM devices d
WHERE d.device_code = 'feeder01'
  AND NOT EXISTS (
    SELECT 1 FROM schedules s WHERE s.device_id = d.id AND s.feed_time = '17:00:00'
  );
