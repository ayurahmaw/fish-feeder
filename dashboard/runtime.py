"""Process-wide runtime: embedded broker + MQTT worker + timeout sweeper.

Deliberately a plain module-level singleton rather than ``st.cache_resource``:
Streamlit only executes the page script once a browser session connects, and
the broker has to be reachable before that (sim.js / ESP32 connect on their own
schedule). ``run.py`` boots this in the main thread and then hands the process
to Streamlit; ``app.py`` just asks for the same singleton.

Importing this module starts nothing.
"""

from __future__ import annotations

import threading

import config
import db
from broker import EmbeddedBroker, port_in_use
from log import log, log_err
from mqtt import Worker


class Runtime:
    def __init__(self):
        self.broker = None
        self.worker = None
        self.mode = "external"
        self._sweeper = None
        self._stop = threading.Event()

    @property
    def broker_label(self) -> str:
        return {
            "embedded": f"embedded ({config.BROKER_BIND})",
            "existing": f"existing broker at {config.MQTT_URL}",
            "external": f"external {config.MQTT_URL}",
        }.get(self.mode, self.mode)


def _start_sweeper(stop_event: threading.Event) -> threading.Thread:
    """Port of the setInterval sweeper in backend/index.js."""

    def loop():
        interval = max(1.0, config.SWEEP_INTERVAL_MS / 1000)
        while not stop_event.wait(interval):
            try:
                stale = db.sweep_timeouts(config.COMMAND_TIMEOUT_SEC)
                if stale:
                    log(
                        f"{stale} perintah ditandai timeout "
                        f"(> {config.COMMAND_TIMEOUT_SEC}s tanpa ack)"
                    )
            except Exception as exc:
                log_err("sweep error:", exc)

    thread = threading.Thread(target=loop, name="timeout-sweeper", daemon=True)
    thread.start()
    return thread


def _build() -> Runtime:
    runtime = Runtime()
    db.init_db()

    host, port = config.mqtt_host_port()
    if not config.EMBED_BROKER:
        log(f"EMBED_BROKER=false — memakai broker eksternal {config.MQTT_URL}")
    elif port_in_use(host, port):
        # e.g. mosquitto is already running as a brew service
        runtime.mode = "existing"
        log(
            f"port {port} sudah terpakai — memakai broker yang sudah jalan "
            f"di {config.MQTT_URL}"
        )
    else:
        broker = EmbeddedBroker(config.BROKER_BIND)
        if broker.start():
            runtime.broker = broker
            runtime.mode = "embedded"
        else:
            log_err(f"broker tertanam gagal ({broker.error}) — memakai {config.MQTT_URL}")

    runtime.worker = Worker()
    runtime.worker.start()
    if not runtime.worker.wait_connected(5):
        log_err("worker belum terhubung ke broker (masih mencoba...)")

    runtime._sweeper = _start_sweeper(runtime._stop)
    log(f"runtime siap — broker: {runtime.broker_label}, db: {config.DB_PATH}")
    return runtime


_runtime = None
_lock = threading.Lock()


def get_runtime() -> Runtime:
    """Start the platform on first call; later calls return the same instance."""
    global _runtime
    if _runtime is None:
        with _lock:
            if _runtime is None:
                _runtime = _build()
    return _runtime
