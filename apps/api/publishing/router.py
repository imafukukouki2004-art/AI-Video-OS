"""Publishing foundation API routes."""

from uuid import UUID

from fastapi import APIRouter, status

from apps.api.dependencies import PublishingServiceDependency
from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.schemas import PublicationCreate, PublicationResponse

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
