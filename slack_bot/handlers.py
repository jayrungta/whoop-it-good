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

        # Only respond to messages from Jay
        if user != SLACK_USER_ID:
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


def register_journal_thread(thread_ts: str, metadata: dict):
    """Called by journal flow to register a pending thread."""
    _pending_journal_threads[thread_ts] = metadata


def unregister_journal_thread(thread_ts: str):
    _pending_journal_threads.pop(thread_ts, None)
