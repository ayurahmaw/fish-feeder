-- ============================================================================
-- feeder_db — Database MySQL untuk Sistem Pakan Otomatis (ESP32 Autofeeder)
-- Desain lengkap: lihat DATABASE_PLAN.md
-- Protokol MQTT: lihat MQTT_FOUNDATION_PLAN.md
--
-- Persyaratan : MySQL 8.0+ (JSON, window function)
-- Cara import : mysql -u root -p < database/schema.sql
-- ============================================================================

CREATE DATABASE IF NOT EXISTS feeder_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE feeder_db;

-- ----------------------------------------------------------------------------
-- 1. devices — daftar perangkat feeder + konfigurasi (Fitur 1 & 3)
-- ----------------------------------------------------------------------------
CREATE TABLE devices (
  id                     INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  device_code            VARCHAR(64)      NOT NULL COMMENT 'Kode unik = bagian topik MQTT, mis. feeder01',
  name                   VARCHAR(100)     NOT NULL COMMENT 'Nama tampilan',
  location               VARCHAR(100)     NULL     COMMENT 'Lokasi penempatan',
  sensor_full_cm         DECIMAL(6,2)     NOT NULL DEFAULT 5.00  COMMENT 'Jarak sensor ke permukaan pakan saat hopper PENUH (kalibrasi)',
  sensor_empty_cm        DECIMAL(6,2)     NOT NULL DEFAULT 25.00 COMMENT 'Jarak sensor ke permukaan pakan saat hopper KOSONG (kalibrasi)',
  low_feed_threshold_pct TINYINT UNSIGNED NOT NULL DEFAULT 20   COMMENT 'Ambang notifikasi pakan menipis (%) — bisa dikonfigurasi',
  is_online              TINYINT(1)       NOT NULL DEFAULT 0    COMMENT 'Dari topik feeder/<device>/status (LWT/birth)',
  last_seen_at           DATETIME(3)      NULL                  COMMENT 'Terakhir telemetry/status diterima',
  created_at             DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at             DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                                          ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uq_devices_code (device_code),
  CONSTRAINT ck_devices_calib CHECK (sensor_full_cm < sensor_empty_cm)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 2. telemetry — time-series level pakan (Fitur 1)
--    Sumber: feeder/<device>/telemetry
--    Konversi jarak -> persen (oleh backend):
--      pct = (empty_cm - distance_cm) / (empty_cm - full_cm) * 100  (batasi 0..100)
-- ----------------------------------------------------------------------------
CREATE TABLE telemetry (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id      INT UNSIGNED    NOT NULL,
  distance_cm    DECIMAL(6,2)    NULL     COMMENT 'RAW jarak ultrasonik ke permukaan pakan (NULL jika device hanya kirim persen)',
  feed_level_pct DECIMAL(5,2)    NULL     COMMENT 'Persen sisa pakan (hasil konversi / dari device)',
  state          VARCHAR(32)     NULL     COMMENT 'State device: idle / feeding / error',
  recorded_at    DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_telemetry_device_time (device_id, recorded_at),
  CONSTRAINT fk_telemetry_device FOREIGN KEY (device_id)
    REFERENCES devices (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 3. schedules — jadwal pakan, berlaku setiap hari (Fitur 4)
-- ----------------------------------------------------------------------------
CREATE TABLE schedules (
  id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  device_id  INT UNSIGNED  NOT NULL,
  name       VARCHAR(100)  NOT NULL DEFAULT 'Jadwal Pakan',
  feed_time  TIME          NOT NULL COMMENT 'Jam pemberian, mis. 07:00:00',
  portions   INT UNSIGNED  NOT NULL DEFAULT 1 COMMENT 'Porsi per eksekusi',
  is_active  TINYINT(1)    NOT NULL DEFAULT 1,
  created_at DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                           ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_schedules_device_active (device_id, is_active, feed_time),
  CONSTRAINT fk_schedules_device FOREIGN KEY (device_id)
    REFERENCES devices (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 4. commands — log perintah MQTT keluar (Fitur 5, korelasi ack)
--    Sumber: feeder/<device>/command (kiriman) dan feeder/<device>/ack (balasan)
-- ----------------------------------------------------------------------------
CREATE TABLE commands (
  id             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  command_id     VARCHAR(64)   NOT NULL COMMENT 'ID dari payload JSON, korelasi dengan ack',
  device_id      INT UNSIGNED  NOT NULL,
  type           ENUM('manual_feed','set_schedule','set_threshold','set_rtc','get_state') NOT NULL,
  payload        JSON          NOT NULL COMMENT 'Payload perintah apa adanya',
  status         ENUM('pending','sent','success','failed','timeout') NOT NULL DEFAULT 'pending',
  result_message VARCHAR(255)  NULL COMMENT 'Pesan "message" dari ack',
  created_at     DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  acked_at       DATETIME(3)   NULL COMMENT 'Diisi saat ack diterima',
  PRIMARY KEY (id),
  UNIQUE KEY uq_commands_command_id (command_id),
  KEY idx_commands_device_time (device_id, created_at),
  CONSTRAINT fk_commands_device FOREIGN KEY (device_id)
    REFERENCES devices (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 5. feeding_logs — history pemberian pakan (Fitur 2 & 6)
-- ----------------------------------------------------------------------------
CREATE TABLE feeding_logs (
  id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id             INT UNSIGNED    NOT NULL,
  command_id            VARCHAR(64)     NULL COMMENT 'Korelasi dengan commands/ack; NULL jika device eksekusi jadwal mandiri',
  trigger_type          ENUM('manual','scheduled') NOT NULL,
  schedule_id           INT UNSIGNED    NULL COMMENT 'Diisi jika trigger_type = scheduled',
  portions              INT UNSIGNED    NOT NULL DEFAULT 1,
  status                ENUM('pending','success','failed') NOT NULL DEFAULT 'pending',
  message               VARCHAR(255)    NULL COMMENT 'Pesan ack dari device',
  distance_before_cm    DECIMAL(6,2)    NULL,
  distance_after_cm     DECIMAL(6,2)    NULL,
  feed_level_before_pct DECIMAL(5,2)    NULL,
  feed_level_after_pct  DECIMAL(5,2)    NULL,
  requested_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  completed_at          DATETIME(3)     NULL COMMENT 'Diisi saat selesai (ack diterima)',
  PRIMARY KEY (id),
  KEY idx_feeding_device_time (device_id, requested_at),
  KEY idx_feeding_status (status),
  CONSTRAINT fk_feeding_device FOREIGN KEY (device_id)
    REFERENCES devices (id) ON DELETE CASCADE,
  CONSTRAINT fk_feeding_schedule FOREIGN KEY (schedule_id)
    REFERENCES schedules (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 6. notifications — alert (Fitur 3)
--    Catatan anti-spam (logika backend): sebelum INSERT, cek notifikasi type
--    sama pada device sama yang masih berlaku, agar tidak berulang tiap telemetry.
-- ----------------------------------------------------------------------------
CREATE TABLE notifications (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id      INT UNSIGNED    NOT NULL,
  type           ENUM('feed_low','feed_empty','feed_failed','device_offline') NOT NULL,
  severity       ENUM('info','warning','critical') NOT NULL DEFAULT 'warning',
  title          VARCHAR(150)    NULL,
  message        VARCHAR(255)    NOT NULL,
  feed_level_pct DECIMAL(5,2)    NULL COMMENT 'Level pakan saat alert',
  is_read        TINYINT(1)      NOT NULL DEFAULT 0,
  created_at     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_notifications_device (device_id, is_read, created_at),
  CONSTRAINT fk_notifications_device FOREIGN KEY (device_id)
    REFERENCES devices (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 7. View v_device_status — sisa pakan terbaru per device (Fitur 1 & 3)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_device_status AS
WITH latest AS (
  SELECT t.device_id,
         t.distance_cm,
         t.feed_level_pct,
         t.state,
         t.recorded_at,
         ROW_NUMBER() OVER (PARTITION BY t.device_id ORDER BY t.recorded_at DESC) AS rn
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
INSERT IGNORE INTO devices (device_code, name, location, sensor_full_cm, sensor_empty_cm, low_feed_threshold_pct)
VALUES ('feeder01', 'Feeder Kolam 1', 'Kolam utama', 5.00, 25.00, 20);

INSERT INTO schedules (device_id, name, feed_time, portions, is_active)
VALUES
  ((SELECT id FROM devices WHERE device_code = 'feeder01'), 'Pakan Pagi', '07:00:00', 2, 1),
  ((SELECT id FROM devices WHERE device_code = 'feeder01'), 'Pakan Sore', '17:00:00', 2, 1);

-- ----------------------------------------------------------------------------
-- 9. User aplikasi backend (jangan pakai root untuk backend)
--    Bisa juga dijalankan terpisah: mysql -u root -p < database/app_user.sql
-- ----------------------------------------------------------------------------
CREATE USER IF NOT EXISTS 'feeder_app'@'localhost' IDENTIFIED BY 'feeder_dev_123';
GRANT SELECT, INSERT, UPDATE, DELETE ON feeder_db.* TO 'feeder_app'@'localhost';
FLUSH PRIVILEGES;
