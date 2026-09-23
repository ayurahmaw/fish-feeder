import mqtt from 'mqtt';
import { config } from './config.js';
import * as db from './db.js';
import { handleTelemetry, handleAck, handleStatus } from './handlers.js';
import { log, logErr } from './log.js';

const client = mqtt.connect(config.mqttUrl, {
  clientId: 'feeder-backend',
  clean: true,
  keepalive: 60,
});

client.on('connect', () => {
  const topics = [
    `${config.topicPrefix}/+/telemetry`,
    `${config.topicPrefix}/+/ack`,
    `${config.topicPrefix}/+/status`,
  ];
  client.subscribe(topics, (err) => {
    if (err) return logErr('subscribe error:', err.message);
    log('connected & subscribed:', topics.join('  '));
  });
});

client.on('message', async (topic, payload) => {
  // format topik: <prefix>/<device>/<kind>
  const parts = topic.split('/');
  if (parts.length !== 3 || parts[0] !== config.topicPrefix) return;
  const [, deviceCode, kind] = parts;

  const raw = payload.toString();
  let json = null;
  try {
    json = JSON.parse(raw);
  } catch {
    json = null;
  }

  try {
    if (kind === 'telemetry') await handleTelemetry(deviceCode, json ?? {});
    else if (kind === 'ack') await handleAck(deviceCode, json ?? {});
    else if (kind === 'status') await handleStatus(deviceCode, json ?? raw);
  } catch (e) {
    logErr(`gagal memproses ${topic}:`, e.message);
  }
});

client.on('error', (e) => logErr('mqtt error:', e.message));
client.on('reconnect', () => log('menghubungkan ulang ke broker...'));

// Sweep berkala: perintah tanpa ack -> timeout (feeding_logs -> failed)
const sweeper = setInterval(async () => {
  try {
    const n = await db.sweepTimeouts(config.commandTimeoutSec);
    if (n > 0) log(`${n} perintah ditandai timeout (> ${config.commandTimeoutSec}s tanpa ack)`);
  } catch (e) {
    logErr('sweep error:', e.message);
  }
}, config.sweepIntervalMs);

async function shutdown(signal) {
  log(`menerima ${signal}, mematikan...`);
  clearInterval(sweeper);
  await new Promise((r) => client.end(false, {}, r));
  await db.pool.end();
  process.exit(0);
}
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

log(`backend siap — broker ${config.mqttUrl}, db ${config.db.database}@${config.db.host}`);
