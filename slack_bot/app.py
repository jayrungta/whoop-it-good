"""
Slack Bolt app — Socket Mode.
Initializes the app and exports the handler for use in main.py.
"""

import logging

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from config.settings import SLACK_APP_TOKEN, SLACK_BOT_TOKEN
from slack_bot.handlers import register_handlers

logger = logging.getLogger(__name__)

app = AsyncApp(token=SLACK_BOT_TOKEN)
register_handlers(app)


async def start_socket_mode():
    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    logger.info("Starting Slack Socket Mode...")
    await handler.start_async()
