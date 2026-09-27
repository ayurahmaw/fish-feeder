"""Embedded MQTT broker.

Runs an amqtt broker inside this process so the app needs no external broker.
The broker owns its own asyncio event loop in a daemon thread; the rest of the
app talks to it over plain TCP exactly as it would to mosquitto.
"""

from __future__ import annotations

import asyncio
import socket
import threading

from log import log, log_err


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _broker_config(bind: str) -> dict:
    """Mirror of amqtt's default broker config, minus the noisy log/$SYS plugins.

    Only the anonymous-auth plugin is kept: the broker is local dev only, and
    the event/packet loggers plus $SYS publishing just add stderr noise.
    """
    return {
        "listeners": {"default": {"type": "tcp", "bind": bind}},
        "plugins": {
            "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                "allow_anonymous": True,
            },
        },
    }


class EmbeddedBroker:
    def __init__(self, bind: str):
        self.bind = bind
        self.error = None
        self._loop = None
        self._broker = None
        self._thread = None
        self._ready = threading.Event()

    def start(self, timeout: float = 5.0) -> bool:
        self._thread = threading.Thread(
            target=self._run, name="amqtt-broker", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout)
        return self._broker is not None and self.error is None

    def _run(self) -> None:
        from amqtt.broker import Broker

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            self._broker = Broker(config=_broker_config(self.bind), loop=loop)
            loop.run_until_complete(self._broker.start())
            self._ready.set()
            log(f"broker tertanam berjalan di {self.bind}")
            loop.run_forever()
        except Exception as exc:  # surfaced through start()'s return value
            self.error = exc
            self._ready.set()
            log_err(f"broker tertanam gagal start: {exc}")

    def stop(self) -> None:
        if not (self._loop and self._broker):
            return
        future = asyncio.run_coroutine_threadsafe(self._broker.shutdown(), self._loop)
        try:
            future.result(timeout=5)
        except Exception as exc:
            log_err(f"broker gagal berhenti dengan bersih: {exc}")
