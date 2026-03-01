import logging
import os
from datetime import datetime, timedelta, timezone

from db.database import get_db
from db.models import OAuthToken

logger = logging.getLogger(__name__)
PROVIDER = "whoop"


def load_tokens_from_db() -> bool:
    """On startup: DB → os.environ. Returns False if no row (first-time setup)."""
    with get_db() as db:
        row = db.query(OAuthToken).filter_by(provider=PROVIDER).first()
        if row is None:
            logger.warning("No WHOOP tokens in DB — run: python -m whoop.auth")
            return False
        os.environ["WHOOP_ACCESS_TOKEN"] = row.access_token
        os.environ["WHOOP_REFRESH_TOKEN"] = row.refresh_token
        logger.info("WHOOP tokens loaded from DB")
        return True


def save_tokens_to_db(tokens: dict) -> None:
    """Upsert tokens into DB + os.environ. Called after every exchange or refresh."""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    with get_db() as db:
        row = db.query(OAuthToken).filter_by(provider=PROVIDER).first()
        if row is None:
            row = OAuthToken(provider=PROVIDER)
            db.add(row)
        row.access_token = tokens["access_token"]
        row.refresh_token = tokens["refresh_token"]
        row.expires_at = expires_at
        row.scope = tokens.get("scope", "")
        row.token_type = tokens.get("token_type", "Bearer")
        row.updated_at = datetime.now(timezone.utc)
    os.environ["WHOOP_ACCESS_TOKEN"] = tokens["access_token"]
    os.environ["WHOOP_REFRESH_TOKEN"] = tokens["refresh_token"]
    logger.info("WHOOP tokens saved to DB + os.environ")


def days_since_last_refresh() -> int | None:
    """Return how many days since tokens were last refreshed, or None if no record."""
    with get_db() as db:
        row = db.query(OAuthToken).filter_by(provider=PROVIDER).first()
        if row is None or row.updated_at is None:
            return None
        updated_at = row.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - updated_at
        return delta.days
