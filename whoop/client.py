"""
Async Whoop API client with automatic token refresh.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

from config.settings import WHOOP_API_BASE
from whoop.auth import refresh_tokens, save_tokens

load_dotenv()


class WhoopClient:
    def __init__(self):
        self._access_token: str | None = os.getenv("WHOOP_ACCESS_TOKEN")
        self._refresh_token: str | None = os.getenv("WHOOP_REFRESH_TOKEN")
        self._client: httpx.AsyncClient | None = None
        self._refresh_lock = asyncio.Lock()
        self._refreshed = False  # ensures only one refresh per client lifetime

    async def __aenter__(self):
        self._client = httpx.AsyncClient(base_url=WHOOP_API_BASE, timeout=30)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def _refresh_if_needed(self, response: httpx.Response) -> bool:
        if response.status_code != 401 or not self._refresh_token:
            return False
        async with self._refresh_lock:
            if self._refreshed:
                # Another parallel request already refreshed — just retry with new token
                return True
            try:
                tokens = await refresh_tokens(self._refresh_token)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    await self._notify_reauth_required()
                    raise RuntimeError("WHOOP refresh token expired — re-auth required") from e
                raise
            self._access_token = tokens["access_token"]
            self._refresh_token = tokens["refresh_token"]
            save_tokens(tokens)
            self._refreshed = True
            return True

    async def _notify_reauth_required(self):
        try:
            from slack_bot.alerts import _slack_client
            from config.settings import SLACK_USER_ID
            if _slack_client:
                await _slack_client.chat_postMessage(
                    channel=SLACK_USER_ID,
                    text=(
                        "🔑 *WHOOP refresh token expired.* All jobs are paused.\n\n"
                        "To fix:\n"
                        "1. Run locally: `python -m whoop.auth`\n"
                        "2. Then: `fly secrets set WHOOP_ACCESS_TOKEN=... WHOOP_REFRESH_TOKEN=...`"
                    )
                )
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to send re-auth DM: {e}")

    async def _get(self, path: str, params: dict | None = None) -> dict:
        resp = await self._client.get(path, headers=self._auth_headers(), params=params)
        if await self._refresh_if_needed(resp):
            resp = await self._client.get(path, headers=self._auth_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    async def _get_paginated(self, path: str, params: dict | None = None) -> list[dict]:
        """Fetch all pages of a paginated endpoint."""
        params = params or {}
        results = []
        next_token = None

        while True:
            if next_token:
                params["nextToken"] = next_token
            data = await self._get(path, params)
            records = data.get("records", [])
            results.extend(records)
            next_token = data.get("next_token")
            if not next_token:
                break

        return results

    # ---- Public API methods ----

    async def get_profile(self) -> dict:
        return await self._get("/user/profile/basic")

    async def get_cycles(self, start: datetime | None = None, end: datetime | None = None) -> list[dict]:
        params: dict[str, Any] = {"limit": 25}
        if start:
            params["start"] = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if end:
            params["end"] = end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return await self._get_paginated("/cycle", params)

    async def get_recovery(self, start: datetime | None = None, end: datetime | None = None) -> list[dict]:
        params: dict[str, Any] = {"limit": 25}
        if start:
            params["start"] = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if end:
            params["end"] = end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return await self._get_paginated("/recovery", params)

    async def get_sleep(self, start: datetime | None = None, end: datetime | None = None) -> list[dict]:
        params: dict[str, Any] = {"limit": 25}
        if start:
            params["start"] = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if end:
            params["end"] = end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return await self._get_paginated("/activity/sleep", params)

    async def get_workouts(self, start: datetime | None = None, end: datetime | None = None) -> list[dict]:
        params: dict[str, Any] = {"limit": 25}
        if start:
            params["start"] = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        if end:
            params["end"] = end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return await self._get_paginated("/activity/workout", params)

    async def get_body_measurement(self) -> dict:
        return await self._get("/user/measurement/body")
