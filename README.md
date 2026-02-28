<p align="center">
  <img src="assets/banner.png" alt="WHOOP it good!" width="480">
</p>

# WHOOP it good!

A personal AI health companion that turns raw Whoop biometric data into actionable insights delivered via Slack.

Whoop's app surfaces recovery and sleep scores but buries the patterns that actually matter. This pulls your data into a Postgres database, runs AI analysis against your personal baselines, and delivers concise daily summaries, proactive health alerts, and conversational Q&A — all in Slack.

---

## What it does

**Morning summary (8am daily)**
- Recovery score, HRV vs your 30-day baseline, sleep breakdown
- 1–2 sentence AI insight based on your actual numbers
- Active health flags if anything needs attention
- Link to the dashboard

**Evening journal (9pm daily)**
- Slack bot prompts for alcohol, stress, late caffeine, notes
- Replies are parsed and stored for correlation analysis

**Proactive flags**
- HRV dropping >15% below baseline for 3+ consecutive days
- Recovery in the red zone for 3+ days in a row
- Sleep debt exceeding 2 hours
- Skin temp spike (possible illness signal)
- High strain consistently outpacing recovery

**Conversational Q&A**
- DM or @mention the bot with any health question
- Answers are grounded in your actual data, not generic advice
- Example: *"why has my sleep been shit this week?"*, *"am I overtraining?"*

**Weekly report (Sunday 9am)**
- Recovery, HRV trend, sleep debt, lifestyle correlations, training load
- Actionable bullet points for the week ahead

**Streamlit dashboard**
- HRV, recovery, and sleep trend charts
- Journal correlation plots (alcohol → HRV, stress → recovery)

---

## Architecture

```
Whoop API (OAuth2)
      ↓
  PostgreSQL (Supabase)
      ↓
AI Analysis (Gemini)
      ↓
Slack Bot ←→ You
      ↓
Streamlit Dashboard
```

- **Bot**: Slack Bolt, Socket Mode (no public URL needed)
- **Scheduler**: APScheduler — morning sync, midday sync, evening journal, weekly report
- **AI**: Google Gemini — analysis model for Q&A/weekly, summary model for daily insights
- **Database**: SQLAlchemy + Alembic migrations

---

## Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12 |
| Database | PostgreSQL (Supabase) |
| ORM | SQLAlchemy + Alembic |
| Whoop client | httpx (async) + OAuth2 |
| Slack bot | Slack Bolt — Socket Mode |
| AI | Google Gemini API |
| Scheduler | APScheduler |
| Dashboard | Streamlit + Plotly |

---

## Local setup

### 1. Clone and install
```bash
git clone https://github.com/jayrungta/whoop-it-good.git
cd whoop-it-good
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in all values — see .env.example for descriptions
```

### 3. Whoop OAuth (one-time)
```bash
python3 -m whoop.auth
# Opens browser → approve → paste redirect URL back
# Tokens saved to .env automatically
```

### 4. Database setup
```bash
alembic upgrade head
```

### 5. Backfill historical data
```bash
python3 -m whoop.sync --days 90
```

### 6. Start the bot
```bash
python main.py
```

### 7. Dashboard (optional, separate terminal)
```bash
streamlit run dashboard/app.py
```

---

## Deployment

### Database — Supabase
1. Create a project at [supabase.com](https://supabase.com)
2. Grab the **Session Pooler** connection string from Settings → Database (use the pooler URL, not the direct connection — direct uses IPv6 which some hosts can't reach)
3. Run migrations locally against Supabase: `DATABASE_URL="..." alembic upgrade head`
4. Backfill: `DATABASE_URL="..." python3 -m whoop.sync --days 90`

### Bot — Fly.io
```bash
fly auth login
fly launch --no-deploy   # imports fly.toml
fly secrets set \
  DATABASE_URL="..." \
  SLACK_BOT_TOKEN="xoxb-..." \
  SLACK_APP_TOKEN="xapp-..." \
  SLACK_USER_ID="U..." \
  GEMINI_API_KEY="..." \
  WHOOP_CLIENT_ID="..." \
  WHOOP_CLIENT_SECRET="..." \
  WHOOP_ACCESS_TOKEN="..." \
  WHOOP_REFRESH_TOKEN="..." \
  DASHBOARD_URL="https://your-app.streamlit.app"
fly deploy
```

### Dashboard — Streamlit Community Cloud
1. Connect repo at [share.streamlit.io](https://share.streamlit.io)
2. Main file: `dashboard/app.py`
3. Add secret: `DATABASE_URL = "postgresql://...pooler.supabase.com/postgres"`
4. Deploy — grab the URL and set it as `DASHBOARD_URL` in Fly secrets

---

## Environment variables

| Variable | Description |
|---|---|
| `WHOOP_CLIENT_ID` | Whoop app client ID |
| `WHOOP_CLIENT_SECRET` | Whoop app client secret |
| `WHOOP_REDIRECT_URI` | OAuth redirect (local only, `http://localhost:8000/callback`) |
| `WHOOP_ACCESS_TOKEN` | OAuth access token (from `python3 -m whoop.auth`) |
| `WHOOP_REFRESH_TOKEN` | OAuth refresh token |
| `SLACK_BOT_TOKEN` | Bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | Socket Mode token (`xapp-...`) |
| `SLACK_USER_ID` | Your Slack user ID for DMs |
| `GEMINI_API_KEY` | Google Gemini API key |
| `DATABASE_URL` | PostgreSQL connection string |
| `DASHBOARD_URL` | Streamlit dashboard URL |
| `MORNING_HOUR` | Morning summary hour (default: `8`) |
| `EVENING_JOURNAL_HOUR` | Journal prompt hour (default: `21`) |
| `TIMEZONE` | Scheduler timezone (default: `America/New_York`) |

---

## Slack app setup

Required bot scopes: `chat:write`, `im:history`, `app_mentions:read`

Required event subscriptions (Socket Mode): `message.im`, `app_mention`

---

## Personalisation

Edit `config/personal_context.py` to update your goals, known sensitivities, sleep targets, and schedule. This context is included in every Gemini prompt, so keeping it accurate improves the quality of all AI responses.
