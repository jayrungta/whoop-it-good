"""
Whoop OAuth2 flow + token refresh.

First-time setup:
    python -m whoop.auth

This launches a local server on port 8000, prints the auth URL,
waits for the redirect, exchanges the code for tokens, and saves
them to .env.
"""

import asyncio
import os
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

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

_auth_code: str | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Auth complete! You can close this tab.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code parameter.")

    def log_message(self, *args):
        pass  # suppress server logs


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
    """Interactive OAuth2 flow. Opens browser, captures redirect, saves tokens."""
    global _auth_code

    auth_url = _build_auth_url()
    print(f"\nOpening browser for Whoop auth...\nIf it doesn't open: {auth_url}\n")
    webbrowser.open(auth_url)

    # Keep handling requests until we get the code (browser may send favicon etc. first)
    server = HTTPServer(("localhost", 8000), _CallbackHandler)
    server.timeout = 120
    print("Waiting for OAuth callback on http://localhost:8000/callback ...")
    while not _auth_code:
        server.handle_request()
        if server.timeout and not _auth_code:
            break
    server.server_close()

    if not _auth_code:
        print("No auth code received. Timed out.")
        sys.exit(1)

    tokens = asyncio.run(exchange_code(_auth_code))
    save_tokens(tokens)
    print("OAuth complete. Access token and refresh token saved.")


if __name__ == "__main__":
    load_dotenv()
    run_oauth_flow()
