"""System information and update endpoints."""

from __future__ import annotations

import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/system", tags=["system"])


def _state(req: Request) -> dict[str, Any]:
    return req.app.state.moses


@router.get("/info")
async def info(req: Request) -> dict[str, Any]:
    state = _state(req)
    updater = state["updater"]
    return {
        "version": updater.current_version(),
        "channel": updater.channel,
        "now": datetime.now(timezone.utc).isoformat(),
        "platform": sys.platform,
        "python": sys.version,
    }


@router.get("/update/check")
async def check_update(req: Request) -> dict[str, Any]:
    updater = _state(req)["updater"]
    release = updater.latest_release()
    return {
        "current": updater.current_version(),
        "latest": release.tag if release else None,
        "name": release.name if release else None,
        "changelog": release.body if release else None,
        "available": bool(release and release.tag and release.tag.lstrip("v") != updater.current_version()),
    }


@router.post("/update/install")
async def install_update(req: Request) -> dict[str, Any]:
    updater = _state(req)["updater"]
    return updater.update_core()


class DisplaySchedule(BaseModel):
    enabled: bool
    on_time: str  # HH:MM
    off_time: str  # HH:MM


@router.get("/display-schedule")
async def get_schedule(req: Request) -> dict[str, Any]:
    db = _state(req)["db"]
    return db.system_get(
        "display_schedule",
        {"enabled": False, "on_time": "06:00", "off_time": "23:00"},
    )


@router.put("/display-schedule")
async def set_schedule(payload: DisplaySchedule, req: Request) -> dict[str, Any]:
    db = _state(req)["db"]
    db.system_set("display_schedule", payload.dict())
    return {"ok": True}


@router.post("/restart")
async def restart_service() -> dict[str, Any]:
    """Self-terminate; systemd will restart us."""
    os.kill(os.getpid(), signal.SIGTERM)
    return {"ok": True}
