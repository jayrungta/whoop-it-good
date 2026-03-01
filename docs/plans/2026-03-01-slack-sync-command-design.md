# Design: On-Demand WHOOP Sync via `/sync` Slack Slash Command

**Date:** 2026-03-01
**Status:** Implemented

---

## Problem

All WHOOP database syncs ran on a fixed schedule (8am, 1pm, Sunday weekly). Between runs — after a workout, after travelling across midnight, or when troubleshooting — there was no way to force a refresh without SSH/CLI access to the server.

---

## Solution

Add a `/sync [days]` Slack slash command that triggers `sync_all` on demand, with the same token-freshness guard used by scheduled jobs.

---

## Design Decisions

### Single file change

Only `slack_bot/handlers.py` needed modification. All dependencies (`sync_all`, `_ensure_token_fresh`) already existed. No new modules, no new dependencies, no config changes.

### Immediate ack, then async work

Slack requires a response within 3 seconds or it marks the command as failed. The handler calls `await ack(...)` first with a visible loading message, then performs the (potentially slow) sync work asynchronously before posting the result.

### Visible channel message, not ephemeral

The result is posted via `client.chat_postMessage` rather than `respond(...)`. This makes the sync auditable — anyone in the channel can see that a manual refresh happened and what it found. Ephemeral messages vanish and leave no record.

### Lazy imports to avoid circular imports

`_ensure_token_fresh` and `sync_all` are imported inside the handler function body, not at module load time. `handlers.py` is loaded early in the app startup sequence; top-level imports of `scheduler.jobs` or `whoop.sync` would create circular import chains.

### Argument parsing: graceful fallback

- No argument → defaults to 3 days (common case: "what did I miss today?")
- Non-integer argument → silently falls back to 3 days (no error message for typos)
- Valid integer → clamped to [1, 365] to prevent absurdly large queries

### Token refresh reuse

`_ensure_token_fresh(client)` is the same guard used by the scheduled jobs. It checks whether the stored OAuth token is >20 days old and proactively refreshes it if so. Reusing this avoids duplicating refresh logic and ensures consistent behaviour across scheduled and manual syncs.

### Error surfacing

If `sync_all` throws, the exception message is posted visibly to the channel (prefixed with ❌). This is intentional — a silent failure would leave the user unsure whether the sync ran. The full traceback is also logged at ERROR level for server-side debugging.

---

## Verification Steps

1. `/sync` — should ack with "⏳ Syncing last 3 days..." then post ✅ counts
2. `/sync 7` — should sync 7 days
3. `/sync abc` — invalid arg, falls back to 3 days gracefully
4. DB check: `SELECT synced_at FROM whoop_cycles ORDER BY synced_at DESC LIMIT 3;`
5. Error path: break `WHOOP_ACCESS_TOKEN`, run `/sync`, confirm ❌ message appears visibly

---

## Manual Setup Required (One-Time)

Register the slash command in the Slack App Dashboard:

1. https://api.slack.com/apps → WhoopBot → **Slash Commands** → **Create New Command**
2. Command: `/sync`
3. Short description: `Sync WHOOP data on demand`
4. Usage hint: `[days]`
5. Request URL: leave blank (Socket Mode)
6. Save → reinstall app if prompted
