-- ============================================================================
-- feeder_db — Contoh Query per Fitur (jalankan SETELAH database/schema.sql)
-- Import: mysql -u root -p feeder_db < database/example_queries.sql
-- Catatan: file ini menyisipkan data contoh (manual feed & telemetry uji).
-- ============================================================================

USE feeder_db;

SET @device_id = (SELECT id FROM devices WHERE device_code = 'feeder01');

-- ============================================================================
-- Fitur 1: Persentase sisa pakan
-- ============================================================================
SELECT device_code, name, feed_level_pct, distance_cm, is_low, is_empty, measured_at
FROM v_device_status
WHERE device_id = @device_id;

-- Contoh telemetry uji (jarak 10 cm -> ~75% pada kalibrasi full=5, empty=25):
-- pct = (25 - 10) / (25 - 5) * 100 = 75
INSERT INTO telemetry (device_id, distance_cm, feed_level_pct, state)
SELECT @device_id, 10.00, 75.00, 'idle'
WHERE EXISTS (SELECT 1 FROM devices WHERE id = @device_id);

-- ============================================================================
-- Fitur 2: Status pemberian pakan terakhir (berhasil / tidak)
-- ============================================================================
SELECT id, trigger_type, portions, status, message,
       feed_level_before_pct, feed_level_after_pct, requested_at, completed_at
FROM feeding_logs
WHERE device_id = @device_id
ORDER BY requested_at DESC
LIMIT 1;

-- ============================================================================
-- Fitur 3: Notifikasi alert (pakan menipis / habis)
-- Threshold dikonfigurasi di devices.low_feed_threshold_pct (ubah kapan saja):
--   UPDATE devices SET low_feed_threshold_pct = 25 WHERE id = @device_id;
-- ============================================================================

-- Notifikasi belum dibaca (terbaru dulu)
SELECT id, type, severity, title, message, feed_level_pct, created_at
FROM notifications
WHERE device_id = @device_id AND is_read = 0
ORDER BY created_at DESC;

-- Tandai semua sudah dibaca
-- UPDATE notifications SET is_read = 1 WHERE device_id = @device_id AND is_read = 0;

-- Contoh pembuatan alert oleh backend saat telemetry masuk:
--   is_empty  -> type 'feed_empty'  severity 'critical'
--   is_low    -> type 'feed_low'    severity 'warning'
-- (cek dulu notifikasi type sama yang belum selesai agar tidak spam)
INSERT INTO notifications (device_id, type, severity, title, message, feed_level_pct)
SELECT @device_id, 'feed_low', 'warning', 'Pakan menipis',
       CONCAT('Sisa pakan ', v.feed_level_pct, '% (threshold ', v.low_feed_threshold_pct, '%)'),
       v.feed_level_pct
FROM v_device_status v
WHERE v.device_id = @device_id
  AND v.is_low = 1
  AND NOT EXISTS (
    SELECT 1 FROM notifications n
    WHERE n.device_id = @device_id AND n.type = 'feed_low' AND n.is_read = 0
  );

-- ============================================================================
-- Fitur 4: Kontroling waktu pemberian pakan (CRUD jadwal)
-- ============================================================================

-- Lihat jadwal aktif
SELECT id, name, feed_time, portions, is_active
FROM schedules
WHERE device_id = @device_id AND is_active = 1
ORDER BY feed_time;

-- Tambah jadwal
-- INSERT INTO schedules (device_id, name, feed_time, portions)
-- VALUES (@device_id, 'Pakan Malam', '21:00:00', 1);

-- Ubah jadwal
-- UPDATE schedules SET feed_time = '06:30:00', portions = 3 WHERE id = 1;

-- Nonaktifkan / aktifkan jadwal
-- UPDATE schedules SET is_active = 0 WHERE id = 1;

-- Hapus jadwal
-- DELETE FROM schedules WHERE id = 1;

-- Saat jadwal diubah, kirim perintah ke device via MQTT:
-- topic feeder/feeder01/command ->
--   {"command_id":"<id>","type":"set_schedule","payload":{"schedules":[...]},"timestamp":"..."}

-- ============================================================================
-- Fitur 5: Tombol pemberian pakan manual
-- ============================================================================

-- Langkah A — saat tombol ditekan (backend): buat perintah + log pending
SET @cmd_id = CONCAT('cmd-', UUID_SHORT());

START TRANSACTION;

INSERT INTO commands (command_id, device_id, type, payload, status)
VALUES (@cmd_id, @device_id, 'manual_feed', JSON_OBJECT('portions', 2), 'sent');

INSERT INTO feeding_logs (device_id, command_id, trigger_type, portions, status, feed_level_before_pct)
SELECT @device_id, @cmd_id, 'manual', 2, 'pending', v.feed_level_pct
FROM v_device_status v
WHERE v.device_id = @device_id;

COMMIT;

-- Publish ke MQTT: topic feeder/feeder01/command ->
--   {"command_id":"<@cmd_id>","type":"manual_feed","payload":{"portions":2},"timestamp":"..."}

-- Langkah B — saat ack diterima dari feeder/<device>/ack: update status
-- Contoh ack sukses (nilai after contoh; di backend ambil dari telemetry terbaru):
UPDATE commands
SET status = 'success', result_message = 'feeding', acked_at = NOW(3)
WHERE command_id = @cmd_id;

UPDATE feeding_logs
SET status = 'success', message = 'feeding', completed_at = NOW(3),
    distance_after_cm = 12.00, feed_level_after_pct = 65.00
WHERE command_id = @cmd_id;

-- Jika gagal (ack result != ok), tambahkan juga alert:
-- INSERT INTO notifications (device_id, type, severity, title, message)
-- VALUES (@device_id, 'feed_failed', 'critical', 'Pemberian pakan gagal', '<pesan ack>');

-- Perintah yang tidak di-ack > 30 detik -> timeout (jalankan berkala via cron/event):
-- UPDATE commands SET status = 'timeout'
-- WHERE status = 'sent' AND created_at < NOW(3) - INTERVAL 30 SECOND;
-- UPDATE feeding_logs fl JOIN commands c ON c.command_id = fl.command_id
-- SET fl.status = 'failed', fl.message = 'timeout', fl.completed_at = NOW(3)
-- WHERE c.status = 'timeout' AND fl.status = 'pending';

-- ============================================================================
-- Fitur 6: History pemberian pakan
-- ============================================================================

-- History 30 hari terakhir
SELECT fl.id, fl.requested_at, fl.trigger_type, IFNULL(s.name, '-') AS schedule_name,
       fl.portions, fl.status, fl.message,
       fl.feed_level_before_pct, fl.feed_level_after_pct
FROM feeding_logs fl
LEFT JOIN schedules s ON s.id = fl.schedule_id
WHERE fl.device_id = @device_id
  AND fl.requested_at >= NOW() - INTERVAL 30 DAY
ORDER BY fl.requested_at DESC;

-- Statistik per hari (sukses vs gagal)
SELECT DATE(fl.requested_at) AS hari,
       SUM(fl.status = 'success') AS sukses,
       SUM(fl.status = 'failed')  AS gagal,
       SUM(fl.status = 'pending') AS tertunda
FROM feeding_logs fl
WHERE fl.device_id = @device_id
GROUP BY DATE(fl.requested_at)
ORDER BY hari DESC;

-- ============================================================================
-- Tambahan: status perangkat (dari topik feeder/<device>/status)
-- UPDATE devices SET is_online = 1, last_seen_at = NOW(3) WHERE id = @device_id;
-- UPDATE devices SET is_online = 0 WHERE id = @device_id;  -- saat LWT 'offline'
-- ============================================================================
