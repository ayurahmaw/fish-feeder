"""MQTT worker.

Port of the subscription half of backend/index.js: connects to the broker,
subscribes to device traffic and dispatches each message to handlers.py. Also
keeps a bounded tail of raw messages for the Live tab.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

import config
from handlers import handle_ack, handle_status, handle_telemetry
from log import log, log_err

TOPIC_KINDS = ("telemetry", "ack", "status")


def _ts() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class Worker:
    def __init__(self):
        self.tail = deque(maxlen=config.LIVE_TAIL_SIZE)
        self._lock = threading.Lock()
        self._connected = threading.Event()
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=config.CLIENT_ID,
            clean_session=True,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_connect_fail = self._on_connect_fail
        self.client.on_message = self._on_message

    # ------------------------------------------------------------------ life
    def start(self) -> None:
        # paho wants host and port separately — it does not parse "mqtt://..." URLs.
        host, port = config.mqtt_host_port()
        self.client.connect_async(host, port, keepalive=60)
        self.client.loop_start()

    def wait_connected(self, timeout: float = 5.0) -> bool:
        return self._connected.wait(timeout)

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic: str, payload: str, qos: int = 1):
        return self.client.publish(topic, payload, qos=qos)

    # ------------------------------------------------------------- callbacks
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        topics = [f"{config.TOPIC_PREFIX}/+/{kind}" for kind in TOPIC_KINDS]
        client.subscribe([(topic, 0) for topic in topics])
        self._connected.set()
        log("worker terhubung & subscribe:", "  ".join(topics))

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self._connected.clear()
        log_err(f"worker terputus (rc={reason_code}) — paho akan mencoba ulang")

    def _on_connect_fail(self, client, userdata):
        log_err(f"worker gagal menyambung ke {config.MQTT_URL}")

    def _on_message(self, client, userdata, msg):
        raw = msg.payload.decode("utf-8", errors="replace")
        with self._lock:
            self.tail.append({"time": _ts(), "topic": msg.topic, "payload": raw})

        parts = msg.topic.split("/")
        if len(parts) != 3 or parts[0] != config.TOPIC_PREFIX:
            return
        _, device_code, kind = parts

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw  # status is a bare "online" / "offline" string

        try:
            if kind == "telemetry":
                handle_telemetry(device_code, parsed if isinstance(parsed, dict) else {})
            elif kind == "ack":
                handle_ack(device_code, parsed if isinstance(parsed, dict) else {})
            elif kind == "status":
                handle_status(device_code, parsed)
        except Exception as exc:
            log_err(f"gagal memproses {msg.topic}: {exc}")

    # --------------------------------------------------------------- helpers
    def tail_snapshot(self):
        with self._lock:
            return list(self.tail)
