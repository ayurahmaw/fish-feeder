import * as db from './db.js';
import { log } from './log.js';

const numOrNull = (v) => {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

// Konversi jarak ultrasonik -> persen (kalibrasi per device, dibatasi 0..100)
function computePct(device, distanceCm) {
  const full = Number(device.sensor_full_cm);
  const empty = Number(device.sensor_empty_cm);
  if (!Number.isFinite(full) || !Number.isFinite(empty) || empty <= full) return null;
  return Math.min(100, Math.max(0, ((empty - distanceCm) / (empty - full)) * 100));
}

// ---------------------------------------------------------------------------
// telemetry: feeder/<device>/telemetry
// Format diterima (fleksibel):
//   { distance_cm, state }            — format firmware target (jarak mentah)
//   { feed_level_pct, state }         — format sim.js saat ini
//   { level, state }                  — format Node-RED flow
// ---------------------------------------------------------------------------
export async function handleTelemetry(deviceCode, payload) {
  const device = await db.ensureDevice(deviceCode);

  const distanceCm = numOrNull(payload.distance_cm ?? payload.distance ?? payload.distanceCm);
  const rawPct = numOrNull(payload.feed_level_pct ?? payload.level ?? payload.feedLevelPct);
  const feedLevelPct = distanceCm != null ? computePct(device, distanceCm) : rawPct;
  const state = payload.state ?? null;

  await db.insertTelemetry({ deviceId: device.id, distanceCm, feedLevelPct, state });
  await db.touchDevice(device.id, true);
  await evaluateFeedAlerts(device, feedLevelPct);

  log(
    `telemetry ${deviceCode}: distance=${distanceCm ?? '-'}cm level=${feedLevelPct ?? '-'}% state=${state ?? '-'}`,
  );
}

// Alert pakan menipis / habis (anti-spam: 1 notifikasi terbuka per type,
// ditutup otomatis saat level kembali sehat agar bisa menyala lagi nanti)
async function evaluateFeedAlerts(device, pct) {
  if (pct == null) return;
  const threshold = Number(device.low_feed_threshold_pct) || 0;

  if (pct <= 0) {
    await db.resolveNotifications(device.id, ['feed_low']);
    if (!(await db.hasOpenNotification(device.id, 'feed_empty'))) {
      await db.insertNotification({
        deviceId: device.id,
        type: 'feed_empty',
        severity: 'critical',
        title: 'Pakan habis',
        message: 'Sisa pakan 0% — segera isi ulang hopper.',
        feedLevelPct: pct,
      });
      log(`ALERT feed_empty (${device.device_code})`);
    }
  } else if (pct <= threshold) {
    await db.resolveNotifications(device.id, ['feed_empty']);
    if (!(await db.hasOpenNotification(device.id, 'feed_low'))) {
      await db.insertNotification({
        deviceId: device.id,
        type: 'feed_low',
        severity: 'warning',
        title: 'Pakan menipis',
        message: `Sisa pakan ${pct}% (threshold ${threshold}%).`,
        feedLevelPct: pct,
      });
      log(`ALERT feed_low (${device.device_code})`);
    }
  } else {
    await db.resolveNotifications(device.id, ['feed_low', 'feed_empty']);
  }
}

// ---------------------------------------------------------------------------
// ack: feeder/<device>/ack  { command_id, result, message }
// ---------------------------------------------------------------------------
export async function handleAck(deviceCode, payload) {
  const device = await db.ensureDevice(deviceCode);
  const commandId = payload.command_id ?? payload.commandId;
  if (!commandId) return log(`ack dari ${deviceCode} tanpa command_id — diabaikan`);

  const ok = String(payload.result ?? '').toLowerCase() === 'ok';
  const message = payload.message ?? payload.result ?? '';
  const known = await db.applyAck({ commandId, ok, message });
  if (!known) return log(`ack command_id tidak dikenal: ${commandId}`);

  if (ok) {
    await db.attachFeedLevelAfter(device.id, commandId);
    log(`command ${commandId} -> success (${message})`);
  } else {
    await db.insertNotification({
      deviceId: device.id,
      type: 'feed_failed',
      severity: 'critical',
      title: 'Pemberian pakan gagal',
      message: String(message),
    });
    log(`command ${commandId} -> FAILED (${message})`);
  }
}

// ---------------------------------------------------------------------------
// status: feeder/<device>/status  ("online" / "offline", retained LWT/birth)
// ---------------------------------------------------------------------------
export async function handleStatus(deviceCode, payload) {
  const device = await db.ensureDevice(deviceCode);
  const status =
    typeof payload === 'string'
      ? payload.trim()
      : String(payload?.status ?? payload?.state ?? '').trim();
  if (!status) return;

  const online = status === 'online';
  await db.touchDevice(device.id, online);

  if (online) {
    await db.resolveNotifications(device.id, ['device_offline']);
    log(`${deviceCode} online`);
  } else if (status === 'offline') {
    if (!(await db.hasOpenNotification(device.id, 'device_offline'))) {
      await db.insertNotification({
        deviceId: device.id,
        type: 'device_offline',
        severity: 'warning',
        title: 'Perangkat offline',
        message: `${deviceCode} tidak merespons (LWT offline).`,
      });
      log(`ALERT device_offline (${deviceCode})`);
    }
  }
}
