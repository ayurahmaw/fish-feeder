"""Live page: sensor telemetry chart and the raw MQTT message stream."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

import data
import ui
from i18n import t
from runtime import get_runtime

device = st.session_state["device"]
runtime = get_runtime()


@st.fragment(run_every="2s")
def render() -> None:
    status = data.status_of(device["id"]) or {}
    threshold = float(status.get("low_feed_threshold_pct") or 20)

    with st.container(border=True):
        head_left, head_right = st.columns([3, 2], vertical_alignment="center")
        head_left.subheader(t("feed_level"))
        head_left.caption(t("live_sub"))
        hours = head_right.segmented_control(
            t("range"),
            options=[1, 6, 24],
            default=24,
            required=True,
            key="live_range",
            format_func=lambda value: t("hour_short", n=value),
            label_visibility="collapsed",
        ) or 24

        rows = data.telemetry(
            device["id"], data.sql_stamp(data.sql_now() - timedelta(hours=hours))
        )
        frame = pd.DataFrame(rows) if rows else pd.DataFrame()
        if not frame.empty:
            frame["recorded_at"] = pd.to_datetime(frame["recorded_at"])
            frame["feed_level_pct"] = pd.to_numeric(
                frame["feed_level_pct"], errors="coerce"
            )
            frame = frame.dropna(subset=["feed_level_pct"])

        latest = frame.iloc[-1] if not frame.empty else None
        first_col, second_col, third_col = st.columns([1, 1, 2], vertical_alignment="bottom")
        first_col.metric(
            t("current"),
            ui.level_text(latest["feed_level_pct"]) if latest is not None else "—",
        )
        second_col.metric(
            t("distance"),
            f"{ui.num(latest['distance_cm'])} cm" if latest is not None else "—",
        )
        with third_col:
            with st.container(horizontal=True, horizontal_alignment="right"):
                ui.badge(t("refresh_2s"), "healthy")

        if latest is None:
            ui.empty_state("show_chart", t("no_telemetry_range"), t("no_telemetry_range"))
        else:
            ui.feed_chart(frame[["recorded_at", "feed_level_pct"]], threshold)
            st.caption(
                f"{t('legend_remaining')} · {t('legend_threshold', pct=int(threshold))} · "
                f"{t('telemetry_points', n=len(frame), h=hours)}"
            )

    with st.container(border=True):
        head_left, head_right = st.columns([3, 3], vertical_alignment="center")
        head_left.subheader(t("mqtt_recent"))
        head_left.caption(t("mqtt_sub"))

        messages = []
        for item in runtime.worker.tail_snapshot():
            messages.append(
                {
                    "time": item["time"],
                    "kind": item["topic"].rsplit("/", 1)[-1],
                    "topic": item["topic"],
                    "payload": item["payload"],
                }
            )

        with head_right:
            with st.container(horizontal=True, horizontal_alignment="right"):
                kind = st.selectbox(
                    t("type_col"),
                    ["all", "telemetry", "status", "ack"],
                    key="mqtt_kind",
                    label_visibility="collapsed",
                    format_func=lambda value: t("all_topics")
                    if value == "all"
                    else value,
                )
                paused = bool(st.session_state.get("live_paused", False))
                if st.button(
                    t("resume") if paused else t("pause"),
                    icon=":material/play_arrow:" if paused else ":material/pause:",
                    key="mqtt_pause",
                ):
                    st.session_state["live_paused"] = not paused
                    if not paused:
                        st.session_state["tail_snapshot"] = messages
                    st.rerun()

        if paused:
            messages = st.session_state.get("tail_snapshot", [])
            st.info(t("paused_notice"), icon=":material/pause_circle:")

        visible = [m for m in messages if kind == "all" or m["kind"] == kind]
        if not visible:
            ui.empty_state("inbox", t("no_messages"), t("no_messages"))
            return

        table = pd.DataFrame(
            {
                t("time_col"): [ui.fmt_clock(item["time"]) for item in visible],
                t("type_col"): [[item["kind"]] for item in visible],
                t("topic_col"): [item["topic"] for item in visible],
                t("payload_col"): [item["payload"] for item in visible],
            }
        )
        st.dataframe(
            table,
            hide_index=True,
            height=300,
            column_config={
                t("type_col"): st.column_config.MultiselectColumn(
                    t("type_col"),
                    options=["telemetry", "status", "ack"],
                    color=["green", "blue", "violet"],
                ),
                t("topic_col"): st.column_config.TextColumn(t("topic_col")),
                t("payload_col"): st.column_config.TextColumn(t("payload_col")),
            },
        )


render()
