"""Presentation helpers shared by the dashboard pages.

Native Streamlit elements do the heavy lifting; the only custom HTML is the
feed-level hero (hopper + threshold track), which has no native equivalent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from i18n import locale

PRIMARY = "#087f70"
WARNING = "#b66a14"
BORDER = "#dfe8e5"

TONE = {
    "healthy": "green",
    "success": "green",
    "warning": "orange",
    "critical": "red",
    "info": "blue",
    "pending": "blue",
    "sent": "blue",
    "timeout": "orange",
    "neutral": "gray",
}

SEVERITY_TONE = {"critical": "red", "warning": "orange", "info": "blue"}
SEVERITY_ICON = {
    "critical": "error",
    "warning": "warning",
    "info": "info",
}
STATUS_TONE = {
    "success": "success",
    "failed": "critical",
    "timeout": "timeout",
    "pending": "pending",
    "sent": "sent",
}


# --------------------------------------------------------------------------- #
# small building blocks
# --------------------------------------------------------------------------- #
def badge(label: str, tone: str = "neutral") -> None:
    st.badge(label, color=TONE.get(tone, "gray"))


def section_head(eyebrow: str | None, title: str, description: str | None = None) -> None:
    if eyebrow:
        st.caption(eyebrow)
    st.subheader(title)
    if description:
        st.caption(description)


def metric_card(icon: str, label: str, value, helper: str | None = None) -> None:
    with st.container(border=True):
        st.metric(label, value, icon=f":material/{icon}:")
        if helper:
            st.caption(helper)


def empty_state(icon: str, title: str, body: str) -> None:
    with st.container(horizontal_alignment="center"):
        st.markdown(f"### :material/{icon}:")
        st.markdown(f"**{title}**")
        st.caption(body)


def toast_after_rerun(message: str, icon: str = ":material/check_circle:") -> None:
    st.session_state["_toast"] = message
    st.session_state["_toast_icon"] = icon


def flush_toast() -> None:
    message = st.session_state.pop("_toast", None)
    icon = st.session_state.pop("_toast_icon", ":material/check_circle:")
    if message:
        st.toast(message, icon=icon)


# --------------------------------------------------------------------------- #
# values / dates
# --------------------------------------------------------------------------- #
def num(value, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def level_text(value) -> str:
    return "—" if value is None else f"{float(value):.0f}%"


def parse_ts(value) -> datetime | None:
    """Parse the UTC timestamps stored in SQLite (or MQTT ISO strings)."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def seconds_since(value) -> int | None:
    moment = parse_ts(value)
    if moment is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - moment).total_seconds()))


def fmt_clock(value) -> str:
    moment = parse_ts(value)
    return moment.astimezone().strftime("%H:%M:%S") if moment else "—"


def fmt_when(value) -> str:
    moment = parse_ts(value)
    if moment is None:
        return "—"
    local = moment.astimezone()
    today = datetime.now().date()
    delta_days = (today - local.date()).days
    if delta_days == 0:
        prefix = "Hari ini" if locale() == "id" else "Today"
    elif delta_days == 1:
        prefix = "Kemarin" if locale() == "id" else "Yesterday"
    else:
        return local.strftime("%d %b %H:%M")
    return f"{prefix}, {local:%H:%M}"


def fmt_datetime(value) -> str:
    """Absolute local date-time, e.g. 20/10/2026 20:12."""
    moment = parse_ts(value)
    return moment.astimezone().strftime("%d/%m/%Y %H:%M") if moment else "—"


def duration_text(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if locale() == "en":
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes or not hours:
            parts.append(f"{minutes}m")
        return " ".join(parts)
    parts = []
    if hours:
        parts.append(f"{hours} jam")
    if minutes or not hours:
        parts.append(f"{minutes} menit")
    return " ".join(parts)


def next_run(schedules, now: datetime | None = None):
    """Earliest active feed time as ``(datetime, seconds_until)``."""
    now = now or datetime.now()
    candidates = []
    for item in schedules:
        raw = (item.get("feed_time") or "")[:5]
        try:
            hour, minute = (int(part) for part in raw.split(":"))
        except (TypeError, ValueError):
            continue
        when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if when <= now:
            when += timedelta(days=1)
        candidates.append(when)
    if not candidates:
        return None
    when = min(candidates)
    return when, int((when - now).total_seconds())


def days_left(frame: pd.DataFrame, level: float | None) -> float | None:
    """Rough days-of-feed estimate from the 7-day telemetry slope."""
    if level is None or frame is None or len(frame) < 2:
        return None
    series = frame.dropna(subset=["feed_level_pct", "recorded_at"])
    if len(series) < 2:
        return None
    first_at = series["recorded_at"].iloc[0]
    last_at = series["recorded_at"].iloc[-1]
    hours = (last_at - first_at).total_seconds() / 3600
    if hours <= 1:
        return None
    drop = float(series["feed_level_pct"].iloc[0]) - float(series["feed_level_pct"].iloc[-1])
    daily = drop / (hours / 24)
    if daily <= 0.3:
        return None
    return max(0.0, float(level) / daily)


# --------------------------------------------------------------------------- #
# charts
# --------------------------------------------------------------------------- #
def feed_chart(frame: pd.DataFrame, threshold: float) -> None:
    base = alt.Chart(frame).encode(
        x=alt.X("recorded_at:T", title=None),
        tooltip=[
            alt.Tooltip("recorded_at:T", title="Waktu", format="%d %b %H:%M"),
            alt.Tooltip("feed_level_pct:Q", title="Sisa pakan", format=".1f"),
        ],
    )
    area = base.mark_area(color=PRIMARY, opacity=0.16).encode(
        y=alt.Y(
            "feed_level_pct:Q",
            title=None,
            scale=alt.Scale(domain=[0, 100]),
        )
    )
    line = base.mark_line(color=PRIMARY, strokeWidth=2).encode(
        y=alt.Y("feed_level_pct:Q", title=None, scale=alt.Scale(domain=[0, 100]))
    )
    rule = (
        alt.Chart(pd.DataFrame({"threshold": [threshold]}))
        .mark_rule(color=WARNING, strokeDash=[4, 4])
        .encode(y=alt.Y("threshold:Q"))
    )
    st.altair_chart((area + line + rule).properties(height=260), theme=None)


# --------------------------------------------------------------------------- #
# feed hero (hopper graphic)
# --------------------------------------------------------------------------- #
_HERO_CSS = """
<style>
.af-hero{display:flex;align-items:center;gap:26px;padding:4px 2px 20px}
.af-hopper{position:relative;width:86px;height:100px;overflow:hidden;border:3px solid #aac4bd;
  border-radius:11px 11px 24px 24px;background:#edf4f2}
.af-hopper::before{content:"";position:absolute;z-index:2;top:5px;left:6px;right:6px;height:7px;
  border-radius:50%;background:#d5e5e0}
.af-fill{position:absolute;left:0;right:0;bottom:0;background:linear-gradient(#69ceb0,#087f70)}
.af-fill::after{content:"";position:absolute;top:-4px;left:-5%;width:110%;height:11px;
  border-radius:50%;background:#7cdbbd}
.af-num{font-family:Manrope,sans-serif;font-size:52px;font-weight:700;letter-spacing:-.06em;
  line-height:1;color:#122521}
.af-num span{font-size:24px;color:#087f70;margin-left:2px}
.af-note{color:#687a75;font-size:12px;margin-top:8px}
.af-threshold{display:flex;justify-content:space-between;color:#687a75;font-size:11px;
  margin-bottom:6px}
.af-threshold strong{color:#b66a14}
.af-track{position:relative;height:8px;border-radius:99px;background:#e7efed}
.af-track .af-bar{display:block;height:100%;border-radius:inherit;background:#087f70}
.af-track .af-tick{position:absolute;z-index:2;top:-2px;width:2px;height:12px;background:#b66a14}
</style>
"""


def feed_hero(level: float | None, threshold: float, threshold_label: str,
              caption: str) -> None:
    pct = 0.0 if level is None else max(0.0, min(100.0, float(level)))
    tick = max(0.0, min(100.0, float(threshold or 0)))
    st.html(
        _HERO_CSS
        + f"""
<div class="af-hero">
  <div class="af-hopper"><div class="af-fill" style="height:{pct:.1f}%"></div></div>
  <div>
    <div class="af-num">{pct:.0f}<span>%</span></div>
    <div class="af-note">{escape(caption)}</div>
  </div>
</div>
<div class="af-threshold"><span>{escape(threshold_label)}</span>
  <strong>{tick:.0f}%</strong></div>
<div class="af-track">
  <span class="af-tick" style="left:{tick:.0f}%"></span>
  <span class="af-bar" style="width:{pct:.1f}%"></span>
</div>
"""
    )
