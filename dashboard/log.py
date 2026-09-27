"""Timestamped logging.

Port of backend/log.js — same shape, UTC timestamps so the output lines up with
the ISO strings stored in SQLite.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone


def _ts() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def log(*args) -> None:
    print(_ts(), "[feeder]", *args, flush=True)


def log_err(*args) -> None:
    print(_ts(), "[feeder]", *args, file=sys.stderr, flush=True)
