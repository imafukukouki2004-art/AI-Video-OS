"""Repository behavior tests for OAuth connection persistence."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.publishing.connection_repository import (
    OAuthStateConsumeStatus,
    PublishingConnectionRepository,
    PublishingCredentialRepository,
    PublishingOAuthStateRepository,
)
from apps.api.publishing.models import PublishingOAuthState


def session_returning(value) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = value
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_connection_and_credential_repository_queries() -> None:
    connection = Mock()
    connection_session = session_returning(connection)
    connection_repository = PublishingConnectionRepository(connection_session)

    assert await connection_repository.get_active("youtube") is connection

    list_result = Mock()
    list_result.scalars.return_value.all.return_value = [connection]
    connection_session.execute.return_value = list_result
    assert await connection_repository.list_active("youtube") == [connection]

    credential = Mock()
    credential_session = session_returning(credential)
    credential_repository = PublishingCredentialRepository(credential_session)
    assert await credential_repository.get_by_connection(uuid4()) is credential
    await credential_repository.delete_by_connection(uuid4())
    credential_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_oauth_state_consume_is_atomic_expiring_and_single_use() -> None:
    now = datetime.now(UTC)
    missing_repository = PublishingOAuthStateRepository(session_returning(None))
    assert (
        await missing_repository.consume("0" * 64, now)
    ).status is OAuthStateConsumeStatus.INVALID

    expired = PublishingOAuthState(
        id=uuid4(),
        connection_id=uuid4(),
        state_digest="1" * 64,
        expires_at=now - timedelta(seconds=1),
        created_at=now,
    )
    assert (
        await PublishingOAuthStateRepository(session_returning(expired)).consume("1" * 64, now)
    ).status is OAuthStateConsumeStatus.EXPIRED

    reused = PublishingOAuthState(
        id=uuid4(),
        connection_id=uuid4(),
        state_digest="2" * 64,
        expires_at=now + timedelta(minutes=1),
        consumed_at=now,
        created_at=now,
    )
    assert (
        await PublishingOAuthStateRepository(session_returning(reused)).consume("2" * 64, now)
    ).status is OAuthStateConsumeStatus.REUSED

    available = PublishingOAuthState(
        id=uuid4(),
        connection_id=uuid4(),
        state_digest="3" * 64,
        expires_at=now + timedelta(minutes=1),
        created_at=now,
    )
    available_session = session_returning(available)
    result = await PublishingOAuthStateRepository(available_session).consume("3" * 64, now)
    assert result.status is OAuthStateConsumeStatus.CONSUMED
    assert available.consumed_at == now
    available_session.commit.assert_awaited_once()
    available_session.refresh.assert_awaited_once_with(available)
