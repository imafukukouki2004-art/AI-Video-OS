"""Credential encryption and connected resolver security tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from apps.api.publishing.credentials import (
    CredentialCipher,
    CredentialResolutionError,
    CredentialSecurityError,
    YouTubeCredentialResolver,
)
from apps.api.publishing.models import (
    PublishingConnection,
    PublishingConnectionStatus,
    PublishingCredential,
)


def cipher() -> CredentialCipher:
    return CredentialCipher(SecretStr(Fernet.generate_key().decode()))


def test_refresh_token_is_authenticated_encrypted_and_key_is_required() -> None:
    credential_cipher = cipher()
    ciphertext = credential_cipher.encrypt(SecretStr("refresh-token-fixture"))

    assert "refresh-token-fixture" not in ciphertext
    assert credential_cipher.decrypt(ciphertext).get_secret_value() == "refresh-token-fixture"
    with pytest.raises(CredentialSecurityError):
        CredentialCipher(SecretStr("")).encrypt(SecretStr("refresh-token-fixture"))
    with pytest.raises(CredentialSecurityError):
        cipher().decrypt(ciphertext)


@pytest.mark.asyncio
async def test_connected_credential_is_decrypted_only_during_resolution() -> None:
    now = datetime.now(UTC)
    connection = PublishingConnection(
        id=uuid4(),
        provider="youtube",
        status=PublishingConnectionStatus.CONNECTED,
        scopes=[],
        created_at=now,
        updated_at=now,
    )
    credential_cipher = cipher()
    credential = PublishingCredential(
        id=uuid4(),
        connection_id=connection.id,
        encrypted_refresh_token=credential_cipher.encrypt(SecretStr("refresh-fixture")),
        created_at=now,
        updated_at=now,
    )
    connection_repository = AsyncMock()
    connection_repository.get_active.return_value = connection
    credential_repository = AsyncMock()
    credential_repository.get_by_connection.return_value = credential
    resolver = YouTubeCredentialResolver(
        connection_repository,
        credential_repository,
        credential_cipher,
        SecretStr("client"),
        SecretStr("secret"),
    )

    resolved = await resolver.resolve()

    assert resolved is not None
    assert resolved.refresh_token.get_secret_value() == "refresh-fixture"
    assert "refresh-fixture" not in credential.encrypted_refresh_token


@pytest.mark.asyncio
async def test_missing_connection_returns_none_and_invalid_ciphertext_is_safe() -> None:
    connection_repository = AsyncMock()
    connection_repository.get_active.return_value = None
    credential_repository = AsyncMock()
    resolver = YouTubeCredentialResolver(
        connection_repository,
        credential_repository,
        cipher(),
        SecretStr("client"),
        SecretStr("secret"),
    )
    assert await resolver.resolve() is None

    now = datetime.now(UTC)
    connection_repository.get_active.return_value = PublishingConnection(
        id=uuid4(),
        provider="youtube",
        status=PublishingConnectionStatus.CONNECTED,
        scopes=[],
        created_at=now,
        updated_at=now,
    )
    credential_repository.get_by_connection.return_value = None
    with pytest.raises(CredentialResolutionError):
        await resolver.resolve()
