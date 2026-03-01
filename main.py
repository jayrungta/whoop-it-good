"""
Entry point — starts the Slack bot and APScheduler.

Usage:
    python main.py

First-time setup:
    1. Copy .env.example → .env and fill in all values
    2. Run: python -m whoop.auth       (OAuth2 dance)
    3. Run: python -m whoop.sync       (backfill 90 days)
    4. Run: alembic upgrade head       (apply DB migrations)
    5. Run: python main.py             (start bot)
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main():
    from db.database import init_db
    from slack_bot.app import app, start_socket_mode
    from scheduler.jobs import create_scheduler

    # Ensure DB tables exist (idempotent)
    init_db()
    logger.info("Database ready")

    from whoop.token_store import load_tokens_from_db
    load_tokens_from_db()

    # Slack web client (async)
    slack_client = app.client

    # Wire alert module so any component can send Slack alerts
    from slack_bot.alerts import init_alerts
    init_alerts(slack_client)
    logger.info("Alert module initialized")

    # Scheduler
    scheduler = create_scheduler(slack_client)
    scheduler.start()
    logger.info(f"Scheduler started with {len(scheduler.get_jobs())} jobs")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} → next run: {job.next_run_time}")

    # Slack Socket Mode (blocks until stopped)
    await start_socket_mode()


if __name__ == "__main__":
    asyncio.run(main())
