"""
Evening journal prompt flow.
Sends a threaded prompt to Slack, parses the reply, and saves to DB.
"""

import logging
import re
from datetime import date

from db.database import get_db
from db.models import JournalEntry
from config.settings import SLACK_USER_ID

logger = logging.getLogger(__name__)

JOURNAL_PROMPT = """\
*Evening check-in* (reply in this thread):

1. Alcohol? (none / 1-2 / 3+)
2. Stress today? (1-5)
3. Late caffeine after 2pm? (y/n)
4. Anything else? (optional)"""


async def send_journal_prompt(client) -> str | None:
    """Post the journal prompt and register the thread for parsing."""
    try:
        resp = await client.chat_postMessage(channel=SLACK_USER_ID, text=JOURNAL_PROMPT)
        thread_ts = resp["ts"]

        # Register thread so handler knows to route replies here
        from slack_bot.handlers import register_journal_thread
        register_journal_thread(thread_ts, {"date": str(date.today())})
        logger.info(f"Journal prompt sent (thread {thread_ts})")
        return thread_ts
    except Exception as e:
        logger.error(f"Failed to send journal prompt: {e}")
        return None


def _parse_alcohol(text: str) -> int | None:
    """Parse alcohol from reply text."""
    text_lower = text.lower()
    if re.search(r"\bnone\b|0\b|no\b", text_lower):
        return 0
    m = re.search(r"(\d+)", text_lower)
    if m:
        return int(m.group(1))
    if "1-2" in text_lower or "one" in text_lower or "two" in text_lower:
        return 1
    if "3+" in text_lower or "three" in text_lower or "few" in text_lower:
        return 3
    return None


def _parse_stress(text: str) -> int | None:
    m = re.search(r"\b([1-5])\b", text)
    return int(m.group(1)) if m else None


def _parse_bool(text: str) -> bool | None:
    text_lower = text.lower()
    if re.search(r"\by(es)?\b|yeah|yep|true", text_lower):
        return True
    if re.search(r"\bno?\b|nope|nah|false", text_lower):
        return False
    return None


def parse_journal_text(text: str) -> dict:
    """
    Parse a free-text journal reply.
    Supports line-by-line format matching the prompt structure.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    result: dict = {
        "alcohol_units": None,
        "stress_level": None,
        "caffeine": None,
        "late_caffeine": None,
        "notes": None,
    }

    notes_parts = []

    for i, line in enumerate(lines):
        # Remove leading number/dot (e.g. "1. " or "1) ")
        clean = re.sub(r"^\d+[\.\)]\s*", "", line)

        if i == 0 or "alcohol" in clean.lower():
            result["alcohol_units"] = _parse_alcohol(clean)
        elif i == 1 or "stress" in clean.lower():
            result["stress_level"] = _parse_stress(clean)
        elif i == 2 or "caffeine" in clean.lower():
            result["late_caffeine"] = _parse_bool(clean)
        elif i >= 3:
            notes_parts.append(clean)

    if notes_parts:
        result["notes"] = " ".join(notes_parts)

    # Fallback: scan whole text for anything we missed
    if result["alcohol_units"] is None:
        result["alcohol_units"] = _parse_alcohol(text)
    if result["stress_level"] is None:
        result["stress_level"] = _parse_stress(text)
    if result["late_caffeine"] is None:
        result["late_caffeine"] = _parse_bool(text)

    return result


async def parse_journal_reply(thread_ts: str, text: str, reply_ts: str, client):
    """Parse user's threaded reply and save to DB."""
    from slack_bot.handlers import unregister_journal_thread

    parsed = parse_journal_text(text)
    today = date.today()

    with get_db() as db:
        existing = db.query(JournalEntry).filter_by(date=today).first()
        if existing:
            # Update fields that were provided
            if parsed["alcohol_units"] is not None:
                existing.alcohol_units = parsed["alcohol_units"]
            if parsed["stress_level"] is not None:
                existing.stress_level = parsed["stress_level"]
            if parsed["late_caffeine"] is not None:
                existing.late_caffeine = parsed["late_caffeine"]
            if parsed["notes"]:
                existing.notes = parsed["notes"]
        else:
            db.add(JournalEntry(
                date=today,
                alcohol_units=parsed["alcohol_units"],
                stress_level=parsed["stress_level"],
                caffeine=None,
                late_caffeine=parsed["late_caffeine"],
                notes=parsed["notes"],
            ))

    unregister_journal_thread(thread_ts)

    # Confirm in thread
    summary_parts = []
    if parsed["alcohol_units"] is not None:
        summary_parts.append(f"🍷 {parsed['alcohol_units']} drink(s)")
    if parsed["stress_level"] is not None:
        summary_parts.append(f"😤 stress {parsed['stress_level']}/5")
    if parsed["late_caffeine"] is not None:
        summary_parts.append(f"☕ late caffeine: {'yes' if parsed['late_caffeine'] else 'no'}")

    confirm = "Logged: " + " | ".join(summary_parts) if summary_parts else "Entry saved."
    try:
        await client.chat_postMessage(
            channel=SLACK_USER_ID,
            thread_ts=thread_ts,
            text=f"✅ {confirm}",
        )
    except Exception as e:
        logger.warning(f"Could not confirm journal entry: {e}")

    logger.info(f"Journal entry saved for {today}: {parsed}")
