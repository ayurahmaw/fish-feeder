"""Configuration for the feeder platform.

Port of backend/config.js. Everything is env-driven with the same variable names
where they still make sense; the MySQL connection settings are gone because the
database now lives inside this process (SQLite).
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _num(value, default):
    if value is None or value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return int(number) if number.is_integer() else number


def _bool(value, default):
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# --- MQTT -------------------------------------------------------------------
MQTT_URL = os.getenv("MQTT_URL", "mqtt://localhost:1883")
TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "feeder")
CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "feeder-dashboard")

# Embedded broker. When true the app hosts the broker itself; when false it
# connects to whatever broker MQTT_URL points at (e.g. a local mosquitto).
EMBED_BROKER = _bool(os.getenv("EMBED_BROKER"), True)
BROKER_BIND = os.getenv("BROKER_BIND", "0.0.0.0:1883")

# --- Database ---------------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "feeder.db"))
SCHEMA_PATH = Path(
    os.getenv("SCHEMA_PATH", str(BASE_DIR.parent / "database" / "schema.sql"))
)

# --- Commands ---------------------------------------------------------------
COMMAND_TIMEOUT_SEC = _num(os.getenv("COMMAND_TIMEOUT_SEC"), 30)
SWEEP_INTERVAL_MS = _num(os.getenv("SWEEP_INTERVAL_MS"), 10_000)

# --- UI ---------------------------------------------------------------------
LIVE_TAIL_SIZE = _num(os.getenv("LIVE_TAIL_SIZE"), 200)


def mqtt_host_port():
    """Host/port of MQTT_URL, used for the embedded-broker port probe."""
    parsed = urlparse(MQTT_URL)
    return parsed.hostname or "localhost", parsed.port or 1883
