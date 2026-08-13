"""Unit tests for the operator-level YouTube connection lifecycle."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.connection_repository import (
    OAuthStateConsumeResult,
    OAuthStateConsumeStatus,
)
from apps.api.publishing.connection_service import YouTubeConnectionService
from apps.api.publishing.credentials import CredentialCipher
from apps.api.publishing.models import (
    PublishingConnection,
    PublishingConnectionStatus,
    PublishingOAuthState,
)
from apps.api.publishing.oauth import (
    GoogleYouTubeOAuthClient,
    OAuthConfigurationError,
    OAuthTokenExchangeError,
    OAuthTokenResult,
)
from apps.api.publishing.youtube import YOUTUBE_UPLOAD_SCOPE


def connection(status: PublishingConnectionStatus = PublishingConnectionStatus.PENDING):
    now = datetime.now(UTC)
    return PublishingConnection(
        id=uuid4(),
        provider="youtube",
        status=status,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
        created_at=now,
        updated_at=now,
    )


def service():
    connection_repository = AsyncMock()
    credential_repository = AsyncMock()
    state_repository = AsyncMock()
    oauth_client = AsyncMock(spec=GoogleYouTubeOAuthClient)
    oauth_client.authorization_url.side_effect = lambda state: f"https://auth.test?state={state}"
    oauth_client.exchange_code.return_value = OAuthTokenResult(
        SecretStr("refresh-token-plaintext"), (YOUTUBE_UPLOAD_SCOPE,)
    )
    credential_cipher = CredentialCipher(SecretStr(Fernet.generate_key().decode()))
    return (
        YouTubeConnectionService(
            connection_repository,
            credential_repository,
            state_repository,
            oauth_client,
            credential_cipher,
            state_ttl_seconds=600,
        ),
        connection_repository,
        credential_repository,
        state_repository,
        oauth_client,
    )


@pytest.mark.asyncio
async def test_authorize_generates_unpredictable_hashed_expiring_single_use_state() -> None:
    connection_record = connection()
    target, connection_repository, _, state_repository, oauth_client = service()
    connection_repository.create.return_value = connection_record

    first = await target.authorize()
    second = await target.authorize()

    first_state = parse_qs(urlparse(first.authorization_url).query)["state"][0]
    second_state = parse_qs(urlparse(second.authorization_url).query)["state"][0]
    assert first_state != second_state
    assert len(first_state) >= 40
    state_create = state_repository.create.call_args_list[0].args[0]
    assert state_create.state_digest == target.state_digest(first_state)
    assert first_state not in state_create.state_digest
    assert first.expires_at > datetime.now(UTC) + timedelta(minutes=9)
    oauth_client.ensure_configured.assert_called()


@pytest.mark.asyncio
async def test_callback_consumes_state_encrypts_token_and_connects() -> None:
    pending = connection()
    connected = connection(PublishingConnectionStatus.CONNECTED)
    target, connection_repository, credential_repository, state_repository, _ = service()
    state_repository.consume.return_value = OAuthStateConsumeResult(
        OAuthStateConsumeStatus.CONSUMED,
        PublishingOAuthState(
            id=uuid4(),
            connection_id=pending.id,
            state_digest=target.state_digest("state"),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            created_at=datetime.now(UTC),
        ),
    )
    connection_repository.list_active.return_value = []
    connection_repository.update.return_value = connected

    result = await target.callback("state", "authorization-code-sensitive")

    assert result.status is PublishingConnectionStatus.CONNECTED
    credential_create = credential_repository.create.call_args.args[0]
    assert credential_create.connection_id == pending.id
    assert "refresh-token-plaintext" not in credential_create.encrypted_refresh_token
    update = connection_repository.update.call_args.args[1]
    assert update.scopes == [YOUTUBE_UPLOAD_SCOPE]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (OAuthStateConsumeStatus.INVALID, "YOUTUBE_OAUTH_INVALID_STATE"),
        (OAuthStateConsumeStatus.EXPIRED, "YOUTUBE_OAUTH_EXPIRED_STATE"),
        (OAuthStateConsumeStatus.REUSED, "YOUTUBE_OAUTH_REUSED_STATE"),
    ],
)
async def test_callback_rejects_invalid_expired_and_reused_state(status, expected_code) -> None:
    target, _, credential_repository, state_repository, oauth_client = service()
    state_repository.consume.return_value = OAuthStateConsumeResult(status)

    with pytest.raises(ApplicationError) as raised:
        await target.callback("state", "code")

    assert raised.value.code == expected_code
    oauth_client.exchange_code.assert_not_awaited()
    credential_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_code_marks_connection_failed_without_leaking_state() -> None:
    pending = connection()
    target, connection_repository, credential_repository, state_repository, _ = service()
    state_repository.consume.return_value = OAuthStateConsumeResult(
        OAuthStateConsumeStatus.CONSUMED,
        PublishingOAuthState(
            id=uuid4(),
            connection_id=pending.id,
            state_digest=target.state_digest("state"),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            created_at=datetime.now(UTC),
        ),
    )

    with pytest.raises(ApplicationError) as raised:
        await target.callback("state", None)

    assert raised.value.code == "YOUTUBE_OAUTH_CODE_MISSING"
    assert "state" not in raised.value.message
    assert (
        connection_repository.update.call_args.args[1].status is PublishingConnectionStatus.FAILED
    )
    credential_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_disconnect_deletes_credential_and_disables_connection() -> None:
    connected = connection(PublishingConnectionStatus.CONNECTED)
    disconnected = connection(PublishingConnectionStatus.DISCONNECTED)
    target, connection_repository, credential_repository, _, _ = service()
    connection_repository.get_by_id.return_value = connected
    connection_repository.update.return_value = disconnected

    result = await target.disconnect(connected.id)

    assert result.status is PublishingConnectionStatus.DISCONNECTED
    credential_repository.delete_by_connection.assert_awaited_once_with(connected.id)
    assert (
        connection_repository.update.call_args.args[1].status
        is PublishingConnectionStatus.DISCONNECTED
    )


@pytest.mark.asyncio
async def test_missing_configuration_fails_before_persistence() -> None:
    target, connection_repository, _, _, oauth_client = service()
    oauth_client.ensure_configured.side_effect = OAuthConfigurationError()

    with pytest.raises(ApplicationError) as raised:
        await target.authorize()

    assert raised.value.code == "YOUTUBE_OAUTH_CONFIGURATION_ERROR"
    connection_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_token_exchange_failure_marks_connection_failed_with_safe_error() -> None:
    pending = connection()
    target, connection_repository, credential_repository, state_repository, oauth_client = service()
    state_repository.consume.return_value = OAuthStateConsumeResult(
        OAuthStateConsumeStatus.CONSUMED,
        PublishingOAuthState(
            id=uuid4(),
            connection_id=pending.id,
            state_digest=target.state_digest("state"),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            created_at=datetime.now(UTC),
        ),
    )
    oauth_client.exchange_code.side_effect = OAuthTokenExchangeError("sensitive-token")

    with pytest.raises(ApplicationError) as raised:
        await target.callback("state", "sensitive-code")

    assert raised.value.code == "YOUTUBE_OAUTH_TOKEN_EXCHANGE_FAILED"
    assert "sensitive" not in raised.value.message
    assert (
        connection_repository.update.call_args.args[1].status is PublishingConnectionStatus.FAILED
    )
    credential_repository.create.assert_not_awaited()
