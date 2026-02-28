"""
Proactive flag detection — runs each morning and mid-day.
Returns a list of active Flag objects when thresholds are breached.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import NamedTuple

from db.database import get_db
from db.models import WhoopRecovery, WhoopSleep, WhoopCycle
from config.settings import (
    HRV_DROP_THRESHOLD_PCT,
    HRV_DROP_CONSECUTIVE_DAYS,
    LOW_RECOVERY_THRESHOLD,
    LOW_RECOVERY_CONSECUTIVE_DAYS,
    SLEEP_DEBT_THRESHOLD_HOURS,
    SLEEP_DEBT_WINDOW_DAYS,
    SKIN_TEMP_SPIKE_C,
    STRAIN_OVERLOAD_DAYS,
)


@dataclass
class Flag:
    key: str
    severity: str        # "warn" | "alert"
    message: str
    data: dict


def _get_recent_recoveries(days: int) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_db() as db:
        return (
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= cutoff)
            .order_by(WhoopRecovery.created_at.desc())
            .all()
        )


def check_hrv_drop(hrv_baseline: float | None) -> Flag | None:
    """Flag if HRV has been >15% below 30-day baseline for 3+ consecutive days."""
    if not hrv_baseline:
        return None

    rows = _get_recent_recoveries(HRV_DROP_CONSECUTIVE_DAYS + 2)
    recent = [r for r in rows if r.hrv_rmssd_milli is not None][:HRV_DROP_CONSECUTIVE_DAYS]

    if len(recent) < HRV_DROP_CONSECUTIVE_DAYS:
        return None

    threshold = hrv_baseline * (1 - HRV_DROP_THRESHOLD_PCT)
    if all(r.hrv_rmssd_milli < threshold for r in recent):
        avg = round(mean(r.hrv_rmssd_milli for r in recent), 1)
        drop_pct = round((hrv_baseline - avg) / hrv_baseline * 100, 1)
        return Flag(
            key="hrv_drop",
            severity="alert",
            message=(
                f"HRV has been {drop_pct}% below your {hrv_baseline}ms baseline "
                f"for {HRV_DROP_CONSECUTIVE_DAYS} consecutive days (avg: {avg}ms). "
                "Your body is under strain — consider a rest day."
            ),
            data={"avg_hrv": avg, "baseline": hrv_baseline, "drop_pct": drop_pct},
        )
    return None


def check_low_recovery() -> Flag | None:
    """Flag if recovery has been in red zone (<33%) for 3+ consecutive days."""
    rows = _get_recent_recoveries(LOW_RECOVERY_CONSECUTIVE_DAYS + 2)
    recent = [r for r in rows if r.recovery_score is not None][:LOW_RECOVERY_CONSECUTIVE_DAYS]

    if len(recent) < LOW_RECOVERY_CONSECUTIVE_DAYS:
        return None

    if all(r.recovery_score < LOW_RECOVERY_THRESHOLD for r in recent):
        scores = [r.recovery_score for r in recent]
        return Flag(
            key="low_recovery",
            severity="alert",
            message=(
                f"Recovery has been in the red zone (<{LOW_RECOVERY_THRESHOLD}%) "
                f"for {LOW_RECOVERY_CONSECUTIVE_DAYS} days in a row: {scores}. "
                "Prioritize sleep and reduce training load."
            ),
            data={"scores": scores},
        )
    return None


def check_sleep_debt() -> Flag | None:
    """Flag if sleep debt is accumulating (>2 hours over 5 days)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=SLEEP_DEBT_WINDOW_DAYS)
    with get_db() as db:
        sleeps = (
            db.query(WhoopSleep)
            .filter(WhoopSleep.end >= cutoff)
            .filter(WhoopSleep.sleep_debt_milli.isnot(None))
            .order_by(WhoopSleep.end.desc())
            .all()
        )

    if not sleeps:
        return None

    latest_debt_h = sleeps[0].sleep_debt_milli / 3_600_000
    if latest_debt_h > SLEEP_DEBT_THRESHOLD_HOURS:
        return Flag(
            key="sleep_debt",
            severity="warn",
            message=(
                f"Sleep debt is {round(latest_debt_h, 1)}h — above your {SLEEP_DEBT_THRESHOLD_HOURS}h threshold. "
                "Aim for an earlier bedtime tonight."
            ),
            data={"debt_hours": round(latest_debt_h, 1)},
        )
    return None


def check_skin_temp_spike() -> Flag | None:
    """Flag significant skin temp spike (>0.5°C above recent baseline)."""
    rows = _get_recent_recoveries(14)
    temps = [r.skin_temp_celsius for r in rows if r.skin_temp_celsius is not None]

    if len(temps) < 5:
        return None

    baseline = mean(temps[1:])   # exclude most recent
    latest = temps[0]
    delta = latest - baseline

    if delta > SKIN_TEMP_SPIKE_C:
        return Flag(
            key="skin_temp",
            severity="alert",
            message=(
                f"Skin temp spiked +{round(delta, 2)}°C above your recent baseline "
                f"({round(latest, 2)}°C vs {round(baseline, 2)}°C avg). Possible early illness signal."
            ),
            data={"latest": round(latest, 2), "baseline": round(baseline, 2), "delta": round(delta, 2)},
        )
    return None


def check_strain_overload() -> Flag | None:
    """Flag if high strain is consistently outpacing low recovery for 5+ days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=STRAIN_OVERLOAD_DAYS)
    with get_db() as db:
        cycles = (
            db.query(WhoopCycle)
            .filter(WhoopCycle.start >= cutoff)
            .filter(WhoopCycle.strain_score.isnot(None))
            .order_by(WhoopCycle.start.desc())
            .all()
        )
        recoveries = (
            db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= cutoff)
            .filter(WhoopRecovery.recovery_score.isnot(None))
            .order_by(WhoopRecovery.created_at.desc())
            .all()
        )

    if len(cycles) < STRAIN_OVERLOAD_DAYS or len(recoveries) < STRAIN_OVERLOAD_DAYS:
        return None

    # High strain (≥14) paired with low/moderate recovery (<67%) every day
    overloaded_days = sum(
        1 for c, r in zip(cycles[:STRAIN_OVERLOAD_DAYS], recoveries[:STRAIN_OVERLOAD_DAYS])
        if (c.strain_score or 0) >= 14 and (r.recovery_score or 100) < 67
    )

    if overloaded_days >= STRAIN_OVERLOAD_DAYS:
        avg_strain = round(mean(c.strain_score for c in cycles[:STRAIN_OVERLOAD_DAYS] if c.strain_score), 1)
        avg_rec = round(mean(r.recovery_score for r in recoveries[:STRAIN_OVERLOAD_DAYS] if r.recovery_score), 1)
        return Flag(
            key="strain_overload",
            severity="alert",
            message=(
                f"High strain (avg {avg_strain}) has outpaced recovery (avg {avg_rec}%) "
                f"for {STRAIN_OVERLOAD_DAYS} consecutive days. You're accumulating fatigue."
            ),
            data={"avg_strain": avg_strain, "avg_recovery": avg_rec},
        )
    return None


def run_all_checks(hrv_baseline: float | None = None) -> list[Flag]:
    """Run all flag checks and return active flags."""
    checkers = [
        lambda: check_hrv_drop(hrv_baseline),
        check_low_recovery,
        check_sleep_debt,
        check_skin_temp_spike,
        check_strain_overload,
    ]
    flags = []
    for checker in checkers:
        try:
            flag = checker()
            if flag:
                flags.append(flag)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Flag check failed: {e}")
    return flags
