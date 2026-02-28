"""
Builds the data context payload to include in Claude prompts.
Pulls relevant records from DB and formats them as readable text.
"""

from datetime import date, datetime, timedelta, timezone
from statistics import mean

from db.database import get_db
from db.models import AIInsight, JournalEntry, WhoopCycle, WhoopRecovery, WhoopSleep, WhoopWorkout


def _milli_to_hours(ms: int | None) -> float | None:
    if ms is None:
        return None
    return round(ms / 3_600_000, 2)


def _pct(part: int | None, total: int | None) -> float | None:
    if not part or not total or total == 0:
        return None
    return round((part / total) * 100, 1)


def get_hrv_baseline(days: int = 30) -> float | None:
    """30-day rolling HRV average."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_db() as db:
        rows = (
            db.query(WhoopRecovery.hrv_rmssd_milli)
            .filter(WhoopRecovery.created_at >= cutoff)
            .filter(WhoopRecovery.hrv_rmssd_milli.isnot(None))
            .all()
        )
    values = [r[0] for r in rows]
    return round(mean(values), 1) if values else None


def get_rhr_baseline(days: int = 30) -> float | None:
    """30-day rolling RHR average."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_db() as db:
        rows = (
            db.query(WhoopRecovery.resting_heart_rate)
            .filter(WhoopRecovery.created_at >= cutoff)
            .filter(WhoopRecovery.resting_heart_rate.isnot(None))
            .all()
        )
    values = [r[0] for r in rows]
    return round(mean(values), 1) if values else None


def build_daily_context(target_date: date | None = None) -> str:
    """Build context string for morning summary."""
    if target_date is None:
        target_date = date.today()

    window_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc) - timedelta(days=1)
    window_end = window_start + timedelta(days=2)

    with get_db() as db:
        recovery = (
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= window_start)
            .filter(WhoopRecovery.created_at < window_end)
            .order_by(WhoopRecovery.created_at.desc())
            .first()
        )

        sleep = (
            db.query(WhoopSleep)
            .filter(WhoopSleep.end >= window_start)
            .filter(WhoopSleep.end < window_end)
            .order_by(WhoopSleep.end.desc())
            .first()
        )

        # Last 7 days recovery for trend
        seven_day_cutoff = window_start - timedelta(days=7)
        recent_recoveries = (
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= seven_day_cutoff)
            .order_by(WhoopRecovery.created_at.desc())
            .all()
        )

        # Recent journal entry
        journal = (
            db.query(JournalEntry)
            .filter(JournalEntry.date >= (target_date - timedelta(days=2)))
            .order_by(JournalEntry.date.desc())
            .first()
        )

    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()

    lines = [f"=== Daily Data Context: {target_date} ===\n"]

    if recovery:
        hrv = recovery.hrv_rmssd_milli
        hrv_vs_baseline = ""
        if hrv and hrv_baseline:
            delta_pct = round((hrv - hrv_baseline) / hrv_baseline * 100, 1)
            direction = "↑" if delta_pct >= 0 else "↓"
            hrv_vs_baseline = f" ({direction}{abs(delta_pct)}% vs {hrv_baseline}ms baseline)"

        lines.append(f"RECOVERY: {recovery.recovery_score}% | State: {recovery.score_state}")
        lines.append(f"HRV: {hrv}ms{hrv_vs_baseline}")
        lines.append(f"RHR: {recovery.resting_heart_rate}bpm (baseline: {rhr_baseline}bpm)")
        lines.append(f"SpO2: {recovery.spo2_percentage}% | Skin temp: {recovery.skin_temp_celsius}°C")
    else:
        lines.append("RECOVERY: No data for this period")

    lines.append("")

    if sleep:
        total_h = _milli_to_hours(sleep.total_in_bed_milli)
        deep_pct = _pct(sleep.slow_wave_milli, sleep.total_in_bed_milli)
        rem_pct = _pct(sleep.rem_sleep_milli, sleep.total_in_bed_milli)
        light_pct = _pct(sleep.light_sleep_milli, sleep.total_in_bed_milli)
        debt_h = _milli_to_hours(sleep.sleep_debt_milli)

        lines.append(f"SLEEP: {total_h}h in bed | Performance: {sleep.sleep_performance_pct}% | Efficiency: {sleep.sleep_efficiency_pct}%")
        lines.append(f"Stages: {deep_pct}% deep / {rem_pct}% REM / {light_pct}% light")
        lines.append(f"Disturbances: {sleep.awake_count} | Resp rate: {sleep.respiratory_rate} rpm")
        lines.append(f"Sleep debt: {debt_h}h" if debt_h else "Sleep debt: unknown")
    else:
        lines.append("SLEEP: No data for this period")

    lines.append("")

    if recent_recoveries:
        hrv_trend = [r.hrv_rmssd_milli for r in recent_recoveries if r.hrv_rmssd_milli]
        rec_trend = [r.recovery_score for r in recent_recoveries if r.recovery_score]
        lines.append(f"7-DAY TREND — HRV: {hrv_trend} | Recovery scores: {rec_trend}")

    if journal:
        lines.append("")
        lines.append(f"LAST JOURNAL ({journal.date}): alcohol={journal.alcohol_units} units | stress={journal.stress_level}/5 | late_caffeine={journal.late_caffeine}")
        if journal.notes:
            lines.append(f"Notes: {journal.notes}")

    return "\n".join(lines)


def build_weekly_context(weeks_back: int = 1) -> str:
    """Build context for weekly report."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(weeks=weeks_back)
    four_weeks_ago = end - timedelta(weeks=4)

    with get_db() as db:
        recoveries = (
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= start)
            .order_by(WhoopRecovery.created_at)
            .all()
        )
        sleeps = (
            db.query(WhoopSleep)
            .filter(WhoopSleep.end >= start)
            .order_by(WhoopSleep.end)
            .all()
        )
        workouts = (
            db.query(WhoopWorkout)
            .filter(WhoopWorkout.start >= start)
            .order_by(WhoopWorkout.start)
            .all()
        )
        journals = (
            db.query(JournalEntry)
            .filter(JournalEntry.date >= start.date())
            .order_by(JournalEntry.date)
            .all()
        )
        # Previous 4 weeks HRV for comparison
        prev_recoveries = (
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= four_weeks_ago)
            .filter(WhoopRecovery.created_at < start)
            .all()
        )

    lines = [f"=== Weekly Data Context: {start.date()} to {end.date()} ===\n"]

    if recoveries:
        hrv_vals = [r.hrv_rmssd_milli for r in recoveries if r.hrv_rmssd_milli]
        rec_scores = [r.recovery_score for r in recoveries if r.recovery_score]
        lines.append(f"RECOVERY SCORES: {rec_scores}")
        lines.append(f"HRV VALUES (ms): {hrv_vals}")
        if hrv_vals:
            lines.append(f"HRV avg this week: {round(mean(hrv_vals), 1)}ms")
        if prev_recoveries:
            prev_hrv = [r.hrv_rmssd_milli for r in prev_recoveries if r.hrv_rmssd_milli]
            if prev_hrv:
                lines.append(f"HRV avg prev 4 weeks: {round(mean(prev_hrv), 1)}ms")

    lines.append("")

    if sleeps:
        total_hours = [_milli_to_hours(s.total_in_bed_milli) for s in sleeps if s.total_in_bed_milli]
        debt_hours = [_milli_to_hours(s.sleep_debt_milli) for s in sleeps if s.sleep_debt_milli]
        lines.append(f"SLEEP (hours each night): {total_hours}")
        lines.append(f"Sleep debt end of week: {debt_hours[-1] if debt_hours else 'unknown'}h")

    lines.append("")

    if workouts:
        strains = [w.strain_score for w in workouts if w.strain_score]
        sports = [w.sport_name for w in workouts]
        lines.append(f"WORKOUTS: {sports}")
        lines.append(f"Strain scores: {strains}")

    lines.append("")

    if journals:
        for j in journals:
            lines.append(f"JOURNAL {j.date}: alcohol={j.alcohol_units}, stress={j.stress_level}/5, late_caffeine={j.late_caffeine}, notes={j.notes}")

    return "\n".join(lines)


def build_qa_context(question: str, days: int = 14) -> str:
    """Build context for a user Q&A question."""
    daily = build_daily_context()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with get_db() as db:
        recoveries = (
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= cutoff)
            .order_by(WhoopRecovery.created_at.desc())
            .limit(14)
            .all()
        )
        journals = (
            db.query(JournalEntry)
            .filter(JournalEntry.date >= cutoff.date())
            .order_by(JournalEntry.date.desc())
            .limit(14)
            .all()
        )

    hrv_trend = [(str(r.created_at.date()), r.hrv_rmssd_milli) for r in recoveries if r.hrv_rmssd_milli]
    rec_trend = [(str(r.created_at.date()), r.recovery_score) for r in recoveries if r.recovery_score]

    lines = [
        f"=== Q&A Context (last {days} days) ===",
        "",
        daily,
        "",
        f"HRV TREND (date, ms): {hrv_trend}",
        f"RECOVERY TREND (date, score): {rec_trend}",
        "",
    ]

    if journals:
        lines.append("RECENT JOURNAL ENTRIES:")
        for j in journals:
            lines.append(f"  {j.date}: alcohol={j.alcohol_units}, stress={j.stress_level}/5, late_caffeine={j.late_caffeine}")

    lines.append(f"\nUSER QUESTION: {question}")
    return "\n".join(lines)
