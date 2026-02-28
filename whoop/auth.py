"""
Whoop OAuth2 flow + token refresh.

First-time setup:
    python3 -m whoop.auth

Prints the auth URL, you approve in browser, paste the redirect URL back.
No local server required.
"""

import asyncio
import os
import urllib.parse
from pathlib import Path

import httpx
from dotenv import load_dotenv, set_key

from config.settings import (
    WHOOP_AUTH_URL,
    WHOOP_CLIENT_ID,
    WHOOP_CLIENT_SECRET,
    WHOOP_REDIRECT_URI,
    WHOOP_SCOPES,
    WHOOP_TOKEN_URL,
)

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _build_auth_url() -> str:
    params = {
        "client_id": WHOOP_CLIENT_ID,
        "redirect_uri": WHOOP_REDIRECT_URI,
        "response_type": "code",
        "scope": WHOOP_SCOPES,
    }
    return f"{WHOOP_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            WHOOP_TOKEN_URL,
            data={
                "client_id": WHOOP_CLIENT_ID,
                "client_secret": WHOOP_CLIENT_SECRET,
                "code": code,
                "redirect_uri": WHOOP_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_tokens(refresh_token: str) -> dict:
    """Exchange a refresh token for new access + refresh tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            WHOOP_TOKEN_URL,
            data={
                "client_id": WHOOP_CLIENT_ID,
                "client_secret": WHOOP_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


def save_tokens(tokens: dict):
    """Persist tokens to .env file."""
    set_key(str(ENV_PATH), "WHOOP_ACCESS_TOKEN", tokens["access_token"])
    set_key(str(ENV_PATH), "WHOOP_REFRESH_TOKEN", tokens["refresh_token"])
    print("Tokens saved to .env")


def run_oauth_flow():
    """
    Manual OAuth2 flow — no local server needed.

    1. Opens the Whoop auth URL in your browser
    2. You approve access
    3. Browser redirects to localhost:8000/callback?code=... (will show connection error — that's fine)
    4. Copy the full URL from the browser address bar and paste it here
    """
    auth_url = _build_auth_url()
    print("\n" + "="*60)
    print("Open this URL in your browser:")
    print(f"\n{auth_url}\n")
    print("="*60)
    print("\nAfter approving, the browser will redirect to localhost.")
    print("It will show a connection error — that's expected.")
    print("Copy the full URL from the address bar and paste it below.\n")

    redirect_url = input("Paste redirect URL here: ").strip()

    parsed = urllib.parse.urlparse(redirect_url)
    params = urllib.parse.parse_qs(parsed.query)

    if "code" not in params:
        print(f"\nNo 'code' found in URL. Got params: {list(params.keys())}")
        print("Make sure you copied the full URL from the address bar.")
        return

    code = params["code"][0]
    print(f"\nGot auth code. Exchanging for tokens...")

    tokens = asyncio.run(exchange_code(code))
    save_tokens(tokens)
    print("Done! You can now run: python3 -m whoop.sync")


if __name__ == "__main__":
    load_dotenv()
    run_oauth_flow()
