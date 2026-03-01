"""
APScheduler job definitions.
All times are in the configured TIMEZONE.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config.settings import MORNING_HOUR, EVENING_JOURNAL_HOUR, TIMEZONE

logger = logging.getLogger(__name__)


async def _morning_job(slack_client):
    from slack_bot.morning import post_morning_message
    from slack_bot.alerts import notify_sync_success, notify_error
    from whoop.sync import sync_all

    logger.info("Running morning job: sync + morning message")
    try:
        counts = await sync_all(days=3)
        await notify_sync_success("Morning", counts, days=3)
    except Exception as e:
        logger.error(f"Morning sync failed: {e}")
        await notify_error("Morning sync", e)

    await post_morning_message(slack_client)


async def _midday_sync_job(slack_client):
    """Mid-day sync + re-check flags."""
    from whoop.sync import sync_all
    from ai.flags import run_all_checks
    from ai.context import get_hrv_baseline
    from ai.analyzer import analyze_flags
    from slack_bot.alerts import notify_sync_success, notify_error
    from config.settings import SLACK_USER_ID

    logger.info("Running midday sync")
    try:
        counts = await sync_all(days=1)
        await notify_sync_success("Midday", counts, days=1)
    except Exception as e:
        logger.error(f"Midday sync failed: {e}")
        await notify_error("Midday sync", e)
        return

    hrv_baseline = get_hrv_baseline()
    flags = run_all_checks(hrv_baseline=hrv_baseline)
    if flags:
        alert_text = analyze_flags(flags)
        if alert_text:
            await slack_client.chat_postMessage(channel=SLACK_USER_ID, text=f"⚠️ Midday alert:\n{alert_text}")


async def _evening_journal_job(slack_client):
    from journal.flow import send_journal_prompt
    logger.info("Running evening journal prompt")
    await send_journal_prompt(slack_client)


async def _weekly_job(slack_client):
    from whoop.sync import sync_all
    from slack_bot.weekly import post_weekly_report
    from slack_bot.alerts import notify_sync_success, notify_error

    logger.info("Running weekly report job")
    try:
        counts = await sync_all(days=7)
        await notify_sync_success("Weekly", counts, days=7)
    except Exception as e:
        logger.error(f"Weekly sync failed: {e}")
        await notify_error("Weekly sync", e)

    await post_weekly_report(slack_client)


def create_scheduler(slack_client) -> AsyncIOScheduler:
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        _morning_job,
        CronTrigger(hour=MORNING_HOUR, minute=0, timezone=tz),
        args=[slack_client],
        id="morning",
        name="Morning health summary",
        replace_existing=True,
    )

    scheduler.add_job(
        _midday_sync_job,
        CronTrigger(hour=13, minute=0, timezone=tz),
        args=[slack_client],
        id="midday_sync",
        name="Midday sync + flag check",
        replace_existing=True,
    )

    scheduler.add_job(
        _evening_journal_job,
        CronTrigger(hour=EVENING_JOURNAL_HOUR, minute=0, timezone=tz),
        args=[slack_client],
        id="evening_journal",
        name="Evening journal prompt",
        replace_existing=True,
    )

    # Sunday 9am weekly report
    scheduler.add_job(
        _weekly_job,
        CronTrigger(day_of_week="sun", hour=9, minute=0, timezone=tz),
        args=[slack_client],
        id="weekly_report",
        name="Weekly health report",
        replace_existing=True,
    )

    return scheduler
