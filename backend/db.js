import mysql from 'mysql2/promise';
import { config } from './config.js';
import { logErr } from './log.js';

export const pool = mysql.createPool({
  ...config.db,
  waitForConnections: true,
  connectionLimit: 5,
  decimalNumbers: true,
});

pool.on('error', (e) => logErr('db pool error:', e.message));

// ---------------------------------------------------------------------------
// devices
// ---------------------------------------------------------------------------

export async function findDeviceByCode(deviceCode) {
  const [rows] = await pool.execute(
    `SELECT id, device_code, sensor_full_cm, sensor_empty_cm, low_feed_threshold_pct
     FROM devices WHERE device_code = ?`,
    [deviceCode],
  );
  return rows[0] ?? null;
}

export async function ensureDevice(deviceCode) {
  const found = await findDeviceByCode(deviceCode);
  if (found) return found;
  await pool.execute('INSERT IGNORE INTO devices (device_code, name) VALUES (?, ?)', [
    deviceCode,
    `Feeder ${deviceCode}`,
  ]);
  return findDeviceByCode(deviceCode);
}

export async function touchDevice(deviceId, online) {
  await pool.execute('UPDATE devices SET is_online = ?, last_seen_at = NOW(3) WHERE id = ?', [
    online ? 1 : 0,
    deviceId,
  ]);
}

// ---------------------------------------------------------------------------
// telemetry
// ---------------------------------------------------------------------------

export async function insertTelemetry({ deviceId, distanceCm, feedLevelPct, state }) {
  const [res] = await pool.execute(
    'INSERT INTO telemetry (device_id, distance_cm, feed_level_pct, state) VALUES (?, ?, ?, ?)',
    [deviceId, distanceCm ?? null, feedLevelPct ?? null, state ?? null],
  );
  return res.insertId;
}

export async function latestTelemetry(deviceId) {
  const [rows] = await pool.execute(
    `SELECT distance_cm, feed_level_pct, recorded_at
     FROM telemetry WHERE device_id = ? ORDER BY recorded_at DESC LIMIT 1`,
    [deviceId],
  );
  return rows[0] ?? null;
}

// ---------------------------------------------------------------------------
// notifications (anti-spam: 1 notifikasi terbuka per type per device)
// ---------------------------------------------------------------------------

export async function hasOpenNotification(deviceId, type) {
  const [rows] = await pool.execute(
    'SELECT 1 FROM notifications WHERE device_id = ? AND type = ? AND is_read = 0 LIMIT 1',
    [deviceId, type],
  );
  return rows.length > 0;
}

export async function insertNotification({ deviceId, type, severity, title, message, feedLevelPct = null }) {
  await pool.execute(
    `INSERT INTO notifications (device_id, type, severity, title, message, feed_level_pct)
     VALUES (?, ?, ?, ?, ?, ?)`,
    [deviceId, type, severity, title, message, feedLevelPct],
  );
}

export async function resolveNotifications(deviceId, types) {
  if (!types.length) return;
  const placeholders = types.map(() => '?').join(',');
  await pool.execute(
    `UPDATE notifications SET is_read = 1
     WHERE device_id = ? AND type IN (${placeholders}) AND is_read = 0`,
    [deviceId, ...types],
  );
}

// ---------------------------------------------------------------------------
// commands + feeding_logs
// ---------------------------------------------------------------------------

export async function insertCommand({ commandId, deviceId, type, payload }) {
  await pool.execute(
    'INSERT INTO commands (command_id, device_id, type, payload, status) VALUES (?, ?, ?, ?, ?)',
    [commandId, deviceId, type, JSON.stringify(payload), 'sent'],
  );
}

export async function insertFeedingLog({ deviceId, commandId, portions, feedLevelBefore = null }) {
  const [res] = await pool.execute(
    `INSERT INTO feeding_logs (device_id, command_id, trigger_type, portions, status, feed_level_before_pct)
     VALUES (?, ?, 'manual', ?, 'pending', ?)`,
    [deviceId, commandId, portions, feedLevelBefore],
  );
  return res.insertId;
}

export async function applyAck({ commandId, ok, message }) {
  const [res] = await pool.execute(
    'UPDATE commands SET status = ?, result_message = ?, acked_at = NOW(3) WHERE command_id = ?',
    [ok ? 'success' : 'failed', message, commandId],
  );
  if (res.affectedRows === 0) return false;

  await pool.execute(
    `UPDATE feeding_logs SET status = ?, message = ?, completed_at = NOW(3)
     WHERE command_id = ? AND status = 'pending'`,
    [ok ? 'success' : 'failed', message, commandId],
  );
  return true;
}

export async function attachFeedLevelAfter(deviceId, commandId) {
  const latest = await latestTelemetry(deviceId);
  if (!latest || latest.feed_level_pct == null) return;
  await pool.execute(
    'UPDATE feeding_logs SET distance_after_cm = ?, feed_level_after_pct = ? WHERE command_id = ?',
    [latest.distance_cm ?? null, latest.feed_level_pct, commandId],
  );
}

// ---------------------------------------------------------------------------
// timeout sweep — perintah tanpa ack dianggap timeout
// ---------------------------------------------------------------------------

export async function sweepTimeouts(timeoutSec) {
  const [stale] = await pool.execute(
    `UPDATE commands SET status = 'timeout'
     WHERE status IN ('pending', 'sent') AND created_at < NOW(3) - INTERVAL ? SECOND`,
    [timeoutSec],
  );
  if (stale.affectedRows > 0) {
    await pool.execute(
      `UPDATE feeding_logs fl
       JOIN commands c ON c.command_id = fl.command_id
       SET fl.status = 'failed', fl.message = 'timeout', fl.completed_at = NOW(3)
       WHERE c.status = 'timeout' AND fl.status = 'pending'`,
    );
  }
  return stale.affectedRows;
}
