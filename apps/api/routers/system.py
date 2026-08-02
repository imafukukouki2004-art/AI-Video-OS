"""Process health and application readiness endpoints."""

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from apps.api.dependencies import DatabaseDependency, SettingsDependency

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    environment: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDependency) -> HealthResponse:
    """Report that the application process is running."""

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready(
    request: Request,
    response: Response,
    settings: SettingsDependency,
    database: DatabaseDependency,
) -> ReadyResponse:
    """Report readiness only when application startup and PostgreSQL are healthy."""

    database_ready = await database.check_connection()
    is_ready = request.app.state.ready and database_ready
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        service=settings.app_name,
        environment=settings.app_env,
        database="connected" if database_ready else "unavailable",
    )
