"""SQLAlchemy repository for publication persistence."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.schemas import PublicationCreate, PublicationUpdate
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
