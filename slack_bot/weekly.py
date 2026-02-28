"""Builds and posts the Sunday weekly report to Slack."""

import logging

from ai.analyzer import generate_weekly_report
from config.settings import SLACK_USER_ID

logger = logging.getLogger(__name__)
DASHBOARD_URL = "http://localhost:8501"


def build_weekly_message() -> str:
    report = generate_weekly_report()
    lines = [
        "*📊 Weekly Health Report*",
        "",
        report,
        "",
        f"<{DASHBOARD_URL}|View Full Dashboard →>",
    ]
    return "\n".join(lines)


async def post_weekly_report(client):
    text = build_weekly_message()
    try:
        await client.chat_postMessage(channel=SLACK_USER_ID, text=text)
        logger.info("Weekly report posted to Slack")
    except Exception as e:
        logger.error(f"Failed to post weekly report: {e}")
