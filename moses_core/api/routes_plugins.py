"""HTTP API for plugin lifecycle: list, install, enable, configure."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


def _state(req: Request) -> dict[str, Any]:
    return req.app.state.moses


@router.get("")
async def list_plugins(req: Request) -> dict[str, Any]:
    state = _state(req)
    db = state["db"]
    registry = state["registry"]
    rows = {p["id"]: p for p in db.list_plugins()}
    out = []
    for manifest in registry.installed():
        meta = rows.get(manifest.id, {})
        out.append(
            {
                "manifest": manifest.to_dict(),
                "enabled": bool(meta.get("enabled", 0)),
                "active": registry.is_active(manifest.id),
                "last_run_at": meta.get("last_run_at"),
                "last_status": meta.get("last_status"),
                "last_error": meta.get("last_error"),
            }
        )
    return {"plugins": out}


@router.get("/active")
async def active_plugins(req: Request) -> dict[str, Any]:
    state = _state(req)
    registry = state["registry"]
    return {
        "plugins": [
            {"id": p.manifest.id, "manifest": p.manifest.to_dict()} for p in registry.active()
        ]
    }


@router.get("/store")
async def plugin_store(req: Request) -> dict[str, Any]:
    state = _state(req)
    installer = state["installer"]
    registry = state["registry"]
    installed = {m.id: m for m in registry.installed()}
    try:
        index = installer.fetch_index()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Plugin index unavailable: {exc}")
    out = []
    for entry in index:
        installed_manifest = installed.get(entry.id)
        out.append(
            {
                "id": entry.id,
                "name": entry.name,
                "description": entry.description,
                "author": entry.author,
                "version": entry.version,
                "requires_api_key": entry.requires_api_key,
                "requires_oauth": entry.requires_oauth,
                "dependencies": entry.dependencies,
                "installed": installed_manifest is not None,
                "installed_version": installed_manifest.version if installed_manifest else None,
                "update_available": (
                    installed_manifest is not None
                    and installed_manifest.version != entry.version
                ),
            }
        )
    return {"plugins": out}


class InstallRequest(BaseModel):
    id: str


@router.post("/install")
async def install_plugin(payload: InstallRequest, req: Request) -> dict[str, Any]:
    state = _state(req)
    installer = state["installer"]
    registry = state["registry"]
    try:
        installer.install(payload.id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc))
    registry.load_all()
    registry.activate(payload.id)
    return {"ok": True, "id": payload.id}


@router.post("/{plugin_id}/enable")
async def enable_plugin(plugin_id: str, req: Request) -> dict[str, Any]:
    registry = _state(req)["registry"]
    registry.activate(plugin_id)
    return {"ok": True, "active": True}


@router.post("/{plugin_id}/disable")
async def disable_plugin(plugin_id: str, req: Request) -> dict[str, Any]:
    registry = _state(req)["registry"]
    registry.deactivate(plugin_id)
    return {"ok": True, "active": False}


@router.delete("/{plugin_id}")
async def remove_plugin(plugin_id: str, req: Request) -> dict[str, Any]:
    state = _state(req)
    state["registry"].remove(plugin_id)
    return {"ok": True}


@router.get("/{plugin_id}/config")
async def get_config(plugin_id: str, req: Request) -> dict[str, Any]:
    db = _state(req)["db"]
    return {"config": db.config_all(plugin_id)}


class ConfigPayload(BaseModel):
    config: dict[str, Any]


@router.put("/{plugin_id}/config")
async def set_config(plugin_id: str, payload: ConfigPayload, req: Request) -> dict[str, Any]:
    state = _state(req)
    db = state["db"]
    registry = state["registry"]
    db.config_replace(plugin_id, payload.config)
    if registry.is_active(plugin_id):
        try:
            registry.reload(plugin_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"reload failed: {exc}")
    return {"ok": True}


@router.post("/{plugin_id}/update")
async def update_plugin(plugin_id: str, req: Request) -> dict[str, Any]:
    state = _state(req)
    installer = state["installer"]
    registry = state["registry"]
    was_active = registry.is_active(plugin_id)
    if was_active:
        registry.deactivate(plugin_id)
    installer.install(plugin_id)
    registry.load_all()
    if was_active:
        registry.activate(plugin_id)
    return {"ok": True}
