#!/usr/bin/env python
"""Start the whole feeder platform, then hand this process to Streamlit.

    pipenv run python run.py                 # -> http://localhost:8501
    pipenv run python run.py --server.port 8600

The broker, MQTT worker and timeout sweeper start here, before Streamlit does,
so `sim.js` / the ESP32 can connect without waiting for someone to open the
dashboard in a browser. `streamlit run app.py` also works, but then the platform
only starts once the first page session connects.
"""

from __future__ import annotations

import sys
from pathlib import Path

from runtime import get_runtime

APP = Path(__file__).resolve().with_name("app.py")


def main() -> int:
    runtime = get_runtime()
    print(f"[feeder] platform siap — broker: {runtime.broker_label}", flush=True)

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(APP),
        "--browser.gatherUsageStats",
        "false",
        *sys.argv[1:],
    ]
    return stcli.main()


if __name__ == "__main__":
    raise SystemExit(main())
