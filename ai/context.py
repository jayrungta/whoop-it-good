"""
Builds the data context payload to include in AI prompts.
All ORM data is extracted to plain values inside the session to avoid DetachedInstanceError.
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
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_db() as db:
        values = [
            r.hrv_rmssd_milli for r in
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= cutoff)
            .filter(WhoopRecovery.hrv_rmssd_milli.isnot(None))
            .all()
        ]
    return round(mean(values), 1) if values else None


def get_rhr_baseline(days: int = 30) -> float | None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_db() as db:
        values = [
            r.resting_heart_rate for r in
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= cutoff)
            .filter(WhoopRecovery.resting_heart_rate.isnot(None))
            .all()
        ]
    return round(mean(values), 1) if values else None


def build_daily_context(target_date: date | None = None) -> str:
    if target_date is None:
        target_date = date.today()

    window_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc) - timedelta(days=1)
    window_end = window_start + timedelta(days=2)
    seven_day_cutoff = window_start - timedelta(days=7)

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
            "state": r.score_state,
        } if r else None

        s = (
            db.query(WhoopSleep)
            .filter(WhoopSleep.end >= window_start)
            .filter(WhoopSleep.end < window_end)
            .order_by(WhoopSleep.end.desc())
            .first()
        )
        sleep = {
            "total_in_bed_milli": s.total_in_bed_milli,
            "slow_wave_milli": s.slow_wave_milli,
            "rem_sleep_milli": s.rem_sleep_milli,
            "light_sleep_milli": s.light_sleep_milli,
            "awake_count": s.awake_count,
            "performance_pct": s.sleep_performance_pct,
            "efficiency_pct": s.sleep_efficiency_pct,
            "respiratory_rate": s.respiratory_rate,
            "debt_milli": s.sleep_debt_milli,
        } if s else None

        recent_recoveries = [
            {"hrv": r.hrv_rmssd_milli, "score": r.recovery_score}
            for r in db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= seven_day_cutoff)
            .order_by(WhoopRecovery.created_at.desc())
            .all()
        ]

        j = (
            db.query(JournalEntry)
            .filter(JournalEntry.date >= (target_date - timedelta(days=2)))
            .order_by(JournalEntry.date.desc())
            .first()
        )
        journal = {
            "date": str(j.date),
            "alcohol": j.alcohol_units,
            "stress": j.stress_level,
            "late_caffeine": j.late_caffeine,
            "notes": j.notes,
        } if j else None

    hrv_baseline = get_hrv_baseline()
    rhr_baseline = get_rhr_baseline()

    lines = [f"=== Daily Data Context: {target_date} ===\n"]

    if recovery:
        hrv = recovery["hrv"]
        hrv_vs_baseline = ""
        if hrv and hrv_baseline:
            delta_pct = round((hrv - hrv_baseline) / hrv_baseline * 100, 1)
            direction = "↑" if delta_pct >= 0 else "↓"
            hrv_vs_baseline = f" ({direction}{abs(delta_pct)}% vs {hrv_baseline}ms baseline)"
        lines.append(f"RECOVERY: {recovery['score']}% | State: {recovery['state']}")
        lines.append(f"HRV: {hrv}ms{hrv_vs_baseline}")
        lines.append(f"RHR: {recovery['rhr']}bpm (baseline: {rhr_baseline}bpm)")
        lines.append(f"SpO2: {recovery['spo2']}% | Skin temp: {recovery['skin_temp']}°C")
    else:
        lines.append("RECOVERY: No data for this period")

    lines.append("")

    if sleep:
        total_h = _milli_to_hours(sleep["total_in_bed_milli"])
        deep_pct = _pct(sleep["slow_wave_milli"], sleep["total_in_bed_milli"])
        rem_pct = _pct(sleep["rem_sleep_milli"], sleep["total_in_bed_milli"])
        light_pct = _pct(sleep["light_sleep_milli"], sleep["total_in_bed_milli"])
        debt_h = _milli_to_hours(sleep["debt_milli"])
        lines.append(f"SLEEP: {total_h}h in bed | Performance: {sleep['performance_pct']}% | Efficiency: {sleep['efficiency_pct']}%")
        lines.append(f"Stages: {deep_pct}% deep / {rem_pct}% REM / {light_pct}% light")
        lines.append(f"Disturbances: {sleep['awake_count']} | Resp rate: {sleep['respiratory_rate']} rpm")
        lines.append(f"Sleep debt: {debt_h}h" if debt_h else "Sleep debt: unknown")
    else:
        lines.append("SLEEP: No data for this period")

    lines.append("")

    if recent_recoveries:
        hrv_trend = [r["hrv"] for r in recent_recoveries if r["hrv"]]
        rec_trend = [r["score"] for r in recent_recoveries if r["score"]]
        lines.append(f"7-DAY TREND — HRV: {hrv_trend} | Recovery scores: {rec_trend}")

    if journal:
        lines.append("")
        lines.append(f"LAST JOURNAL ({journal['date']}): alcohol={journal['alcohol']} units | stress={journal['stress']}/5 | late_caffeine={journal['late_caffeine']}")
        if journal["notes"]:
            lines.append(f"Notes: {journal['notes']}")

    return "\n".join(lines)


def build_weekly_context(weeks_back: int = 1) -> str:
    end = datetime.now(timezone.utc)
    start = end - timedelta(weeks=weeks_back)
    four_weeks_ago = end - timedelta(weeks=4)

    with get_db() as db:
        recoveries = [
            {"date": str(r.created_at.date()), "hrv": r.hrv_rmssd_milli, "score": r.recovery_score}
            for r in db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= start)
            .order_by(WhoopRecovery.created_at)
            .all()
        ]
        sleeps = [
            {"total_milli": s.total_in_bed_milli, "debt_milli": s.sleep_debt_milli}
            for s in db.query(WhoopSleep)
            .filter(WhoopSleep.end >= start)
            .order_by(WhoopSleep.end)
            .all()
        ]
        workouts = [
            {"sport": w.sport_name, "strain": w.strain_score}
            for w in db.query(WhoopWorkout)
            .filter(WhoopWorkout.start >= start)
            .order_by(WhoopWorkout.start)
            .all()
        ]
        journals = [
            {"date": str(j.date), "alcohol": j.alcohol_units, "stress": j.stress_level,
             "late_caffeine": j.late_caffeine, "notes": j.notes}
            for j in db.query(JournalEntry)
            .filter(JournalEntry.date >= start.date())
            .order_by(JournalEntry.date)
            .all()
        ]
        prev_hrvs = [
            r.hrv_rmssd_milli for r in
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= four_weeks_ago)
            .filter(WhoopRecovery.created_at < start)
            .filter(WhoopRecovery.hrv_rmssd_milli.isnot(None))
            .all()
        ]

    lines = [f"=== Weekly Data Context: {start.date()} to {end.date()} ===\n"]

    if recoveries:
        hrv_vals = [r["hrv"] for r in recoveries if r["hrv"]]
        rec_scores = [r["score"] for r in recoveries if r["score"]]
        lines.append(f"RECOVERY SCORES: {rec_scores}")
        lines.append(f"HRV VALUES (ms): {hrv_vals}")
        if hrv_vals:
            lines.append(f"HRV avg this week: {round(mean(hrv_vals), 1)}ms")
        if prev_hrvs:
            lines.append(f"HRV avg prev 4 weeks: {round(mean(prev_hrvs), 1)}ms")

    lines.append("")

    if sleeps:
        total_hours = [_milli_to_hours(s["total_milli"]) for s in sleeps if s["total_milli"]]
        debt = _milli_to_hours(sleeps[-1]["debt_milli"]) if sleeps[-1]["debt_milli"] else "unknown"
        lines.append(f"SLEEP (hours each night): {total_hours}")
        lines.append(f"Sleep debt end of week: {debt}h")

    lines.append("")

    if workouts:
        lines.append(f"WORKOUTS: {[w['sport'] for w in workouts]}")
        lines.append(f"Strain scores: {[w['strain'] for w in workouts if w['strain']]}")

    lines.append("")

    for j in journals:
        lines.append(f"JOURNAL {j['date']}: alcohol={j['alcohol']}, stress={j['stress']}/5, late_caffeine={j['late_caffeine']}, notes={j['notes']}")

    return "\n".join(lines)


def build_qa_context(question: str, days: int = 14) -> str:
    daily = build_daily_context()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with get_db() as db:
        recoveries = [
            {"date": str(r.created_at.date()), "hrv": r.hrv_rmssd_milli, "score": r.recovery_score}
            for r in db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= cutoff)
            .order_by(WhoopRecovery.created_at.desc())
            .limit(14)
            .all()
        ]
        journals = [
            {"date": str(j.date), "alcohol": j.alcohol_units, "stress": j.stress_level, "late_caffeine": j.late_caffeine}
            for j in db.query(JournalEntry)
            .filter(JournalEntry.date >= cutoff.date())
            .order_by(JournalEntry.date.desc())
            .limit(14)
            .all()
        ]

    lines = [
        f"=== Q&A Context (last {days} days) ===",
        "",
        daily,
        "",
        f"HRV TREND (date, ms): {[(r['date'], r['hrv']) for r in recoveries if r['hrv']]}",
        f"RECOVERY TREND (date, score): {[(r['date'], r['score']) for r in recoveries if r['score']]}",
        "",
    ]

    if journals:
        lines.append("RECENT JOURNAL ENTRIES:")
        for j in journals:
            lines.append(f"  {j['date']}: alcohol={j['alcohol']}, stress={j['stress']}/5, late_caffeine={j['late_caffeine']}")

    lines.append(f"\nUSER QUESTION: {question}")
    return "\n".join(lines)
