"""API routers."""

from apps.api.assets.router import router as assets_router
from apps.api.routers.system import router as system_router

__all__ = ["assets_router", "system_router"]
