"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.config import Settings, get_settings
from apps.api.database import Database
from apps.api.errors import register_error_handlers
from apps.api.logging import configure_logging, get_logger
from apps.api.middleware import RequestContextMiddleware
from apps.api.routers import system_router


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    """Create an independently configurable FastAPI application."""

    application_settings = settings or get_settings()
    database_manager = database or Database(application_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(application_settings)
        app.state.database = database_manager
        app.state.ready = True
        get_logger().info("application_started", version=application_settings.app_version)
        try:
            yield
        finally:
            app.state.ready = False
            await database_manager.dispose()
            get_logger().info("application_stopped")

    app = FastAPI(
        title=application_settings.app_name,
        version=application_settings.app_version,
        debug=application_settings.app_debug,
        lifespan=lifespan,
    )
    app.state.ready = False
    app.state.settings = application_settings
    app.state.database = database_manager

    def provide_application_settings() -> Settings:
        return application_settings

    app.dependency_overrides[get_settings] = provide_application_settings
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(system_router)
    return app
