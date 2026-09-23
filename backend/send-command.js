#!/usr/bin/env node
// CLI kirim perintah ke feeder (masuk tabel commands + publish MQTT).
//
// Pemakaian:
//   node send-command.js <type> [deviceCode] ['{payload json}']
//
// Contoh:
//   node send-command.js manual_feed feeder01 '{"portions":2}'
//   node send-command.js get_state feeder01
//   node send-command.js set_threshold feeder01 '{"threshold_pct":25}'
import mqtt from 'mqtt';
import { config } from './config.js';
import { sendCommand } from './commands.js';
import { pool } from './db.js';

const [type = 'manual_feed', deviceCode = 'feeder01', payloadArg] = process.argv.slice(2);

let payload = {};
if (payloadArg) {
  try {
    payload = JSON.parse(payloadArg);
  } catch {
    console.error('payload bukan JSON valid, contoh: \'{"portions":2}\'');
    process.exit(1);
  }
}

const client = mqtt.connect(config.mqttUrl, { clientId: `feeder-cli-${process.pid}` });

client.on('connect', async () => {
  try {
    const { commandId } = await sendCommand(client, config.topicPrefix, deviceCode, type, payload);
    console.log(`terkirim: ${type} -> ${deviceCode} (command_id=${commandId})`);
    if (type === 'manual_feed') console.log('feeding_logs dibuat berstatus pending, menunggu ack...');
  } catch (e) {
    console.error('gagal:', e.message);
  } finally {
    await new Promise((r) => client.end(false, {}, r));
    await pool.end();
  }
});

client.on('error', (e) => {
  console.error('mqtt error:', e.message);
  process.exit(1);
});
