"""Builds and posts the morning health summary to Slack."""

import logging
from datetime import date

from ai.analyzer import generate_morning_summary
from ai.flags import Flag
from config.settings import SLACK_USER_ID

logger = logging.getLogger(__name__)

DASHBOARD_URL = "http://localhost:8501"  # Streamlit local URL


def _recovery_emoji(score: int | None) -> str:
    if score is None:
        return "⚪"
    if score >= 67:
        return "🟢"
    if score >= 34:
        return "🟡"
    return "🔴"


def build_morning_message(target_date: date | None = None) -> str:
    summary, flags = generate_morning_summary(target_date)

    lines = [f"*Morning Health Summary — {target_date or date.today()}*", ""]
    lines.append(summary)

    if flags:
        lines.append("")
        lines.append("⚠️ *Active Flags*")
        for flag in flags:
            severity_icon = "🚨" if flag.severity == "alert" else "⚠️"
            lines.append(f"{severity_icon} {flag.message}")

    lines.append("")
    lines.append(f"<{DASHBOARD_URL}|View Dashboard →>")

    return "\n".join(lines)


async def post_morning_message(client, target_date: date | None = None):
    """Post morning summary as a DM to Jay."""
    text = build_morning_message(target_date)
    try:
        await client.chat_postMessage(channel=SLACK_USER_ID, text=text)
        logger.info("Morning message posted to Slack")
    except Exception as e:
        logger.error(f"Failed to post morning message: {e}")
