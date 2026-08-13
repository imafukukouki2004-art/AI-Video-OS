"""Publishing foundation API routes."""

from uuid import UUID

from fastapi import APIRouter, status

from apps.api.dependencies import (
    PublishingQueueServiceDependency,
    PublishingServiceDependency,
    YouTubeConnectionServiceDependency,
)
from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.schemas import (
    PublicationCreate,
    PublicationResponse,
    PublicationSchedule,
    PublishingConnectionResponse,
    YouTubeAuthorizationResponse,
)

router = APIRouter(tags=["publishing"])


@router.post(
    "/publications",
    response_model=PublicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_publication(
    publication_in: PublicationCreate,
    service: PublishingServiceDependency,
) -> PublicationResponse:
    publication = await service.create(publication_in)
    return PublicationResponse.model_validate(publication)


@router.get("/publications/{publication_id}", response_model=PublicationResponse)
async def get_publication(
    publication_id: UUID,
    service: PublishingServiceDependency,
) -> PublicationResponse:
    publication = await service.get_by_id(publication_id)
    if publication is None:
        raise ApplicationError(
            code="PUBLICATION_NOT_FOUND",
            message="Publication not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return PublicationResponse.model_validate(publication)


@router.get("/assets/{asset_id}/publications", response_model=list[PublicationResponse])
async def list_asset_publications(
    asset_id: UUID,
    service: PublishingServiceDependency,
) -> list[PublicationResponse]:
    publications = await service.list_by_asset(asset_id)
    return [PublicationResponse.model_validate(publication) for publication in publications]


@router.post("/publications/{publication_id}/publish", response_model=PublicationResponse)
async def publish_publication(
    publication_id: UUID,
    service: PublishingServiceDependency,
) -> PublicationResponse:
    publication = await service.publish(publication_id)
    return PublicationResponse.model_validate(publication)


@router.post(
    "/publications/{publication_id}/enqueue",
    response_model=PublicationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_publication(
    publication_id: UUID,
    service: PublishingQueueServiceDependency,
) -> PublicationResponse:
    publication = await service.enqueue(publication_id)
    return PublicationResponse.model_validate(publication)


@router.post(
    "/publications/{publication_id}/schedule",
    response_model=PublicationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def schedule_publication(
    publication_id: UUID,
    schedule: PublicationSchedule,
    service: PublishingQueueServiceDependency,
) -> PublicationResponse:
    publication = await service.enqueue(publication_id, scheduled_at=schedule.scheduled_at)
    return PublicationResponse.model_validate(publication)


@router.post(
    "/publishing/connections/youtube/authorize",
    response_model=YouTubeAuthorizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def authorize_youtube_connection(
    service: YouTubeConnectionServiceDependency,
) -> YouTubeAuthorizationResponse:
    return await service.authorize()


@router.get(
    "/publishing/connections/youtube/callback",
    response_model=PublishingConnectionResponse,
)
async def youtube_connection_callback(
    service: YouTubeConnectionServiceDependency,
    state: str | None = None,
    code: str | None = None,
) -> PublishingConnectionResponse:
    connection = await service.callback(state, code)
    return PublishingConnectionResponse.model_validate(connection)


@router.get(
    "/publishing/connections/{connection_id}",
    response_model=PublishingConnectionResponse,
)
async def get_publishing_connection(
    connection_id: UUID,
    service: YouTubeConnectionServiceDependency,
) -> PublishingConnectionResponse:
    connection = await service.get(connection_id)
    return PublishingConnectionResponse.model_validate(connection)


@router.delete(
    "/publishing/connections/{connection_id}",
    response_model=PublishingConnectionResponse,
)
async def disconnect_publishing_connection(
    connection_id: UUID,
    service: YouTubeConnectionServiceDependency,
) -> PublishingConnectionResponse:
    connection = await service.disconnect(connection_id)
    return PublishingConnectionResponse.model_validate(connection)
