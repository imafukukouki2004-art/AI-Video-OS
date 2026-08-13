"""Encrypted credential storage and YouTube credential resolution."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from apps.api.publishing.models import (
    PublishingConnection,
    PublishingConnectionStatus,
    PublishingCredential,
)
from apps.api.publishing.youtube import YouTubeCredentialSettings


class CredentialSecurityError(Exception):
    """Fail-closed credential encryption or decryption error."""


class CredentialResolutionError(Exception):
    """Connected credential exists but cannot be safely resolved."""


class CredentialCipher:
    """Authenticated encryption for refresh tokens using an external Fernet key."""

    def __init__(self, encryption_key: SecretStr) -> None:
        self._encryption_key = encryption_key

    def ensure_configured(self) -> None:
        self._fernet()

    def encrypt(self, plaintext: SecretStr) -> str:
        try:
            return self._fernet().encrypt(plaintext.get_secret_value().encode()).decode()
        except CredentialSecurityError:
            raise
        except Exception as error:
            raise CredentialSecurityError from error

    def decrypt(self, ciphertext: str) -> SecretStr:
        try:
            plaintext = self._fernet().decrypt(ciphertext.encode()).decode()
        except (InvalidToken, UnicodeError, ValueError) as error:
            raise CredentialSecurityError from error
        return SecretStr(plaintext)

    def _fernet(self) -> Fernet:
        key = self._encryption_key.get_secret_value()
        if not key:
            raise CredentialSecurityError
        try:
            return Fernet(key.encode())
        except (TypeError, ValueError) as error:
            raise CredentialSecurityError from error


class ConnectionReader(Protocol):
    async def get_active(self, provider: str) -> PublishingConnection | None: ...


class CredentialReader(Protocol):
    async def get_by_connection(self, connection_id: UUID) -> PublishingCredential | None: ...


@dataclass(frozen=True, slots=True)
class YouTubeCredentialResolver:
    """Resolve the operator's active encrypted YouTube credential."""

    connection_repository: ConnectionReader
    credential_repository: CredentialReader
    cipher: CredentialCipher
    client_id: SecretStr
    client_secret: SecretStr

    async def resolve(self) -> YouTubeCredentialSettings | None:
        connection = await self.connection_repository.get_active("youtube")
        if connection is None:
            return None
        if connection.status is not PublishingConnectionStatus.CONNECTED:
            return None
        credential = await self.credential_repository.get_by_connection(connection.id)
        if credential is None:
            raise CredentialResolutionError
        try:
            refresh_token = self.cipher.decrypt(credential.encrypted_refresh_token)
        except CredentialSecurityError as error:
            raise CredentialResolutionError from error
        return YouTubeCredentialSettings(
            client_id=self.client_id,
            client_secret=self.client_secret,
            refresh_token=refresh_token,
        )
