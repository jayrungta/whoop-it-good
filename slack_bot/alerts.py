"""
Central alerting module.

Call init_alerts(client) once at startup.
Then use notify_sync_success / notify_error anywhere (async),
or schedule_alert() from synchronous code when a loop is running.
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_slack_client = None


def init_alerts(client):
    """Store the Slack async web client for use by all alert functions."""
    global _slack_client
    _slack_client = client


async def notify_sync_success(job_name: str, counts: dict, days: int):
    """Post a brief sync-success ping after a scheduled Whoop sync."""
    if _slack_client is None:
        return
    from config.settings import SLACK_USER_ID

    parts = [f"{k}: +{v}" for k, v in counts.items() if v > 0]
    detail = ", ".join(parts) if parts else "no new records"
    text = f"✅ *{job_name}* sync done — {detail} (last {days}d)"
    try:
        await _slack_client.chat_postMessage(channel=SLACK_USER_ID, text=text)
    except Exception as e:
        logger.error(f"Failed to post sync-success alert: {e}")


async def notify_error(source: str, error: Exception, context: str = ""):
    """Post a 🚨 error alert to Slack."""
    if _slack_client is None:
        logger.error(f"[{source}] {error} — no Slack client configured for alerts")
        return
    from config.settings import SLACK_USER_ID

    ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
    ctx_line = f"\n_{context}_" if context else ""
    text = f"🚨 *{source} error* ({ts})\n```{error}```{ctx_line}"
    try:
        await _slack_client.chat_postMessage(channel=SLACK_USER_ID, text=text)
    except Exception as e:
        logger.error(f"Failed to post error alert: {e}")


def schedule_alert(source: str, error: Exception, context: str = ""):
    """
    Fire-and-forget error alert from synchronous code.
    Requires a running asyncio event loop (always true inside APScheduler jobs).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(notify_error(source, error, context))
        else:
            logger.error(f"[{source}] {error} (no running loop to send alert)")
    except Exception as inner:
        logger.error(f"[{source}] {error} — schedule_alert itself failed: {inner}")
