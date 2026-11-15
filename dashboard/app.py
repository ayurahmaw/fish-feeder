"""AquaFeed dashboard.

Router and shared shell for the six dashboard pages. The MQTT broker, SQLite
database and ingestion worker are started by ``runtime.py`` (via ``run.py``).

    python run.py            # -> http://localhost:8501
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import config
import data
import ui
from i18n import PAGE_COPY, locale, t
from runtime import get_runtime

BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="AquaFeed",
    page_icon=":material/set_meal:",
    layout="wide",
)

runtime = get_runtime()

st.logo(str(BASE_DIR / "assets" / "brand.svg"), size="large")
st.html(BASE_DIR / "assets" / "theme.css")

device_list = data.devices()
if not device_list:
    st.error(t("no_device"))
    st.stop()

# --------------------------------------------------------------------------- #
# navigation
# --------------------------------------------------------------------------- #
PAGES = [
    ("status", "app_pages/status.py", ":material/speed:"),
    ("live", "app_pages/live.py", ":material/monitoring:"),
    ("alerts", "app_pages/alerts.py", ":material/notifications:"),
    ("history", "app_pages/history.py", ":material/history:"),
    ("schedules", "app_pages/schedules.py", ":material/calendar_month:"),
    ("control", "app_pages/control.py", ":material/tune:"),
]

built = [
    (page_id, st.Page(path, title=PAGE_COPY[page_id][locale()]["title"], icon=icon))
    for page_id, path, icon in PAGES
]

page = st.navigation([page_obj for _, page_obj in built], position="sidebar")
page_id = next((pid for pid, page_obj in built if page_obj is page), built[0][0])

# --------------------------------------------------------------------------- #
# sidebar: device + system health + language
# --------------------------------------------------------------------------- #
with st.sidebar:
    options = [item["device_code"] for item in device_list]
    if st.session_state.get("device_code") not in options:
        st.session_state["device_code"] = options[0]

    chosen = st.selectbox(t("select_device"), options, key="device_code")
    device = next(item for item in device_list if item["device_code"] == chosen)
    st.caption(f"{device['device_code']} · {device['location'] or device['name']}")

    with st.container(border=True):
        st.markdown(f"**{t('system_status')}**")
        ui.badge(t("healthy"), "healthy")
        st.markdown(f":material/dns: {t('broker')} · {runtime.mode}")
        st.markdown(
            f":material/settings_input_antenna: {t('worker')} · "
            f"{t('connected') if runtime.worker.connected else t('disconnected')}"
        )
        st.markdown(f":material/database: {t('database')} · {t('ready')}")
        st.caption(f"{t('ack_timeout')} · {config.COMMAND_TIMEOUT_SEC}s")

    if st.button(t("reload"), icon=":material/refresh:"):
        data.clear_reads()
        ui.toast_after_rerun(t("refreshed_toast"))
        st.rerun()

    st.segmented_control(
        t("language"),
        options=["id", "en"],
        default="id",
        required=True,
        key="locale",
        format_func=lambda value: "ID" if value == "id" else "EN",
    )
    st.caption(t("local_footer"))

# --------------------------------------------------------------------------- #
# topbar
# --------------------------------------------------------------------------- #
status = data.status_of(device["id"])
online = bool(status and status["is_online"])

title_col, action_col = st.columns([3, 2], vertical_alignment="center")
with title_col:
    st.title(page.title)
    st.caption(PAGE_COPY[page_id][locale()]["description"])
with action_col:
    with st.container(horizontal=True, horizontal_alignment="right"):
        ui.badge(
            t("online") if online else t("offline"),
            "healthy" if online else "critical",
        )
        ui.badge(runtime.mode, "neutral")
        if st.button(t("refresh"), icon=":material/refresh:", key="refresh_top"):
            data.clear_reads()
            ui.toast_after_rerun(t("refreshed_toast"))
            st.rerun()

st.session_state["device"] = device
ui.flush_toast()

page.run()
