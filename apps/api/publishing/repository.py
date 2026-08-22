"""SQLAlchemy repository for publication persistence."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.schemas import (
    AutomaticPublicationCreate,
    PublicationCreate,
    PublicationUpdate,
)
from apps.api.repositories.sqlalchemy import SQLAlchemyRepository


class PublicationRepository(
    SQLAlchemyRepository[Publication, PublicationCreate, PublicationUpdate]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Publication)

    async def list_by_asset(self, asset_id: UUID) -> Sequence[Publication]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.asset_id == asset_id)
            .order_by(self.model.created_at)
        )
        return result.scalars().all()

    async def list_by_execution(self, execution_id: UUID) -> Sequence[Publication]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.workflow_execution_id == execution_id)
            .order_by(self.model.created_at)
        )
        return result.scalars().all()

    async def get_automatic(
        self,
        workflow_execution_id: UUID,
        provider: str,
        asset_id: UUID,
    ) -> Publication | None:
        result = await self.session.execute(
            select(self.model).where(
                self.model.workflow_execution_id == workflow_execution_id,
                self.model.provider == provider,
                self.model.asset_id == asset_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_automatic(
        self,
        publication_in: AutomaticPublicationCreate,
    ) -> tuple[Publication, bool]:
        """Insert once using the database uniqueness constraint as the authority."""

        values = publication_in.model_dump()
        values["id"] = uuid4()
        statement = (
            insert(self.model)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_publications_auto_workflow_provider_asset")
            .returning(self.model)
        )
        result = await self.session.execute(statement)
        publication = result.scalar_one_or_none()
        await self.session.commit()
        if publication is not None:
            return publication, True

        existing = await self.get_automatic(
            publication_in.workflow_execution_id,
            publication_in.provider,
            publication_in.asset_id,
        )
        if existing is None:
            raise RuntimeError("Automatic publication conflict could not be resolved")
        return existing, False

    async def transition_status(
        self,
        publication_id: UUID,
        from_status: PublicationStatus,
        to_status: PublicationStatus,
        update_in: PublicationUpdate | None = None,
    ) -> Publication | None:
        """Atomically transition a publication when its current status matches."""

        values = update_in.model_dump(exclude_unset=True) if update_in is not None else {}
        values["status"] = to_status
        values["updated_at"] = datetime.now(UTC)
        result = await self.session.execute(
            update(self.model)
            .where(self.model.id == publication_id, self.model.status == from_status)
            .values(**values)
            .returning(self.model)
        )
        publication = result.scalar_one_or_none()
        await self.session.commit()
        if publication is not None:
            await self.session.refresh(publication)
        return publication
