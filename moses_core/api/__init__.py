from .routes_plugins import router as plugins_router
from .routes_layout import router as layout_router
from .routes_oauth import router as oauth_router
from .routes_system import router as system_router
from .routes_assets import router as assets_router

__all__ = [
    "plugins_router",
    "layout_router",
    "oauth_router",
    "system_router",
    "assets_router",
]
