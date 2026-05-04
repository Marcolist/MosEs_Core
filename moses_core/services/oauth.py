"""OAuth2 service. Currently supports Google."""

from __future__ import annotations

import json
import logging
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.request import Request, urlopen

from ..db import Database

logger = logging.getLogger(__name__)


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class OAuthService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._states: dict[str, dict[str, Any]] = {}

    # ---------------- credentials ----------------
    def set_google_credentials(self, client_id: str, client_secret: str) -> None:
        self.db.system_set("oauth.google.client_id", client_id)
        self.db.system_set("oauth.google.client_secret", client_secret)

    def google_credentials(self) -> tuple[str | None, str | None]:
        return (
            self.db.system_get("oauth.google.client_id"),
            self.db.system_get("oauth.google.client_secret"),
        )

    # ---------------- google flow ----------------
    def google_authorize_url(self, redirect_uri: str, scopes: list[str]) -> str:
        client_id, _ = self.google_credentials()
        if not client_id:
            raise RuntimeError("Google client_id not configured")
        state = secrets.token_urlsafe(24)
        self._states[state] = {"redirect_uri": redirect_uri, "scopes": scopes}
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def google_exchange_code(self, code: str, state: str) -> dict[str, Any]:
        info = self._states.pop(state, None)
        if info is None:
            raise ValueError("Unknown OAuth state")
        client_id, client_secret = self.google_credentials()
        if not (client_id and client_secret):
            raise RuntimeError("Google credentials missing")
        body = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": info["redirect_uri"],
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")
        req = Request(
            GOOGLE_TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        self._save("google", payload, info["scopes"])
        return payload

    def _save(self, provider: str, payload: dict[str, Any], scopes: list[str]) -> None:
        expires_at = None
        if "expires_in" in payload:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=int(payload["expires_in"]))
            ).isoformat()
        self.db.oauth_set(
            provider=provider,
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            scope=" ".join(scopes),
            extra=payload,
        )

    def get_valid_token(self, provider: str) -> dict[str, Any] | None:
        token = self.db.oauth_get(provider)
        if not token:
            return None
        if not token.get("expires_at"):
            return token
        expires_at = datetime.fromisoformat(token["expires_at"])
        if expires_at - timedelta(seconds=60) > datetime.now(timezone.utc):
            return token
        if provider == "google" and token.get("refresh_token"):
            return self._refresh_google(token)
        return token

    def _refresh_google(self, token: dict[str, Any]) -> dict[str, Any] | None:
        client_id, client_secret = self.google_credentials()
        if not (client_id and client_secret):
            return None
        body = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": token["refresh_token"],
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        req = Request(
            GOOGLE_TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.error("Google token refresh failed: %s", exc)
            return None
        # Refresh response usually omits refresh_token; preserve existing one.
        payload.setdefault("refresh_token", token["refresh_token"])
        self._save("google", payload, (token.get("scope") or "").split())
        return self.db.oauth_get("google")

    # ---------------- listing / deletion ----------------
    def list_providers(self) -> list[dict[str, Any]]:
        return self.db.oauth_list()

    def disconnect(self, provider: str) -> None:
        self.db.oauth_delete(provider)
