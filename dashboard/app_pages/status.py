"""Status / overview page: is the feeder healthy and what happens next?"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import data
import ui
from actions import client_command, confirm_feed, notify_command, notify_failure
from i18n import state_label, status_label, t

device = st.session_state["device"]


@st.fragment(run_every="2s")
def render() -> None:
    status = data.status_of(device["id"])
    if not status or status.get("measured_at") is None:
        st.info(t("no_telemetry"))
        return

    level = status["feed_level_pct"]
    threshold = status["low_feed_threshold_pct"] or 0
    online = bool(status["is_online"])
    schedules = data.schedules(device["id"])
    active = [item for item in schedules if item["is_active"]]
    upcoming = ui.next_run(active)
    next_time = upcoming[0].strftime("%H:%M") if upcoming else "—"

    if status["is_empty"]:
        headline = t("welcome_empty")
        sub = t("welcome_no_schedule")
    elif status["is_low"]:
        headline = t("welcome_low")
        sub = t("welcome_sub", time=next_time) if upcoming else t("welcome_no_schedule")
    else:
        headline = t("welcome_ok")
        sub = t("welcome_sub", time=next_time) if upcoming else t("welcome_no_schedule")

    head_left, head_right = st.columns([3, 1], vertical_alignment="bottom")
    with head_left:
        st.caption(t("welcome_eyebrow"))
        st.subheader(headline)
        st.caption(sub)
    head_right.caption(f"{t('updated')} {datetime.now():%H:%M}")

    if status["is_empty"]:
        st.error(t("welcome_empty"), icon=":material/error:")
    elif status["is_low"]:
        st.warning(t("welcome_low"), icon=":material/warning:")
    else:
        st.success(t("welcome_ok"), icon=":material/check_circle:")

    rows = data.telemetry(
        device["id"], data.sql_stamp(data.sql_now() - timedelta(days=7))
    )
    frame = (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(columns=["recorded_at", "feed_level_pct"])
    )
    if not frame.empty:
        frame["recorded_at"] = pd.to_datetime(frame["recorded_at"])
        frame["feed_level_pct"] = pd.to_numeric(
            frame["feed_level_pct"], errors="coerce"
        )

    left, right = st.columns([1.1, 1.4], gap="medium")

    with left:
        with st.container(border=True, key="card_hero"):
            st.caption(t("feed_remaining"))
            st.subheader(t("hopper_level"))
            if status["is_empty"]:
                ui.badge(t("badge_empty"), "critical")
            elif status["is_low"]:
                ui.badge(t("badge_low"), "warning")
            else:
                ui.badge(t("badge_healthy"), "healthy")
            estimate = ui.days_left(frame, level)
            caption = (
                t("days_left", days=max(1, round(estimate)))
                if estimate is not None
                else t("days_left_unknown")
            )
            ui.feed_hero(level, threshold, t("alert_threshold"), caption)

    with right:
        first, second = st.columns(2)
        with first:
            ui.metric_card(
                "straighten",
                t("sensor_distance"),
                f"{ui.num(status['distance_cm'])} cm",
                t("normal_range"),
            )
        with second:
            ui.metric_card(
                "settings_input_component",
                t("device_state"),
                state_label(status["state"]),
                t("servo_ready"),
            )
        third, fourth = st.columns(2)
        with third:
            ui.metric_card(
                "wifi",
                t("connection"),
                "Online" if online else "Offline",
                t("signal_stable"),
            )
        with fourth:
            age = ui.seconds_since(status["measured_at"])
            ui.metric_card(
                "schedule",
                t("last_seen"),
                f"{age if age is not None else '—'} {t('seconds_short')}",
                t("latest_telemetry"),
            )

    schedule_col, activity_col = st.columns(2)
    with schedule_col:
        with st.container(border=True):
            st.caption(t("today"))
            st.subheader(t("next_schedule"))
            if upcoming:
                when, seconds = upcoming
                st.markdown(f"### :material/schedule: {when:%H:%M}")
                st.caption(t("in_duration", duration=ui.duration_text(seconds)))
                for item in active:
                    st.markdown(
                        f":material/circle: {item['feed_time'][:5]} · "
                        f"**{item['name']}**"
                    )
            else:
                st.caption(t("no_active_schedule"))
            st.page_link(
                "app_pages/schedules.py",
                label=t("manage"),
                icon=":material/chevron_right:",
            )

    with activity_col:
        with st.container(border=True):
            st.caption(t("latest_activity"))
            st.subheader(t("feeding_event"))
            latest = data.latest_feeding_log(device["id"])
            if latest:
                ui.badge(
                    status_label(latest["status"]),
                    "success" if latest["status"] == "success" else "critical",
                )
                name = latest["schedule_name"] or t("manual")
                st.markdown(f"### :material/check_circle: {name}")
                st.caption(
                    f"{ui.fmt_when(latest['requested_at'])} · "
                    f"{latest['portions']} {t('portions')}"
                )
                before, after = st.columns(2)
                before.metric(t("before"), ui.level_text(latest["feed_level_before_pct"]))
                after.metric(t("after"), ui.level_text(latest["feed_level_after_pct"]))
            else:
                st.caption(t("no_feeding_yet"))


render()

# Quick actions live outside the auto-refreshing fragment so the confirmation
# dialog is never re-entered by the 2-second tick.
status = data.status_of(device["id"])
online = bool(status and status["is_online"])

with st.container(border=True, key="card_quick"):
    text_col, action_col = st.columns([3, 2], vertical_alignment="center")
    with text_col:
        st.markdown(f"**{t('quick_actions')}**")
        st.caption(t("quick_actions_sub"))
    with action_col:
        with st.container(horizontal=True, horizontal_alignment="right"):
            if st.button(
                t("feed_now"),
                icon=":material/bolt:",
                type="primary",
                disabled=not online,
                key="quick_feed",
            ):
                confirm_feed(int(st.session_state.get("manual_portions", 2)))
            if st.button(
                t("request_state"),
                icon=":material/restart_alt:",
                disabled=not online,
                key="quick_state",
            ):
                try:
                    result = client_command(device, "get_state")
                except Exception as exc:
                    notify_failure(exc)
                else:
                    notify_command(result, "state_requested")
                st.rerun()
