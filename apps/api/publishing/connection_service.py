"""Operator-level YouTube OAuth connection lifecycle."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import SecretStr

from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.connection_repository import (
    OAuthStateConsumeStatus,
    PublishingConnectionRepository,
    PublishingCredentialRepository,
    PublishingOAuthStateRepository,
)
from apps.api.publishing.credentials import CredentialCipher, CredentialSecurityError
from apps.api.publishing.models import PublishingConnection, PublishingConnectionStatus
from apps.api.publishing.oauth import (
    GoogleYouTubeOAuthClient,
    OAuthConfigurationError,
    OAuthRefreshTokenMissingError,
    OAuthTokenExchangeError,
)
from apps.api.publishing.schemas import (
    PublishingConnectionCreate,
    PublishingConnectionUpdate,
    PublishingCredentialCreate,
    PublishingOAuthStateCreate,
    YouTubeAuthorizationResponse,
)
from apps.api.publishing.youtube import YOUTUBE_UPLOAD_SCOPE


class YouTubeConnectionService:
    """Coordinate OAuth state, token encryption, and connection persistence."""

    def __init__(
        self,
        connection_repository: PublishingConnectionRepository,
        credential_repository: PublishingCredentialRepository,
        state_repository: PublishingOAuthStateRepository,
        oauth_client: GoogleYouTubeOAuthClient,
        cipher: CredentialCipher,
        *,
        state_ttl_seconds: int,
    ) -> None:
        self.connection_repository = connection_repository
        self.credential_repository = credential_repository
        self.state_repository = state_repository
        self.oauth_client = oauth_client
        self.cipher = cipher
        self.state_ttl_seconds = state_ttl_seconds

    async def authorize(self) -> YouTubeAuthorizationResponse:
        self._ensure_configuration()
        now = datetime.now(UTC)
        connection = await self.connection_repository.create(
            PublishingConnectionCreate(
                provider="youtube",
                scopes=[YOUTUBE_UPLOAD_SCOPE],
            )
        )
        state = secrets.token_urlsafe(32)
        expires_at = now + timedelta(seconds=self.state_ttl_seconds)
        await self.state_repository.create(
            PublishingOAuthStateCreate(
                connection_id=connection.id,
                state_digest=self.state_digest(state),
                expires_at=expires_at,
            )
        )
        return YouTubeAuthorizationResponse(
            connection_id=connection.id,
            authorization_url=self.oauth_client.authorization_url(state),
            expires_at=expires_at,
        )

    async def callback(self, state: str | None, code: str | None) -> PublishingConnection:
        if not state:
            raise self._error("YOUTUBE_OAUTH_INVALID_STATE", "OAuth state is invalid.", 400)
        consumed = await self.state_repository.consume(self.state_digest(state), datetime.now(UTC))
        if consumed.status is OAuthStateConsumeStatus.INVALID:
            raise self._error("YOUTUBE_OAUTH_INVALID_STATE", "OAuth state is invalid.", 400)
        if consumed.status is OAuthStateConsumeStatus.EXPIRED:
            raise self._error("YOUTUBE_OAUTH_EXPIRED_STATE", "OAuth state has expired.", 400)
        if consumed.status is OAuthStateConsumeStatus.REUSED:
            raise self._error("YOUTUBE_OAUTH_REUSED_STATE", "OAuth state was already used.", 409)
        if consumed.state is None:  # pragma: no cover - repository contract guard
            raise self._error("YOUTUBE_OAUTH_INVALID_STATE", "OAuth state is invalid.", 400)

        connection_id = consumed.state.connection_id
        if not code:
            await self._mark_failed(
                connection_id,
                "YOUTUBE_OAUTH_CODE_MISSING",
                "OAuth authorization code is missing.",
            )
            raise self._error(
                "YOUTUBE_OAUTH_CODE_MISSING", "OAuth authorization code is missing.", 400
            )

        try:
            self._ensure_configuration()
            token = await self.oauth_client.exchange_code(SecretStr(code))
            ciphertext = self.cipher.encrypt(token.refresh_token)
        except OAuthConfigurationError as error:
            await self._mark_failed(
                connection_id,
                "YOUTUBE_OAUTH_CONFIGURATION_ERROR",
                "YouTube OAuth is not configured.",
            )
            raise self._error(
                "YOUTUBE_OAUTH_CONFIGURATION_ERROR", "YouTube OAuth is not configured.", 503
            ) from error
        except OAuthRefreshTokenMissingError as error:
            await self._mark_failed(
                connection_id,
                "YOUTUBE_OAUTH_REFRESH_TOKEN_MISSING",
                "Google did not return the required offline credential.",
            )
            raise self._error(
                "YOUTUBE_OAUTH_REFRESH_TOKEN_MISSING",
                "Google did not return the required offline credential.",
                502,
            ) from error
        except OAuthTokenExchangeError as error:
            await self._mark_failed(
                connection_id,
                "YOUTUBE_OAUTH_TOKEN_EXCHANGE_FAILED",
                "YouTube OAuth token exchange failed.",
            )
            raise self._error(
                "YOUTUBE_OAUTH_TOKEN_EXCHANGE_FAILED",
                "YouTube OAuth token exchange failed.",
                502,
            ) from error
        except CredentialSecurityError as error:
            await self._mark_failed(
                connection_id,
                "YOUTUBE_CREDENTIAL_ENCRYPTION_FAILED",
                "YouTube credential could not be stored securely.",
            )
            raise self._error(
                "YOUTUBE_CREDENTIAL_ENCRYPTION_FAILED",
                "YouTube credential could not be stored securely.",
                500,
            ) from error

        await self.credential_repository.create(
            PublishingCredentialCreate(
                connection_id=connection_id,
                encrypted_refresh_token=ciphertext,
            )
        )
        connected = await self.connection_repository.update(
            connection_id,
            PublishingConnectionUpdate(
                status=PublishingConnectionStatus.CONNECTED,
                scopes=list(token.scopes),
                error_code=None,
                error_message=None,
                connected_at=datetime.now(UTC),
                disconnected_at=None,
            ),
        )
        if connected is None:  # pragma: no cover - state FK contract guard
            raise self._error(
                "YOUTUBE_CONNECTION_NOT_FOUND", "YouTube connection was not found.", 404
            )
        await self._disconnect_previous_connections(connection_id)
        return connected

    async def get(self, connection_id: UUID) -> PublishingConnection:
        connection = await self.connection_repository.get_by_id(connection_id)
        if connection is None:
            raise self._error(
                "YOUTUBE_CONNECTION_NOT_FOUND", "YouTube connection was not found.", 404
            )
        return connection

    async def disconnect(self, connection_id: UUID) -> PublishingConnection:
        connection = await self.get(connection_id)
        if connection.status is PublishingConnectionStatus.DISCONNECTED:
            return connection
        await self.credential_repository.delete_by_connection(connection.id)
        disconnected = await self.connection_repository.update(
            connection.id,
            PublishingConnectionUpdate(
                status=PublishingConnectionStatus.DISCONNECTED,
                disconnected_at=datetime.now(UTC),
            ),
        )
        if disconnected is None:  # pragma: no cover - fetched immediately above
            raise self._error(
                "YOUTUBE_CONNECTION_NOT_FOUND", "YouTube connection was not found.", 404
            )
        return disconnected

    def _ensure_configuration(self) -> None:
        try:
            self.oauth_client.ensure_configured()
            self.cipher.ensure_configured()
        except (OAuthConfigurationError, CredentialSecurityError) as error:
            raise self._error(
                "YOUTUBE_OAUTH_CONFIGURATION_ERROR", "YouTube OAuth is not configured.", 503
            ) from error

    async def _mark_failed(self, connection_id: UUID, code: str, message: str) -> None:
        await self.connection_repository.update(
            connection_id,
            PublishingConnectionUpdate(
                status=PublishingConnectionStatus.FAILED,
                error_code=code,
                error_message=message,
            ),
        )

    async def _disconnect_previous_connections(self, connection_id: UUID) -> None:
        for connection in await self.connection_repository.list_active("youtube"):
            if connection.id == connection_id:
                continue
            await self.credential_repository.delete_by_connection(connection.id)
            await self.connection_repository.update(
                connection.id,
                PublishingConnectionUpdate(
                    status=PublishingConnectionStatus.DISCONNECTED,
                    disconnected_at=datetime.now(UTC),
                ),
            )

    @staticmethod
    def state_digest(state: str) -> str:
        return hashlib.sha256(state.encode()).hexdigest()

    @staticmethod
    def _error(code: str, message: str, status_code: int) -> ApplicationError:
        return ApplicationError(code=code, message=message, status_code=status_code)
