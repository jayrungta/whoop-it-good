"""Builds and posts the morning health summary to Slack."""

import logging
from datetime import date, datetime, timedelta, timezone

from ai.analyzer import generate_daily_insight, analyze_flags
from ai.context import build_daily_context, get_hrv_baseline, get_rhr_baseline
from ai.flags import run_all_checks
from config.settings import SLACK_USER_ID
from db.database import get_db
from db.models import WhoopRecovery, WhoopSleep

logger = logging.getLogger(__name__)

DASHBOARD_URL = "http://localhost:8501"


def _recovery_emoji(score: int | None) -> str:
    if score is None:
        return "⚪"
    if score >= 67:
        return "🟢"
    if score >= 34:
        return "🟡"
    return "🔴"


def _milli_to_hm(ms: int | None) -> str:
    if not ms:
        return "—"
    total_min = int(ms / 60_000)
    return f"{total_min // 60}h {total_min % 60}m"


def _pct(part: int | None, total: int | None) -> str:
    if not part or not total or total == 0:
        return "—"
    return f"{round(part / total * 100)}%"


def _get_today_data(target_date: date) -> dict:
    """Pull today's recovery and sleep as plain dicts within one session."""
    window_start = datetime(target_date.year, target_date.month, target_date.day,
                            tzinfo=timezone.utc) - timedelta(days=1)
    window_end = window_start + timedelta(days=2)

    with get_db() as db:
        r = (
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= window_start)
            .filter(WhoopRecovery.created_at < window_end)
            .order_by(WhoopRecovery.created_at.desc())
            .first()
        )
        recovery = {
            "score": r.recovery_score,
            "hrv": r.hrv_rmssd_milli,
            "rhr": r.resting_heart_rate,
            "spo2": r.spo2_percentage,
            "skin_temp": r.skin_temp_celsius,
        } if r else {}

        s = (
            db.query(WhoopSleep)
            .filter(WhoopSleep.end >= window_start)
            .filter(WhoopSleep.end < window_end)
            .filter(WhoopSleep.nap.isnot(True))
            .order_by(WhoopSleep.end.desc())
            .first()
        )
        sleep = {
            "total_milli": s.total_in_bed_milli,
            "deep_milli": s.slow_wave_milli,
            "rem_milli": s.rem_sleep_milli,
            "light_milli": s.light_sleep_milli,
            "performance_pct": s.sleep_performance_pct,
            "efficiency_pct": s.sleep_efficiency_pct,
            "disturbances": s.awake_count,
            "debt_milli": s.sleep_debt_milli,
            "respiratory_rate": s.respiratory_rate,
        } if s else {}

    return {"recovery": recovery, "sleep": sleep}


def build_morning_message(target_date: date | None = None) -> str:
    target_date = target_date or date.today()
    data = _get_today_data(target_date)
    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()
    flags = run_all_checks(hrv_baseline=hrv_baseline)
    context = build_daily_context(target_date)

    rec = data["recovery"]
    slp = data["sleep"]

    lines = [f"*Morning Health Summary — {target_date}*", ""]

    # ---- Recovery block ----
    score = rec.get("score")
    emoji = _recovery_emoji(score)
    score_str = f"{score}%" if score is not None else "Pending"
    recovery_label = (
        "Green — high readiness" if score and score >= 67
        else "Moderate readiness" if score and score >= 34
        else "Red — take it easy" if score is not None
        else "Score pending"
    )
    lines.append(f"{emoji} *Recovery: {score_str}* — {recovery_label}")

    hrv = rec.get("hrv")
    if hrv:
        hrv = round(hrv, 1)
        if hrv_baseline:
            delta_pct = round((hrv - hrv_baseline) / hrv_baseline * 100, 1)
            direction = "↑" if delta_pct >= 0 else "↓"
            lines.append(f"HRV: {hrv}ms  {direction}{abs(delta_pct)}% vs your {hrv_baseline}ms baseline")
        else:
            lines.append(f"HRV: {hrv}ms")

    rhr = rec.get("rhr")
    if rhr:
        rhr_delta = f"  ({'+' if rhr >= (rhr_baseline or rhr) else ''}{round(rhr - rhr_baseline)} vs baseline)" if rhr_baseline else ""
        lines.append(f"RHR: {rhr}bpm{rhr_delta}")

    spo2 = rec.get("spo2")
    skin_temp = rec.get("skin_temp")
    if spo2:
        parts = [f"SpO2: {round(spo2, 1)}%"]
        if skin_temp:
            parts.append(f"Skin temp: {round(skin_temp, 1)}°C")
        lines.append("  |  ".join(parts))

    # ---- Sleep block ----
    lines.append("")
    if slp:
        total_str = _milli_to_hm(slp.get("total_milli"))
        deep_pct = _pct(slp.get("deep_milli"), slp.get("total_milli"))
        rem_pct = _pct(slp.get("rem_milli"), slp.get("total_milli"))
        light_pct = _pct(slp.get("light_milli"), slp.get("total_milli"))
        debt_str = _milli_to_hm(slp.get("debt_milli"))

        perf = round(slp["performance_pct"], 1) if slp.get("performance_pct") else "—"
        eff = round(slp["efficiency_pct"], 1) if slp.get("efficiency_pct") else "—"
        lines.append(f"*Sleep: {total_str}*  |  Perf: {perf}%  |  Efficiency: {eff}%")
        lines.append(f"Stages: {deep_pct} deep  /  {rem_pct} REM  /  {light_pct} light")
        if slp.get("disturbances") is not None:
            lines.append(f"Disturbances: {slp['disturbances']}  |  Sleep debt: {debt_str}")
    else:
        lines.append("_Sleep data not yet available_")

    # ---- Flags ----
    if flags:
        lines.append("")
        for flag in flags:
            icon = "🚨" if flag.severity == "alert" else "⚠️"
            lines.append(f"{icon} {flag.message}")

    # ---- AI insight ----
    lines.append("")
    try:
        insight = generate_daily_insight(context, flags)
        lines.append(f"_{insight}_")
    except Exception as e:
        logger.warning(f"Could not generate insight: {e}")

    lines.append("")
    lines.append(f"<{DASHBOARD_URL}|View Dashboard →>")

    return "\n".join(lines)


async def post_morning_message(client, target_date: date | None = None):
    text = build_morning_message(target_date)
    try:
        await client.chat_postMessage(channel=SLACK_USER_ID, text=text)
        logger.info("Morning message posted to Slack")
    except Exception as e:
        logger.error(f"Failed to post morning message: {e}")
