"""External-call-free OAuth connection to YouTube publication E2E contract."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from apps.api.assets.models import Asset
from apps.api.publishing.connection_repository import (
    OAuthStateConsumeResult,
    OAuthStateConsumeStatus,
)
from apps.api.publishing.connection_service import YouTubeConnectionService
from apps.api.publishing.credentials import CredentialCipher, YouTubeCredentialResolver
from apps.api.publishing.models import (
    Publication,
    PublicationStatus,
    PublishingConnection,
    PublishingConnectionStatus,
    PublishingCredential,
    PublishingOAuthState,
)
from apps.api.publishing.oauth import GoogleYouTubeOAuthClient, OAuthTokenResult
from apps.api.publishing.providers import PublishingProviderResolver
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.schemas import PublicationCreate
from apps.api.publishing.service import PublishingService
from apps.api.publishing.youtube import (
    YOUTUBE_UPLOAD_SCOPE,
    YouTubeCredentialSettings,
    YouTubePublishingProvider,
)
from apps.api.repositories import AssetRepository
from apps.api.storage import ObjectStorage, StoredObject


@pytest.mark.asyncio
async def test_oauth_callback_encrypted_credential_drives_youtube_publication() -> None:
    now = datetime.now(UTC)
    connection = PublishingConnection(
        id=uuid4(),
        provider="youtube",
        status=PublishingConnectionStatus.PENDING,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
        created_at=now,
        updated_at=now,
    )
    connection_repository = AsyncMock()
    credential_repository = AsyncMock()
    state_repository = AsyncMock()
    connection_repository.create.return_value = connection
    connection_repository.list_active.return_value = []

    async def update_connection(connection_id, update):
        assert connection_id == connection.id
        for field, value in update.model_dump(exclude_unset=True).items():
            setattr(connection, field, value)
        return connection

    connection_repository.update.side_effect = update_connection
    oauth_client = AsyncMock(spec=GoogleYouTubeOAuthClient)
    oauth_client.authorization_url.side_effect = lambda state: f"https://auth.test?state={state}"
    oauth_client.exchange_code.return_value = OAuthTokenResult(
        SecretStr("refresh-token-plaintext"), (YOUTUBE_UPLOAD_SCOPE,)
    )
    credential_cipher = CredentialCipher(SecretStr(Fernet.generate_key().decode()))
    connection_service = YouTubeConnectionService(
        connection_repository,
        credential_repository,
        state_repository,
        oauth_client,
        credential_cipher,
        state_ttl_seconds=600,
    )

    authorization = await connection_service.authorize()
    state = parse_qs(urlparse(authorization.authorization_url).query)["state"][0]
    state_repository.consume.return_value = OAuthStateConsumeResult(
        OAuthStateConsumeStatus.CONSUMED,
        PublishingOAuthState(
            id=uuid4(),
            connection_id=connection.id,
            state_digest=connection_service.state_digest(state),
            expires_at=now + timedelta(minutes=10),
            created_at=now,
        ),
    )

    connected = await connection_service.callback(state, "authorization-code")
    credential_create = credential_repository.create.call_args.args[0]
    assert connected.status is PublishingConnectionStatus.CONNECTED
    assert "refresh-token-plaintext" not in credential_create.encrypted_refresh_token

    persisted_credential = PublishingCredential(
        id=uuid4(),
        connection_id=connection.id,
        encrypted_refresh_token=credential_create.encrypted_refresh_token,
        created_at=now,
        updated_at=now,
    )
    connection_repository.get_active.return_value = connection
    credential_repository.get_by_connection.return_value = persisted_credential
    resolver = YouTubeCredentialResolver(
        connection_repository,
        credential_repository,
        credential_cipher,
        SecretStr("client-fixture"),
        SecretStr("secret-fixture"),
    )

    asset = Asset(
        id=uuid4(),
        object_key="assets/final.mp4",
        filename="final.mp4",
        content_type="video/mp4",
        size_bytes=5,
        created_at=now,
    )
    storage = AsyncMock(spec=ObjectStorage)
    storage.download.return_value = StoredObject(body=b"video", content_type="video/mp4")
    request = Mock()
    request.execute.return_value = {"id": "oauth-connected-video"}
    videos = Mock()
    videos.insert.return_value = request
    client = Mock()
    client.videos.return_value = videos
    seen_tokens: list[str] = []

    def client_factory(settings: YouTubeCredentialSettings):
        seen_tokens.append(settings.refresh_token.get_secret_value())
        return client

    youtube = YouTubePublishingProvider(
        storage,
        credential_source=resolver,
        client_factory=client_factory,
        media_upload_factory=lambda stream, content_type: "media",
    )
    publication_repository = AsyncMock(spec=PublicationRepository)
    asset_repository = AsyncMock(spec=AssetRepository)
    asset_repository.get_by_id.return_value = asset
    publication = Publication(
        id=uuid4(),
        asset_id=asset.id,
        provider="youtube",
        status=PublicationStatus.PENDING,
        title="Connected upload",
        provider_metadata={},
        created_at=now,
        updated_at=now,
    )
    publication_repository.create.return_value = publication
    publication_repository.get_by_id.return_value = publication

    async def update_publication(publication_id, update):
        assert publication_id == publication.id
        for field, value in update.model_dump(exclude_unset=True).items():
            setattr(publication, field, value)
        return publication

    publication_repository.update.side_effect = update_publication
    publishing = PublishingService(
        publication_repository,
        asset_repository,
        PublishingProviderResolver({"youtube": youtube}),
    )
    created = await publishing.create(
        PublicationCreate(asset_id=asset.id, provider="youtube", title="Connected upload")
    )
    published = await publishing.publish(created.id)

    assert published.status is PublicationStatus.PUBLISHED
    assert published.external_id == "oauth-connected-video"
    assert published.external_url == "https://www.youtube.com/watch?v=oauth-connected-video"
    assert seen_tokens == ["refresh-token-plaintext"]
