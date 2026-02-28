"""
Sync Whoop data into PostgreSQL.
Pulls cycles, recovery, sleep, and workouts — deduplicates by primary ID.

Usage:
    python -m whoop.sync            # full backfill (last 90 days)
    python -m whoop.sync --days 7   # last N days
"""

import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from db.database import get_db
from db.models import WhoopCycle, WhoopRecovery, WhoopSleep, WhoopWorkout
from whoop.client import WhoopClient

logger = logging.getLogger(__name__)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    # Whoop returns ISO strings with trailing Z
    s = s.rstrip("Z").replace("T", " ")
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _sync_cycles(db, records: list[dict]) -> int:
    saved = 0
    for r in records:
        existing = db.get(WhoopCycle, r["id"])
        if existing:
            continue
        score = r.get("score") or {}
        cycle = WhoopCycle(
            id=r["id"],
            user_id=r["user_id"],
            start=_parse_dt(r.get("start")),
            end=_parse_dt(r.get("end")),
            strain_score=score.get("strain"),
            kilojoules=score.get("kilojoule"),
            avg_heart_rate=score.get("average_heart_rate"),
            max_heart_rate=score.get("max_heart_rate"),
            score_state=r.get("score_state"),
        )
        db.add(cycle)
        saved += 1
    return saved


def _sync_recovery(db, records: list[dict]) -> int:
    saved = 0
    for r in records:
        existing = db.query(WhoopRecovery).filter_by(cycle_id=r["cycle_id"]).first()
        if existing:
            continue
        score = r.get("score") or {}
        rec = WhoopRecovery(
            cycle_id=r["cycle_id"],
            sleep_id=r.get("sleep_id"),
            user_id=r["user_id"],
            recovery_score=score.get("recovery_score"),
            hrv_rmssd_milli=score.get("hrv_rmssd_milli"),
            resting_heart_rate=score.get("resting_heart_rate"),
            spo2_percentage=score.get("spo2_percentage"),
            skin_temp_celsius=score.get("skin_temp_celsius"),
            score_state=r.get("score_state"),
            created_at=_parse_dt(r.get("created_at")),
        )
        db.add(rec)
        saved += 1
    return saved


def _sync_sleep(db, records: list[dict]) -> int:
    saved = 0
    for r in records:
        existing = db.get(WhoopSleep, r["id"])
        if existing:
            continue
        score = r.get("score") or {}
        stage_summary = score.get("stage_summary") or {}
        sleep = WhoopSleep(
            id=r["id"],
            cycle_id=r.get("cycle_id"),
            user_id=r["user_id"],
            start=_parse_dt(r.get("start")),
            end=_parse_dt(r.get("end")),
            total_in_bed_milli=stage_summary.get("total_in_bed_time_milli"),
            light_sleep_milli=stage_summary.get("total_light_sleep_time_milli"),
            slow_wave_milli=stage_summary.get("total_slow_wave_sleep_time_milli"),
            rem_sleep_milli=stage_summary.get("total_rem_sleep_time_milli"),
            awake_count=stage_summary.get("disturbance_count"),
            sleep_cycle_count=stage_summary.get("sleep_cycle_count"),
            sleep_performance_pct=score.get("sleep_performance_percentage"),
            sleep_consistency_pct=score.get("sleep_consistency_percentage"),
            sleep_efficiency_pct=score.get("sleep_efficiency_percentage"),
            respiratory_rate=score.get("respiratory_rate"),
            sleep_debt_milli=score.get("sleep_debt_milli") if score.get("sleep_debt_milli") else None,
            score_state=r.get("score_state"),
        )
        db.add(sleep)
        saved += 1
    return saved


def _sync_workouts(db, records: list[dict]) -> int:
    saved = 0
    for r in records:
        existing = db.get(WhoopWorkout, r["id"])
        if existing:
            continue
        score = r.get("score") or {}
        zones = score.get("zone_duration") or {}
        sport_name = r.get("sport_name") or str(r.get("sport_id", "Unknown"))
        workout = WhoopWorkout(
            id=r["id"],
            cycle_id=r.get("cycle_id"),
            user_id=r["user_id"],
            sport_name=sport_name,
            start=_parse_dt(r.get("start")),
            end=_parse_dt(r.get("end")),
            strain_score=score.get("strain"),
            avg_heart_rate=score.get("average_heart_rate"),
            max_heart_rate=score.get("max_heart_rate"),
            kilojoules=score.get("kilojoule"),
            distance_meter=score.get("distance_meter"),
            zone_zero_milli=zones.get("zone_zero_milli"),
            zone_one_milli=zones.get("zone_one_milli"),
            zone_two_milli=zones.get("zone_two_milli"),
            zone_three_milli=zones.get("zone_three_milli"),
            zone_four_milli=zones.get("zone_four_milli"),
            zone_five_milli=zones.get("zone_five_milli"),
            score_state=r.get("score_state"),
        )
        db.add(workout)
        saved += 1
    return saved


async def sync_all(days: int = 90):
    """Pull all data types for the last `days` days."""
    start = datetime.now(timezone.utc) - timedelta(days=days)

    logger.info(f"Syncing Whoop data for last {days} days...")

    async with WhoopClient() as client:
        cycles_data, recovery_data, sleep_data, workout_data = await asyncio.gather(
            client.get_cycles(start=start),
            client.get_recovery(start=start),
            client.get_sleep(start=start),
            client.get_workouts(start=start),
        )

    with get_db() as db:
        c = _sync_cycles(db, cycles_data)
        r = _sync_recovery(db, recovery_data)
        s = _sync_sleep(db, sleep_data)
        w = _sync_workouts(db, workout_data)

    logger.info(f"Sync complete — cycles: {c}, recovery: {r}, sleep: {s}, workouts: {w}")
    return {"cycles": c, "recovery": r, "sleep": s, "workouts": w}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()

    asyncio.run(sync_all(days=args.days))
