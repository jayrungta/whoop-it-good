"""
Slack message event handlers.
Handles conversational Q&A when user DMs or @mentions the bot.
"""

import logging
import re

from ai.analyzer import answer_question
from config.settings import SLACK_USER_ID

logger = logging.getLogger(__name__)

# Journal reply parsing state — keyed by thread_ts
_pending_journal_threads: dict[str, dict] = {}


def register_handlers(app):
    """Register all event handlers on the Bolt app."""

    @app.event("message")
    async def handle_dm(event, client, say):
        """Handle direct messages — route to Q&A or journal parser."""
        channel_type = event.get("channel_type")
        user = event.get("user")
        text = event.get("text", "").strip()
        thread_ts = event.get("thread_ts")
        ts = event.get("ts")

        # Ignore bot messages
        if event.get("bot_id"):
            return

        logger.info(f"Message event — user: {user}, channel_type: {channel_type}, expected_user: {SLACK_USER_ID}")

        # Only respond to messages from Jay
        if user != SLACK_USER_ID:
            logger.warning(f"Ignoring message from unexpected user: {user}")
            return

        # If this is a thread reply to a pending journal prompt, handle it
        if thread_ts and thread_ts in _pending_journal_threads:
            from journal.flow import parse_journal_reply
            await parse_journal_reply(thread_ts, text, ts, client)
            return

        # Direct message Q&A
        if channel_type == "im" and text:
            logger.info(f"Q&A question received: {text[:80]}")
            try:
                await client.reactions_add(channel=event["channel"], timestamp=ts, name="thinking_face")
            except Exception:
                pass

            answer = answer_question(text)

            await say(text=answer, thread_ts=ts)
            try:
                await client.reactions_remove(channel=event["channel"], timestamp=ts, name="thinking_face")
            except Exception:
                pass

    @app.event("app_mention")
    async def handle_mention(event, say):
        """Handle @mentions in any channel."""
        text = re.sub(r"<@[^>]+>", "", event.get("text", "")).strip()
        if not text:
            await say("Hey! Ask me anything about your health data.")
            return

        logger.info(f"Mention Q&A: {text[:80]}")
        answer = answer_question(text)
        await say(text=answer, thread_ts=event.get("ts"))


    @app.command("/sync")
    async def handle_sync_command(ack, respond, command, client):
        """Handle /sync [days] — on-demand WHOOP data refresh."""
        text = command.get("text", "").strip()
        try:
            days = int(text) if text else 3
        except ValueError:
            days = 3
        days = max(1, min(days, 365))

        await ack(text=f"⏳ Syncing last {days} day{'s' if days != 1 else ''}...")

        from scheduler.jobs import _ensure_token_fresh
        from whoop.sync import sync_all

        await _ensure_token_fresh(client)

        channel = command["channel_id"]
        try:
            counts = await sync_all(days=days)
            msg = (
                f"✅ *Manual sync done* — "
                f"cycles: +{counts['cycles']}, recovery: +{counts['recovery']}, "
                f"sleep: +{counts['sleep']}, workouts: +{counts['workouts']} "
                f"(last {days}d)"
            )
        except Exception as e:
            logger.error(f"Manual /sync failed: {e}")
            msg = f"❌ Sync failed: {e}"

        await client.chat_postMessage(channel=channel, text=msg)


def register_journal_thread(thread_ts: str, metadata: dict):
    """Called by journal flow to register a pending thread."""
    _pending_journal_threads[thread_ts] = metadata


def unregister_journal_thread(thread_ts: str):
    _pending_journal_threads.pop(thread_ts, None)
