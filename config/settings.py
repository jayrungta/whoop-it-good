import os
from dotenv import load_dotenv

load_dotenv()

# Whoop OAuth
WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID", "")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET", "")
WHOOP_REDIRECT_URI = os.getenv("WHOOP_REDIRECT_URI", "http://localhost:8000/callback")
WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_API_BASE = "https://api.prod.whoop.com/developer/v1"
WHOOP_SCOPES = "offline read:recovery read:sleep read:workout read:cycles read:body_measurement"

# Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
SLACK_USER_ID = os.getenv("SLACK_USER_ID", "")

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/whoop_ai")

# Scheduler
MORNING_HOUR = int(os.getenv("MORNING_HOUR", "8"))
EVENING_JOURNAL_HOUR = int(os.getenv("EVENING_JOURNAL_HOUR", "21"))
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

# Gemini models
GEMINI_ANALYSIS_MODEL = "gemini-2.0-flash"    # Q&A + weekly reports
GEMINI_SUMMARY_MODEL = "gemini-2.0-flash"     # morning summaries + flag alerts

# Flag thresholds
HRV_DROP_THRESHOLD_PCT = 0.15
HRV_DROP_CONSECUTIVE_DAYS = 3
LOW_RECOVERY_THRESHOLD = 33
LOW_RECOVERY_CONSECUTIVE_DAYS = 3
SLEEP_DEBT_THRESHOLD_HOURS = 2.0
SLEEP_DEBT_WINDOW_DAYS = 5
SKIN_TEMP_SPIKE_C = 0.5
STRAIN_OVERLOAD_DAYS = 5


def require(key: str) -> str:
    """Get a required env var — raise at call time, not import time."""
    val = os.getenv(key, "")
    if not val:
        raise RuntimeError(f"Required environment variable not set: {key}")
    return val
