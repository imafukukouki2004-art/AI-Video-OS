"""SQLAlchemy repository for publication persistence."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.publishing.models import Publication
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
