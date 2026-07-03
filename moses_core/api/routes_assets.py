"""Serve plugin frontend/admin JS files from the plugins directory."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/plugins", tags=["plugin-assets"])

ALLOWED = {"frontend.js", "admin.js", "frontend.css", "admin.css", "icon.svg", "icon.png"}


@router.get("/{plugin_id}/asset/{filename}")
async def plugin_asset(plugin_id: str, filename: str, req: Request) -> FileResponse:
    if filename not in ALLOWED:
        raise HTTPException(status_code=404, detail="not found")
    state = req.app.state.moses
    plugins_dir = state["plugins_dir"]
    path = (plugins_dir / plugin_id / filename).resolve()
    if not str(path).startswith(str(plugins_dir.resolve())):
        raise HTTPException(status_code=400, detail="invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path)
