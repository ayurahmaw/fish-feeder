import 'dotenv/config';

const num = (v, d) => (v !== undefined && v !== '' && Number.isFinite(Number(v)) ? Number(v) : d);

export const config = {
  mqttUrl: process.env.MQTT_URL || 'mqtt://localhost:1883',
  topicPrefix: process.env.MQTT_TOPIC_PREFIX || 'feeder',

  db: {
    host: process.env.DB_HOST || 'localhost',
    port: num(process.env.DB_PORT, 3306),
    user: process.env.DB_USER || 'feeder_app',
    password: process.env.DB_PASSWORD || 'feeder_dev_123',
    database: process.env.DB_NAME || 'feeder_db',
    charset: 'utf8mb4',
  },

  commandTimeoutSec: num(process.env.COMMAND_TIMEOUT_SEC, 30),
  sweepIntervalMs: num(process.env.SWEEP_INTERVAL_MS, 10000),
};
