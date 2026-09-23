#!/usr/bin/env node
// ESP32 autofeeder MQTT simulator — proven working against local mosquitto broker
// (verified with the SAME mqtt lib bundled with your node22's node-red, under node v22.23.2)
//
// Run:  node /Users/macbookpro/Documents/TA-UPH/sim.js
//
// Mirrors exactly what the real ESP32 firmware will do:
//   - connect to broker :1883 with a stable client id
//   - subscribe to the command topic
//   - publish telemetry periodically
//   - react to manual-feed commands (reply + echo message)

const mqtt = require('/Users/macbookpro/.nvm/versions/node/v22.23.2/lib/node_modules/node-red/node_modules/mqtt');

const CFG = {
  broker:  'mqtt://localhost:1883',
  deviceId: 'feeder01',             // sinkron dengan seed database (devices.device_code)
  intervalMs: 3000,
};

// --- Topic tree (matches the autofeeder design; topics are stable identifiers) ---
const T = {
  telemetry: `feeder/${CFG.deviceId}/telemetry`,   // device -> platform (periodic)
  command:   `feeder/${CFG.deviceId}/command`,     // platform -> device (manual feed etc.)
  ack:       `feeder/${CFG.deviceId}/ack`,         // device -> platform (command reply)
  status:    `feeder/${CFG.deviceId}/status`,      // LWT + birth (online/offline)
};

let feedLevel = 80;   // % remaining, sim value
let cmdCounter = 0;

const client = mqtt.connect(CFG.broker, {
  clientId: CFG.deviceId,
  clean: false,
  keepalive: 60,
  // LWT: broker publishes this automatically if the sim (or later ESP32) dies
  will: { topic: T.status, payload: 'offline', qos: 0, retain: true },
});

client.on('connect', () => {
  console.log('[sim] CONNECTED as', CFG.deviceId);

  // birth/status retained so the platform can see us online immediately
  client.publish(T.status, 'online', { retain: true });

  // subscribe to incoming commands
  client.subscribe(T.command, (err) => {
    if (err) return console.error('[sim] subscribe ERR', err.message);
    console.log('[sim] SUBSCRIBED to', T.command);
  });

  // periodic telemetry
  setInterval(() => {
    const msg = {
      device: CFG.deviceId,
      state: 'idle',
      feed_level_pct: feedLevel,
      ts: new Date().toISOString(),
    };
    client.publish(T.telemetry, JSON.stringify(msg));
    console.log('[sim] TX telemetry', JSON.stringify(msg));
  }, CFG.intervalMs);
});

client.on('message', (topic, payload) => {
  const text = payload.toString();
  console.log('[sim] RX', topic, '->', text);

  try {
    const cmd = JSON.parse(text);
    if (cmd.cmd === 'feed' || cmd.type === 'manual_feed') {
      const portions = (cmd.portions || cmd.payload?.portions || 1);
      feedLevel = Math.max(0, feedLevel - portions * 2);
      const ack = {
        command_id: cmd.command_id || `c${++cmdCounter}`,
        result: 'ok',
        message: `feeding ${portions} portions`,
        ts: new Date().toISOString(),
      };
      client.publish(T.ack, JSON.stringify(ack));
      console.log('[sim] TX ack', JSON.stringify(ack));
    } else if (cmd.cmd === 'ping') {
      client.publish(T.ack, JSON.stringify({ command_id: cmd.command_id, result: 'ok', message: 'pong' }));
    }
  } catch (e) {
    console.log('[sim] non-JSON payload (ignored):', text);
  }
});

client.on('error', (e) => console.error('[sim] MQTT error', e.message));
client.on('close', () => console.log('[sim] connection closed'));

console.log('[sim] starting — broker', CFG.broker);
