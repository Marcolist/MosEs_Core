"""OAuth provider connection endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from ..services import OAuthService

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

GOOGLE_DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "openid",
    "email",
]


def _state(req: Request) -> dict[str, Any]:
    return req.app.state.moses


@router.get("/providers")
async def list_providers(req: Request) -> dict[str, Any]:
    db = _state(req)["db"]
    return {"providers": OAuthService(db).list_providers()}


class GoogleCreds(BaseModel):
    client_id: str
    client_secret: str


@router.put("/google/credentials")
async def set_google_creds(payload: GoogleCreds, req: Request) -> dict[str, Any]:
    db = _state(req)["db"]
    OAuthService(db).set_google_credentials(payload.client_id, payload.client_secret)
    return {"ok": True}


@router.get("/google/credentials")
async def get_google_creds(req: Request) -> dict[str, Any]:
    db = _state(req)["db"]
    cid, secret = OAuthService(db).google_credentials()
    return {"client_id": cid, "client_secret_set": bool(secret)}


@router.get("/google/start")
async def google_start(req: Request, scopes: str | None = None) -> RedirectResponse:
    db = _state(req)["db"]
    redirect_uri = str(req.url_for("google_callback"))
    scope_list = scopes.split() if scopes else GOOGLE_DEFAULT_SCOPES
    try:
        url = OAuthService(db).google_authorize_url(redirect_uri, scope_list)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url)


@router.get("/google/callback", name="google_callback")
async def google_callback(req: Request, code: str | None = None, state: str | None = None) -> HTMLResponse:
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code or state")
    db = _state(req)["db"]
    try:
        OAuthService(db).google_exchange_code(code, state)
    except Exception as exc:  # noqa: BLE001
        return HTMLResponse(f"<h1>OAuth failed</h1><pre>{exc}</pre>", status_code=500)
    return HTMLResponse(
        "<html><body><h1>Connected</h1>"
        "<p>You can close this window.</p>"
        "<script>window.close();</script></body></html>"
    )


@router.delete("/{provider}")
async def disconnect_provider(provider: str, req: Request) -> dict[str, Any]:
    db = _state(req)["db"]
    OAuthService(db).disconnect(provider)
    return {"ok": True}
