-- ============================================================================
-- feeder_db — Contoh Query per Fitur
-- Jalankan setelah database/schema.sql:
--   sqlite3 dashboard/feeder.db < database/example_queries.sql
-- Catatan: file ini menyisipkan data contoh (telemetry uji).
-- ============================================================================

-- Device contoh 'feeder01' sudah di-seed oleh schema.sql.
-- Kalibrasi: full = 5 cm, empty = 25 cm, threshold = 20%.

-- ============================================================================
-- Fitur 1: Persentase sisa pakan
-- ============================================================================
SELECT device_code, name, feed_level_pct, distance_cm, is_low, is_empty, measured_at
FROM v_device_status;

-- Contoh telemetry uji (jarak 10 cm -> 75%):
--   pct = (25 - 10) / (25 - 5) * 100 = 75
INSERT INTO telemetry (device_id, distance_cm, feed_level_pct, state)
SELECT d.id, 10.00, 75.00, 'idle'
FROM devices d
WHERE d.device_code = 'feeder01';

-- ============================================================================
-- Fitur 2: Status pemberian pakan terakhir (berhasil / tidak)
-- ============================================================================
SELECT id, trigger_type, portions, status, message,
       feed_level_before_pct, feed_level_after_pct, requested_at, completed_at
FROM feeding_logs
WHERE device_id = (SELECT id FROM devices WHERE device_code = 'feeder01')
ORDER BY requested_at DESC, id DESC
LIMIT 1;

-- ============================================================================
-- Fitur 3: Notifikasi alert (pakan menipis / habis)
-- Threshold dikonfigurasi di devices.low_feed_threshold_pct:
--   UPDATE devices SET low_feed_threshold_pct = 25 WHERE device_code = 'feeder01';
-- ============================================================================
SELECT id, type, severity, title, message, feed_level_pct, created_at
FROM notifications
WHERE device_id = (SELECT id FROM devices WHERE device_code = 'feeder01')
  AND is_read = 0
ORDER BY created_at DESC;

-- Tandai semua sudah dibaca
-- UPDATE notifications SET is_read = 1 WHERE is_read = 0;

-- Contoh pembuatan alert oleh aplikasi saat telemetry masuk
-- (cek dulu notifikasi type sama yang belum selesai agar tidak spam):
INSERT INTO notifications (device_id, type, severity, title, message, feed_level_pct)
SELECT v.device_id, 'feed_low', 'warning', 'Pakan menipis',
       'Sisa pakan ' || v.feed_level_pct || '% (threshold '
       || v.low_feed_threshold_pct || '%)',
       v.feed_level_pct
FROM v_device_status v
WHERE v.device_code = 'feeder01'
  AND v.is_low = 1
  AND NOT EXISTS (
    SELECT 1 FROM notifications n
    WHERE n.device_id = v.device_id AND n.type = 'feed_low' AND n.is_read = 0
  );

-- ============================================================================
-- Fitur 4: Kontroling waktu pemberian pakan (CRUD jadwal)
-- ============================================================================
SELECT id, name, feed_time, portions, is_active
FROM schedules
WHERE device_id = (SELECT id FROM devices WHERE device_code = 'feeder01')
ORDER BY feed_time;

-- Tambah jadwal
-- INSERT INTO schedules (device_id, name, feed_time, portions)
-- SELECT id, 'Pakan Malam', '21:00:00', 1 FROM devices WHERE device_code = 'feeder01';

-- Ubah / aktif-nonaktif / hapus jadwal
-- UPDATE schedules SET feed_time = '06:30:00', portions = 3 WHERE id = 1;
-- UPDATE schedules SET is_active = 0 WHERE id = 1;
-- DELETE FROM schedules WHERE id = 1;

-- Saat jadwal diubah, kirim perintah ke device via MQTT:
--   feeder/<device>/command -> {"command_id":"<id>","type":"set_schedule",
--                               "payload":{"schedules":[...]},"timestamp":"..."}

-- ============================================================================
-- Fitur 5: Tombol pemberian pakan manual
-- ============================================================================

-- Langkah A — saat tombol ditekan (aplikasi): buat perintah + log pending
BEGIN IMMEDIATE;

INSERT INTO commands (command_id, device_id, type, payload, status)
SELECT 'cmd-contoh-1', id, 'manual_feed', json_object('portions', 2), 'sent'
FROM devices WHERE device_code = 'feeder01';

INSERT INTO feeding_logs
  (device_id, command_id, trigger_type, portions, status, feed_level_before_pct)
SELECT d.id, 'cmd-contoh-1', 'manual', 2, 'pending', v.feed_level_pct
FROM devices d
LEFT JOIN v_device_status v ON v.device_id = d.id
WHERE d.device_code = 'feeder01';

COMMIT;

-- Publish ke MQTT: feeder/<device>/command ->
--   {"command_id":"cmd-contoh-1","type":"manual_feed","payload":{"portions":2},"timestamp":"..."}

-- Langkah B — saat ack diterima dari feeder/<device>/ack
UPDATE commands
SET status = 'success', result_message = 'feeding',
    acked_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
WHERE command_id = 'cmd-contoh-1';

UPDATE feeding_logs
SET status = 'success', message = 'feeding',
    completed_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
WHERE command_id = 'cmd-contoh-1';

-- Jika gagal (ack result != ok), tambahkan juga alert:
-- INSERT INTO notifications (device_id, type, severity, title, message)
-- SELECT id, 'feed_failed', 'critical', 'Pemberian pakan gagal', '<pesan ack>'
-- FROM devices WHERE device_code = 'feeder01';

-- Perintah tanpa ack > 30 detik -> timeout (aplikasi melakukannya otomatis,
-- berkala sesuai SWEEP_INTERVAL_MS):
UPDATE commands
SET status = 'timeout'
WHERE status IN ('pending', 'sent')
  AND created_at < strftime('%Y-%m-%d %H:%M:%f', 'now', '-30 seconds');

UPDATE feeding_logs
SET status = 'failed', message = 'timeout',
    completed_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
WHERE status = 'pending'
  AND command_id IN (SELECT command_id FROM commands WHERE status = 'timeout');

-- ============================================================================
-- Fitur 6: History pemberian pakan
-- ============================================================================

-- History 30 hari terakhir
SELECT fl.id, fl.requested_at, fl.trigger_type, IFNULL(s.name, '-') AS schedule_name,
       fl.portions, fl.status, fl.message,
       fl.feed_level_before_pct, fl.feed_level_after_pct
FROM feeding_logs fl
LEFT JOIN schedules s ON s.id = fl.schedule_id
WHERE fl.device_id = (SELECT id FROM devices WHERE device_code = 'feeder01')
  AND fl.requested_at >= datetime('now', '-30 days')
ORDER BY fl.requested_at DESC;

-- Statistik per hari (sukses vs gagal)
SELECT date(fl.requested_at)   AS hari,
       SUM(fl.status = 'success') AS sukses,
       SUM(fl.status = 'failed')  AS gagal,
       SUM(fl.status = 'pending') AS tertunda
FROM feeding_logs fl
GROUP BY date(fl.requested_at)
ORDER BY hari DESC;

-- ============================================================================
-- Tambahan: status perangkat (dari topik feeder/<device>/status)
-- ============================================================================
-- UPDATE devices SET is_online = 1,
--   last_seen_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
--   WHERE device_code = 'feeder01';
-- UPDATE devices SET is_online = 0 WHERE device_code = 'feeder01';   -- saat LWT 'offline'
