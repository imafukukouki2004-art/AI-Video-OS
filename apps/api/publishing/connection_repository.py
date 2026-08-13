"""Repositories for publishing connections, encrypted credentials, and OAuth state."""

import enum
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.publishing.models import (
    PublishingConnection,
    PublishingConnectionStatus,
    PublishingCredential,
    PublishingOAuthState,
)
from apps.api.publishing.schemas import (
    PublishingConnectionCreate,
    PublishingConnectionUpdate,
    PublishingCredentialCreate,
    PublishingCredentialUpdate,
    PublishingOAuthStateCreate,
    PublishingOAuthStateUpdate,
)
from apps.api.repositories.sqlalchemy import SQLAlchemyRepository


class OAuthStateConsumeStatus(str, enum.Enum):
    CONSUMED = "consumed"
    INVALID = "invalid"
    EXPIRED = "expired"
    REUSED = "reused"


@dataclass(frozen=True, slots=True)
class OAuthStateConsumeResult:
    status: OAuthStateConsumeStatus
    state: PublishingOAuthState | None = None


class PublishingConnectionRepository(
    SQLAlchemyRepository[
        PublishingConnection, PublishingConnectionCreate, PublishingConnectionUpdate
    ]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PublishingConnection)

    async def get_active(self, provider: str) -> PublishingConnection | None:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.provider == provider)
            .where(self.model.status == PublishingConnectionStatus.CONNECTED)
            .order_by(self.model.connected_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_active(self, provider: str) -> list[PublishingConnection]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.provider == provider)
            .where(self.model.status == PublishingConnectionStatus.CONNECTED)
            .order_by(self.model.connected_at)
        )
        return list(result.scalars().all())


class PublishingCredentialRepository(
    SQLAlchemyRepository[
        PublishingCredential, PublishingCredentialCreate, PublishingCredentialUpdate
    ]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PublishingCredential)

    async def get_by_connection(self, connection_id: UUID) -> PublishingCredential | None:
        result = await self.session.execute(
            select(self.model).where(self.model.connection_id == connection_id)
        )
        return result.scalar_one_or_none()

    async def delete_by_connection(self, connection_id: UUID) -> None:
        await self.session.execute(
            delete(self.model).where(self.model.connection_id == connection_id)
        )
        await self.session.commit()


class PublishingOAuthStateRepository(
    SQLAlchemyRepository[
        PublishingOAuthState, PublishingOAuthStateCreate, PublishingOAuthStateUpdate
    ]
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PublishingOAuthState)

    async def consume(self, state_digest: str, now: datetime) -> OAuthStateConsumeResult:
        result = await self.session.execute(
            select(self.model).where(self.model.state_digest == state_digest).with_for_update()
        )
        state = result.scalar_one_or_none()
        if state is None:
            return OAuthStateConsumeResult(OAuthStateConsumeStatus.INVALID)
        if state.consumed_at is not None:
            return OAuthStateConsumeResult(OAuthStateConsumeStatus.REUSED, state)
        if state.expires_at <= now:
            return OAuthStateConsumeResult(OAuthStateConsumeStatus.EXPIRED, state)
        state.consumed_at = now
        await self.session.commit()
        await self.session.refresh(state)
        return OAuthStateConsumeResult(OAuthStateConsumeStatus.CONSUMED, state)
