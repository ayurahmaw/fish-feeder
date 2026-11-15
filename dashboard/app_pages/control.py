"""Control page: deliberate, auditable device commands."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

import data
import db
import ui
from actions import client_command, confirm_feed, notify_command, notify_failure
from i18n import state_label, status_label, t

device = st.session_state["device"]
status = data.status_of(device["id"]) or {}
online = bool(status.get("is_online"))

st.warning(
    f"**{t('security_title')}** — {t('security_body')}", icon=":material/shield:"
)

row_one = st.columns(2)

with row_one[0]:
    with st.container(border=True, key="control_feed"):
        st.markdown("### :material/bolt:")
        st.subheader(t("manual_feeding"))
        st.caption(t("manual_feeding_sub"))
        if "manual_portions" not in st.session_state:
            st.session_state["manual_portions"] = 2
        portions = st.number_input(
            t("num_portions"), min_value=1, max_value=10, step=1,
            key="manual_portions",
        )
        if st.button(
            t("feed_now"),
            type="primary",
            icon=":material/bolt:",
            disabled=not online,
            key="control_feed_btn",
        ):
            confirm_feed(int(portions))

with row_one[1]:
    with st.container(border=True):
        st.markdown("### :material/restart_alt:")
        st.subheader(t("device_state"))
        st.caption(t("device_state_sub"))
        first, second, third = st.columns(3)
        first.caption(t("state_tile"))
        first.markdown(f"**{state_label(status.get('state'))}**")
        second.caption(t("sensor_distance"))
        second.markdown(f"**{ui.num(status.get('distance_cm'))} cm**")
        third.caption(t("last_seen"))
        third.markdown(f"**{ui.fmt_datetime(status.get('measured_at'))}**")
        if st.button(
            t("request_fresh"),
            icon=":material/refresh:",
            disabled=not online,
            key="control_state",
        ):
            try:
                result = client_command(device, "get_state")
            except Exception as exc:
                notify_failure(exc)
            else:
                notify_command(result, "state_requested")
            st.rerun()

row_two = st.columns(2)

with row_two[0]:
    with st.container(border=True):
        st.markdown("### :material/tune:")
        st.subheader(t("feed_threshold"))
        st.caption(t("feed_threshold_sub"))
        if "threshold" not in st.session_state:
            st.session_state["threshold"] = int(
                device["low_feed_threshold_pct"] or 20
            )
        threshold = st.slider(
            t("feed_threshold"),
            5,
            50,
            step=5,
            key="threshold",
            label_visibility="collapsed",
        )
        value_col, badge_col = st.columns([1, 2], vertical_alignment="center")
        value_col.markdown(f"### {threshold}%")
        with badge_col:
            ui.badge(t("low_feed_alert"), "warning")
        if st.button(
            t("apply_threshold"),
            icon=":material/send:",
            disabled=not online,
            key="apply_threshold",
        ):
            db.set_low_feed_threshold(device["id"], int(threshold))
            try:
                result = client_command(
                    device, "set_threshold", {"threshold_pct": int(threshold)}
                )
            except Exception as exc:
                notify_failure(exc)
            else:
                notify_command(result, "threshold_sent", pct=int(threshold))
            st.rerun()

with row_two[1]:
    with st.container(border=True):
        st.markdown("### :material/schedule:")
        st.subheader(t("device_clock"))
        st.caption(t("device_clock_sub"))
        date_col, time_col = st.columns(2)
        when = date_col.date_input(
            t("date"), value=datetime.now().date(), key="rtc_date"
        )
        clock = time_col.time_input(
            t("time_label"),
            value=datetime.now().time().replace(microsecond=0),
            key="rtc_time",
        )
        if st.button(
            t("sync_rtc"),
            icon=":material/schedule:",
            disabled=not online,
            key="sync_rtc",
        ):
            payload = {
                "datetime": datetime.combine(when, clock).strftime("%Y-%m-%dT%H:%M:%S")
            }
            try:
                result = client_command(device, "set_rtc", payload)
            except Exception as exc:
                notify_failure(exc)
            else:
                notify_command(result, "rtc_sent")
            st.rerun()

with st.container(border=True):
    head_left, head_right = st.columns([3, 1], vertical_alignment="center")
    head_left.subheader(t("command_activity"))
    head_left.caption(t("command_activity_sub"))
    with head_right:
        with st.container(horizontal=True, horizontal_alignment="right"):
            ui.badge(t("ack_timeout_badge"), "neutral")

    commands = data.recent_commands(device["id"])
    if not commands:
        ui.empty_state("receipt_long", t("no_commands"), t("no_commands"))
    else:
        for command in commands:
            icon_col, body_col, time_col, badge_col = st.columns(
                [0.4, 5, 2, 1.3], vertical_alignment="center"
            )
            icon_col.markdown(":material/terminal:")
            with body_col:
                st.markdown(f"**{command['type']}**")
                payload = str(command["payload"] or "")
                if len(payload) > 64:
                    payload = payload[:61] + "…"
                st.caption(f"{command['command_id'][:20]} · {payload}")
            time_col.caption(ui.fmt_when(command["created_at"]))
            with badge_col:
                ui.badge(
                    status_label(command["status"]),
                    ui.STATUS_TONE.get(command["status"], "neutral"),
                )
