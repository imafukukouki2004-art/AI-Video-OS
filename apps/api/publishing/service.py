"""Application service for the publication lifecycle."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from apps.api.assets.models import Asset
from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.providers import PublishingProvider, PublishingProviderResolver
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.schemas import PublicationCreate, PublicationUpdate
from apps.api.repositories import AssetRepository


class PublishingService:
    """Coordinate asset validation, provider execution, and persistence."""

    def __init__(
        self,
        publication_repository: PublicationRepository,
        asset_repository: AssetRepository,
        provider_resolver: PublishingProviderResolver,
    ) -> None:
        self.publication_repository = publication_repository
        self.asset_repository = asset_repository
        self.provider_resolver = provider_resolver

    async def create(self, publication_in: PublicationCreate) -> Publication:
        asset = await self._get_publishable_asset(publication_in.asset_id)
        self._resolve_provider(publication_in.provider)
        if not asset.object_key:
            raise self._invalid_asset()
        return await self.publication_repository.create(publication_in)

    async def get_by_id(self, publication_id: UUID) -> Publication | None:
        return await self.publication_repository.get_by_id(publication_id)

    async def list_by_asset(self, asset_id: UUID) -> Sequence[Publication]:
        await self._get_asset(asset_id)
        return await self.publication_repository.list_by_asset(asset_id)

    async def publish(self, publication_id: UUID) -> Publication:
        publication = await self.publication_repository.get_by_id(publication_id)
        if publication is None:
            raise ApplicationError(
                code="PUBLICATION_NOT_FOUND",
                message="Publication not found.",
                status_code=404,
            )
        if publication.status is not PublicationStatus.PENDING:
            raise ApplicationError(
                code="INVALID_PUBLICATION_STATE",
                message="Only pending publications can be published.",
                status_code=409,
            )

        asset = await self._get_publishable_asset(publication.asset_id)
        provider = self._resolve_provider(publication.provider)
        publishing = await self.publication_repository.update(
            publication.id,
            PublicationUpdate(status=PublicationStatus.PUBLISHING),
        )
        if publishing is None:
            raise ApplicationError(code="PUBLICATION_NOT_FOUND", message="Publication not found.")

        try:
            response = await provider.publish(
                asset,
                title=publication.title,
                description=publication.description,
            )
        except Exception as error:
            await self.publication_repository.update(
                publication.id,
                PublicationUpdate(
                    status=PublicationStatus.FAILED,
                    error_code="PUBLISHING_PROVIDER_ERROR",
                    error_message="The publishing provider could not publish the asset.",
                ),
            )
            raise ApplicationError(
                code="PUBLISHING_PROVIDER_ERROR",
                message="The publishing provider could not publish the asset.",
                status_code=502,
            ) from error

        if not response.external_id or not response.external_url:
            await self.publication_repository.update(
                publication.id,
                PublicationUpdate(
                    status=PublicationStatus.FAILED,
                    error_code="INVALID_PROVIDER_RESPONSE",
                    error_message="The publishing provider returned an invalid response.",
                ),
            )
            raise ApplicationError(
                code="INVALID_PROVIDER_RESPONSE",
                message="The publishing provider returned an invalid response.",
                status_code=502,
            )

        published = await self.publication_repository.update(
            publication.id,
            PublicationUpdate(
                status=PublicationStatus.PUBLISHED,
                external_id=response.external_id,
                external_url=response.external_url,
                provider_metadata=response.metadata,
                error_code=None,
                error_message=None,
                published_at=datetime.now(UTC),
            ),
        )
        if published is None:
            raise ApplicationError(code="PUBLICATION_NOT_FOUND", message="Publication not found.")
        return published

    async def _get_asset(self, asset_id: UUID) -> Asset:
        asset = await self.asset_repository.get_by_id(asset_id)
        if asset is None:
            raise ApplicationError(
                code="ASSET_NOT_FOUND",
                message="The requested asset was not found.",
                status_code=404,
            )
        return asset

    async def _get_publishable_asset(self, asset_id: UUID) -> Asset:
        asset = await self._get_asset(asset_id)
        if (
            not asset.content_type.startswith("video/")
            or not asset.object_key
            or asset.size_bytes <= 0
        ):
            raise self._invalid_asset()
        return asset

    def _resolve_provider(self, provider_name: str) -> PublishingProvider:
        try:
            return self.provider_resolver.resolve(provider_name)
        except ValueError as error:
            raise ApplicationError(
                code="UNSUPPORTED_PUBLISHING_PROVIDER",
                message="The publishing provider is not supported.",
                status_code=422,
            ) from error

    @staticmethod
    def _invalid_asset() -> ApplicationError:
        return ApplicationError(
            code="ASSET_NOT_PUBLISHABLE",
            message="The asset is not a publishable video.",
            status_code=422,
        )
