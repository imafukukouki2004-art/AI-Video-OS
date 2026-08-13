"""YouTube Data API publishing adapter."""

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Literal, Protocol, cast

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from pydantic import SecretStr

from apps.api.assets.models import Asset
from apps.api.publishing.providers import (
    PublishingProvider,
    PublishingProviderError,
    PublishingResponse,
)
from apps.api.storage import ObjectStorage, StorageOperationError

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_TOKEN_URI = "https://oauth2.googleapis.com/token"  # noqa: S105 - public OAuth endpoint
YOUTUBE_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
YouTubePrivacyStatus = Literal["private", "unlisted", "public"]


class YouTubeInsertRequest(Protocol):
    def execute(self) -> object: ...


class YouTubeVideosResource(Protocol):
    def insert(self, **kwargs: Any) -> YouTubeInsertRequest: ...


class YouTubeClient(Protocol):
    def videos(self) -> YouTubeVideosResource: ...


YouTubeClientFactory = Callable[[], YouTubeClient]
MediaUploadFactory = Callable[[BytesIO, str], object]


@dataclass(frozen=True, slots=True)
class YouTubeCredentialSettings:
    """Environment-provided OAuth material kept outside Publication persistence."""

    client_id: SecretStr
    client_secret: SecretStr
    refresh_token: SecretStr

    def is_configured(self) -> bool:
        return all(
            value.get_secret_value()
            for value in (self.client_id, self.client_secret, self.refresh_token)
        )


class YouTubePublishingError(PublishingProviderError):
    """Base for safe YouTube provider failures."""


class YouTubeConfigurationError(YouTubePublishingError):
    def __init__(self) -> None:
        super().__init__(
            "YOUTUBE_CONFIGURATION_ERROR",
            "YouTube publishing credentials are not configured.",
        )


class YouTubeAssetRetrievalError(YouTubePublishingError):
    def __init__(self) -> None:
        super().__init__(
            "YOUTUBE_ASSET_RETRIEVAL_ERROR",
            "The video asset could not be retrieved for YouTube publishing.",
        )


class YouTubeInvalidMediaError(YouTubePublishingError):
    def __init__(self) -> None:
        super().__init__(
            "YOUTUBE_INVALID_MEDIA",
            "The asset is not valid YouTube upload media.",
        )


class YouTubeUploadError(YouTubePublishingError):
    def __init__(self) -> None:
        super().__init__(
            "YOUTUBE_UPLOAD_ERROR",
            "YouTube could not upload the video.",
        )


class YouTubeMalformedResponseError(YouTubePublishingError):
    def __init__(self) -> None:
        super().__init__(
            "YOUTUBE_MALFORMED_RESPONSE",
            "YouTube returned an invalid upload response.",
        )


class YouTubePublishingProvider(PublishingProvider):
    """Upload an existing ObjectStorage video through YouTube Data API v3."""

    def __init__(
        self,
        storage: ObjectStorage,
        credentials: YouTubeCredentialSettings,
        *,
        privacy_status: YouTubePrivacyStatus = "private",
        client_factory: YouTubeClientFactory | None = None,
        media_upload_factory: MediaUploadFactory | None = None,
    ) -> None:
        self._storage = storage
        self._credentials = credentials
        self._privacy_status = privacy_status
        self._client_factory = client_factory or self._build_client
        self._media_upload_factory = media_upload_factory or self._build_media_upload

    async def publish(
        self,
        asset: Asset,
        *,
        title: str,
        description: str | None,
    ) -> PublishingResponse:
        if not self._credentials.is_configured():
            raise YouTubeConfigurationError

        try:
            stored_object = await self._storage.download(asset.object_key)
        except StorageOperationError as error:
            raise YouTubeAssetRetrievalError from error

        if (
            not asset.content_type.startswith("video/")
            or not stored_object.content_type.startswith("video/")
            or not stored_object.body
        ):
            raise YouTubeInvalidMediaError

        body = {
            "snippet": {
                "title": title,
                "description": description or "",
            },
            "status": {"privacyStatus": self._privacy_status},
        }
        try:
            response = await asyncio.to_thread(
                self._upload,
                stored_object.body,
                stored_object.content_type,
                body,
            )
        except PublishingProviderError:
            raise
        except Exception as error:
            raise YouTubeUploadError from error

        video_id = response.get("id") if isinstance(response, dict) else None
        if not isinstance(video_id, str) or not YOUTUBE_VIDEO_ID.fullmatch(video_id):
            raise YouTubeMalformedResponseError

        return PublishingResponse(
            external_id=video_id,
            external_url=f"https://www.youtube.com/watch?v={video_id}",
            metadata={
                "provider": "youtube",
                "privacy_status": self._privacy_status,
            },
        )

    def _upload(
        self,
        content: bytes,
        content_type: str,
        body: dict[str, object],
    ) -> object:
        client = self._client_factory()
        stream = BytesIO(content)
        try:
            media = self._media_upload_factory(stream, content_type)
            request = client.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
                notifySubscribers=False,
            )
            return request.execute()
        finally:
            stream.close()

    def _build_client(self) -> YouTubeClient:
        credentials = Credentials(  # type: ignore[no-untyped-call]
            token=None,
            refresh_token=self._credentials.refresh_token.get_secret_value(),
            token_uri=YOUTUBE_TOKEN_URI,
            client_id=self._credentials.client_id.get_secret_value(),
            client_secret=self._credentials.client_secret.get_secret_value(),
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )
        return cast(
            YouTubeClient,
            build("youtube", "v3", credentials=credentials, cache_discovery=False),
        )

    @staticmethod
    def _build_media_upload(stream: BytesIO, content_type: str) -> object:
        return MediaIoBaseUpload(stream, mimetype=content_type, resumable=False)
