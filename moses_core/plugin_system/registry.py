"""Plugin registry: discovers, loads, and registers installed plugins."""

from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI

from ..db import Database
from .api import PluginAPI
from .manifest import PluginManifest

logger = logging.getLogger(__name__)


@dataclass
class LoadedPlugin:
    manifest: PluginManifest
    path: Path
    router: APIRouter | None
    api: PluginAPI | None
    module: Any | None


class PluginRegistry:
    def __init__(self, plugins_dir: Path, db: Database, scheduler: Any, app: FastAPI) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.db = db
        self.scheduler = scheduler
        self.app = app
        self._loaded: dict[str, LoadedPlugin] = {}
        self._mounted: dict[str, APIRouter] = {}

    # ---------------- discovery ----------------
    def discover(self) -> list[PluginManifest]:
        manifests: list[PluginManifest] = []
        if not self.plugins_dir.exists():
            return manifests
        for entry in sorted(self.plugins_dir.iterdir()):
            manifest_path = entry / "plugin.json"
            if entry.is_dir() and manifest_path.exists():
                try:
                    manifests.append(PluginManifest.load(manifest_path))
                except Exception as exc:  # noqa: BLE001
                    logger.error("Failed to parse %s: %s", manifest_path, exc)
        return manifests

    # ---------------- lifecycle ----------------
    def load_all(self) -> None:
        for manifest in self.discover():
            self._record_install(manifest)
            if self._is_enabled(manifest.id):
                try:
                    self.activate(manifest.id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Plugin %s failed to activate: %s", manifest.id, exc)

    def _record_install(self, manifest: PluginManifest) -> None:
        existing = {p["id"]: p for p in self.db.list_plugins()}
        if manifest.id not in existing:
            self.db.upsert_plugin(
                manifest.id,
                manifest.version,
                manifest.default_enabled,
                datetime.now(timezone.utc).isoformat(),
            )
            for field in manifest.settings_schema:
                if field.default is not None:
                    self.db.config_set(manifest.id, field.key, field.default)
        else:
            self.db.upsert_plugin(
                manifest.id,
                manifest.version,
                bool(existing[manifest.id]["enabled"]),
                existing[manifest.id]["installed_at"],
            )

    def _is_enabled(self, plugin_id: str) -> bool:
        for row in self.db.list_plugins():
            if row["id"] == plugin_id:
                return bool(row["enabled"])
        return False

    def activate(self, plugin_id: str) -> LoadedPlugin:
        if plugin_id in self._loaded:
            return self._loaded[plugin_id]
        manifest = self._manifest_for(plugin_id)
        path = self.plugins_dir / plugin_id
        router: APIRouter | None = None
        module = None
        api: PluginAPI | None = None

        backend_file = path / "backend.py"
        if manifest.has_backend and backend_file.exists():
            module_name = f"moses_plugins.{plugin_id}"
            spec = importlib.util.spec_from_file_location(module_name, backend_file)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot load plugin backend: {backend_file}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            api = PluginAPI(plugin_id, self.db, self.scheduler)
            if hasattr(module, "setup"):
                router = module.setup(api)
                if router is not None and not isinstance(router, APIRouter):
                    raise TypeError(f"Plugin {plugin_id}: setup() must return APIRouter or None")
            elif hasattr(module, "router"):
                router = module.router

            if router is not None:
                self.app.include_router(router, prefix=f"/api/plugins/{plugin_id}")
                self._mounted[plugin_id] = router

        self.db.set_enabled(plugin_id, True)
        self._loaded[plugin_id] = LoadedPlugin(
            manifest=manifest, path=path, router=router, api=api, module=module
        )
        logger.info("Activated plugin %s v%s", plugin_id, manifest.version)
        return self._loaded[plugin_id]

    def deactivate(self, plugin_id: str) -> None:
        loaded = self._loaded.pop(plugin_id, None)
        if loaded is None:
            self.db.set_enabled(plugin_id, False)
            return
        self.scheduler.remove_plugin_jobs(plugin_id)
        if loaded.module is not None and hasattr(loaded.module, "teardown"):
            try:
                loaded.module.teardown(loaded.api)
            except Exception:  # noqa: BLE001
                logger.exception("teardown failed for %s", plugin_id)
        if plugin_id in self._mounted:
            self._remove_router(plugin_id)
        self.db.set_enabled(plugin_id, False)
        logger.info("Deactivated plugin %s", plugin_id)

    def _remove_router(self, plugin_id: str) -> None:
        prefix = f"/api/plugins/{plugin_id}"
        self.app.router.routes = [
            r for r in self.app.router.routes if getattr(r, "path", "").startswith(prefix) is False
        ]
        self._mounted.pop(plugin_id, None)

    def reload(self, plugin_id: str) -> LoadedPlugin:
        if plugin_id in self._loaded:
            self.deactivate(plugin_id)
        # purge cached module
        module_name = f"moses_plugins.{plugin_id}"
        sys.modules.pop(module_name, None)
        return self.activate(plugin_id)

    # ---------------- queries ----------------
    def _manifest_for(self, plugin_id: str) -> PluginManifest:
        manifest_path = self.plugins_dir / plugin_id / "plugin.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Plugin {plugin_id} not installed")
        return PluginManifest.load(manifest_path)

    def get(self, plugin_id: str) -> LoadedPlugin | None:
        return self._loaded.get(plugin_id)

    def is_active(self, plugin_id: str) -> bool:
        return plugin_id in self._loaded

    def installed(self) -> list[PluginManifest]:
        return self.discover()

    def active(self) -> list[LoadedPlugin]:
        return list(self._loaded.values())

    def remove(self, plugin_id: str) -> None:
        self.deactivate(plugin_id)
        path = self.plugins_dir / plugin_id
        if path.exists():
            import shutil

            shutil.rmtree(path)
        self.db.delete_plugin(plugin_id)
        self.db.layout_remove(plugin_id)
