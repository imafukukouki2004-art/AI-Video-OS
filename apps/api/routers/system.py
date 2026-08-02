"""Process health and application readiness endpoints."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from apps.api.dependencies import SettingsDependency

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDependency) -> HealthResponse:
    """Report that the application process is running."""

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request, settings: SettingsDependency) -> ReadyResponse:
    """Report readiness based only on application initialization in TICKET-002."""

    status = "ready" if request.app.state.ready else "not_ready"
    return ReadyResponse(
        status=status,
        service=settings.app_name,
        environment=settings.app_env,
    )
