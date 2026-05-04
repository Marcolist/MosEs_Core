"""Layout API: read and write the dashboard grid."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/layout", tags=["layout"])

GRID_COLUMNS = 12


class LayoutEntry(BaseModel):
    plugin_id: str
    x: int
    y: int
    w: int
    h: int


class LayoutPayload(BaseModel):
    entries: list[LayoutEntry]


def _state(req: Request) -> dict[str, Any]:
    return req.app.state.moses


@router.get("")
async def get_layout(req: Request) -> dict[str, Any]:
    state = _state(req)
    db = state["db"]
    registry = state["registry"]
    stored = {e["plugin_id"]: e for e in db.layout_get()}
    entries = []
    for plugin in registry.active():
        manifest = plugin.manifest
        if manifest.id in stored:
            e = stored[manifest.id]
            entries.append({"plugin_id": manifest.id, "x": e["x"], "y": e["y"], "w": e["w"], "h": e["h"]})
        else:
            entries.append(
                {
                    "plugin_id": manifest.id,
                    "x": 0,
                    "y": 0,
                    "w": manifest.widget.default_width,
                    "h": manifest.widget.default_height,
                }
            )
    return {"columns": GRID_COLUMNS, "entries": entries}


@router.put("")
async def set_layout(payload: LayoutPayload, req: Request) -> dict[str, Any]:
    db = _state(req)["db"]
    db.layout_set([e.dict() for e in payload.entries])
    return {"ok": True}


@router.post("/reset")
async def reset_layout(req: Request) -> dict[str, Any]:
    state = _state(req)
    db = state["db"]
    registry = state["registry"]
    entries = []
    x = 0
    y = 0
    row_h = 0
    for plugin in registry.active():
        w = plugin.manifest.widget.default_width
        h = plugin.manifest.widget.default_height
        if x + w > GRID_COLUMNS:
            y += row_h
            x = 0
            row_h = 0
        entries.append({"plugin_id": plugin.manifest.id, "x": x, "y": y, "w": w, "h": h})
        x += w
        row_h = max(row_h, h)
    db.layout_set(entries)
    return {"ok": True, "entries": entries}
