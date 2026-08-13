"""API routers."""

from apps.api.assets.router import router as assets_router
from apps.api.domain.router import router as domain_router
from apps.api.publishing.router import router as publishing_router
from apps.api.routers.system import router as system_router

__all__ = ["assets_router", "domain_router", "publishing_router", "system_router"]
