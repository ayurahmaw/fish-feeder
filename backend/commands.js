import { randomUUID } from 'node:crypto';
import * as db from './db.js';

// Buat baris command di DB lalu publish JSON perintah ke feeder/<device>/command.
// Untuk manual_feed, juga buat feeding_logs berstatus 'pending' (ditutup saat ack).
export async function sendCommand(client, topicPrefix, deviceCode, type, payload = {}) {
  const device = await db.ensureDevice(deviceCode);
  const commandId = `cmd-${randomUUID()}`;
  await db.insertCommand({ commandId, deviceId: device.id, type, payload });

  let feedLogId = null;
  if (type === 'manual_feed') {
    const latest = await db.latestTelemetry(device.id);
    const portions = Number(payload.portions) > 0 ? Number(payload.portions) : 1;
    feedLogId = await db.insertFeedingLog({
      deviceId: device.id,
      commandId,
      portions,
      feedLevelBefore: latest?.feed_level_pct ?? null,
    });
  }

  const message = {
    command_id: commandId,
    type,
    payload,
    timestamp: new Date().toISOString(),
  };
  // qos 1 + callback: tunggu PUBACK broker agar pesan benar-benar terkirim
  await new Promise((resolve, reject) => {
    client.publish(`${topicPrefix}/${deviceCode}/command`, JSON.stringify(message), { qos: 1 }, (err) =>
      err ? reject(err) : resolve(),
    );
  });

  return { commandId, feedLogId };
}
