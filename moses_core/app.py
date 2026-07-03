"""FastAPI application factory.

Wires together: db, scheduler, plugin registry, plugin installer,
update manager, and HTTP routes. Static frontends are mounted at
/admin and /dashboard.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config as _config
from .api import (
    assets_router,
    layout_router,
    oauth_router,
    plugins_router,
    system_router,
)
from .db import get_db
from .plugin_system import PluginInstaller, PluginRegistry
from .services import Scheduler, UpdateManager

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_ADMIN = PROJECT_ROOT / "frontend" / "admin"
FRONTEND_DASHBOARD = PROJECT_ROOT / "frontend" / "dashboard"
FRONTEND_STATIC = PROJECT_ROOT / "frontend" / "static"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings = _config.settings
        db = get_db()
        scheduler = Scheduler(db)
        scheduler.start()
        registry = PluginRegistry(settings.plugins_dir, db, scheduler, app)
        installer = PluginInstaller(
            settings.plugin_registry_repo,
            settings.plugin_registry_branch,
            settings.plugins_dir,
        )
        updater = UpdateManager(settings.core_repo, settings.update_channel, PROJECT_ROOT)

        app.state.moses = {
            "db": db,
            "scheduler": scheduler,
            "registry": registry,
            "installer": installer,
            "updater": updater,
            "plugins_dir": settings.plugins_dir,
        }

        try:
            registry.load_all()
        except Exception:  # noqa: BLE001
            logger.exception("Plugin loading failed")

        yield

        scheduler.shutdown()

    app = FastAPI(title="MosEs Core", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(plugins_router)
    app.include_router(layout_router)
    app.include_router(oauth_router)
    app.include_router(system_router)
    app.include_router(assets_router)

    if FRONTEND_STATIC.exists():
        app.mount("/static", StaticFiles(directory=FRONTEND_STATIC), name="static")
    if FRONTEND_ADMIN.exists():
        app.mount("/admin", StaticFiles(directory=FRONTEND_ADMIN, html=True), name="admin")
    if FRONTEND_DASHBOARD.exists():
        app.mount(
            "/dashboard", StaticFiles(directory=FRONTEND_DASHBOARD, html=True), name="dashboard"
        )

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse("/dashboard")

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
