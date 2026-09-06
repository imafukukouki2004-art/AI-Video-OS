"""YouTube Data API publishing adapter."""

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Literal, Protocol, cast

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from pydantic import SecretStr

from apps.api.assets.models import Asset
from apps.api.publishing.providers import (
    ProviderErrorMetadata,
    PublishingProvider,
    PublishingProviderError,
    PublishingResponse,
)
from apps.api.storage import ObjectStorage, StorageOperationError

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_TOKEN_URI = "https://oauth2.googleapis.com/token"  # noqa: S105 - public OAuth endpoint
YOUTUBE_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
YouTubePrivacyStatus = Literal["private", "unlisted", "public"]
GOOGLE_ERROR_CODES = frozenset(
    {
        "ABORTED",
        "ALREADY_EXISTS",
        "FAILED_PRECONDITION",
        "INTERNAL",
        "INVALID_ARGUMENT",
        "NOT_FOUND",
        "PERMISSION_DENIED",
        "RESOURCE_EXHAUSTED",
        "UNAUTHENTICATED",
        "UNAVAILABLE",
    }
)
GOOGLE_ERROR_REASONS = frozenset(
    {
        "accountDelegationForbidden",
        "authError",
        "backendError",
        "badRequest",
        "categoryNotFound",
        "dailyLimitExceeded",
        "forbidden",
        "forbiddenLicenseSetting",
        "forbiddenPrivacySetting",
        "insufficientPermissions",
        "invalidCategoryId",
        "invalidDescription",
        "invalidFilename",
        "invalidPublishAt",
        "invalidRecordingDetails",
        "invalidTags",
        "invalidTitle",
        "invalidVideoGameTitle",
        "mediaBodyRequired",
        "quotaExceeded",
        "rateLimitExceeded",
        "uploadLimitExceeded",
        "youtubeSignupRequired",
    }
)
GOOGLE_OAUTH_ERROR_CODES = frozenset(
    {
        "invalid_client",
        "invalid_grant",
        "invalid_scope",
        "server_error",
        "temporarily_unavailable",
        "unauthorized_client",
    }
)


class YouTubeInsertRequest(Protocol):
    def execute(self) -> object: ...


class YouTubeVideosResource(Protocol):
    def insert(self, **kwargs: Any) -> YouTubeInsertRequest: ...


class YouTubeClient(Protocol):
    def videos(self) -> YouTubeVideosResource: ...


YouTubeClientFactory = Callable[["YouTubeCredentialSettings"], YouTubeClient]
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


class YouTubeCredentialSource(Protocol):
    async def resolve(self) -> YouTubeCredentialSettings | None: ...


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
    def __init__(self, metadata: ProviderErrorMetadata | None = None) -> None:
        super().__init__(
            "YOUTUBE_UPLOAD_ERROR",
            "YouTube could not upload the video.",
            metadata=metadata,
        )


class YouTubeMalformedResponseError(YouTubePublishingError):
    def __init__(self) -> None:
        super().__init__(
            "YOUTUBE_MALFORMED_RESPONSE",
            "YouTube returned an invalid upload response.",
        )


class YouTubeCredentialResolutionError(YouTubePublishingError):
    def __init__(self) -> None:
        super().__init__(
            "YOUTUBE_CREDENTIAL_RESOLUTION_ERROR",
            "Connected YouTube credentials could not be resolved.",
        )


class YouTubePublishingProvider(PublishingProvider):
    """Upload an existing ObjectStorage video through YouTube Data API v3."""

    def __init__(
        self,
        storage: ObjectStorage,
        credentials: YouTubeCredentialSettings | None = None,
        *,
        credential_source: YouTubeCredentialSource | None = None,
        privacy_status: YouTubePrivacyStatus = "private",
        client_factory: YouTubeClientFactory | None = None,
        media_upload_factory: MediaUploadFactory | None = None,
    ) -> None:
        self._storage = storage
        self._credentials = credentials
        self._credential_source = credential_source
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
        credentials = await self._resolve_credentials()

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
                credentials,
            )
        except PublishingProviderError:
            raise
        except Exception as error:
            metadata = self._unknown_error_metadata(error, "upload_thread")
            raise YouTubeUploadError(metadata) from error

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
        credentials: YouTubeCredentialSettings,
    ) -> object:
        stream = BytesIO(content)
        try:
            try:
                client = self._client_factory(credentials)
                media = self._media_upload_factory(stream, content_type)
                request = client.videos().insert(
                    part="snippet,status",
                    body=body,
                    media_body=media,
                    notifySubscribers=False,
                )
            except HttpError as error:
                raise YouTubeUploadError(
                    self._http_error_metadata(error, "request_construction")
                ) from error
            except RefreshError as error:
                raise YouTubeUploadError(
                    self._refresh_error_metadata(error, "request_construction")
                ) from error
            except Exception as error:
                raise YouTubeUploadError(
                    self._unknown_error_metadata(error, "request_construction")
                ) from error

            try:
                return request.execute()
            except HttpError as error:
                raise YouTubeUploadError(
                    self._http_error_metadata(error, "upload_execute")
                ) from error
            except RefreshError as error:
                raise YouTubeUploadError(
                    self._refresh_error_metadata(error, "token_refresh")
                ) from error
            except Exception as error:
                raise YouTubeUploadError(
                    self._unknown_error_metadata(error, "upload_execute")
                ) from error
        finally:
            stream.close()

    @staticmethod
    def _base_error_metadata(
        *,
        stage: str,
        category: str,
        exception_class: str,
    ) -> ProviderErrorMetadata:
        return {
            "provider": "youtube",
            "stage": stage,
            "error_category": category,
            "exception_class": exception_class,
        }

    @classmethod
    def _http_error_metadata(cls, error: HttpError, stage: str) -> ProviderErrorMetadata:
        metadata = cls._base_error_metadata(
            stage=stage,
            category="google_http_error",
            exception_class="HttpError",
        )
        status = error.status_code
        if isinstance(status, int):
            metadata["http_status"] = status

        google_code, google_reason = cls._allowlisted_google_error(error)
        if google_code is not None:
            metadata["google_code"] = google_code
        if google_reason is not None:
            metadata["google_reason"] = google_reason
        return metadata

    @classmethod
    def _allowlisted_google_error(cls, error: HttpError) -> tuple[str | None, str | None]:
        """Extract only known-safe symbolic fields; never retain the raw response body."""

        try:
            payload = json.loads(error.content.decode("utf-8"))
        except (UnicodeError, ValueError, TypeError):
            return None, None
        if not isinstance(payload, dict) or not isinstance(payload.get("error"), dict):
            return None, None

        error_payload = payload["error"]
        code_value = error_payload.get("status")
        google_code = code_value if code_value in GOOGLE_ERROR_CODES else None
        details = error_payload.get("errors")
        google_reason: str | None = None
        if isinstance(details, list):
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                reason = detail.get("reason")
                if reason in GOOGLE_ERROR_REASONS:
                    google_reason = reason
                    break
        return google_code, google_reason

    @classmethod
    def _refresh_error_metadata(
        cls,
        error: RefreshError,
        stage: str,
    ) -> ProviderErrorMetadata:
        metadata = cls._base_error_metadata(
            stage=stage,
            category="oauth_refresh_error",
            exception_class="RefreshError",
        )
        metadata["retryable"] = error.retryable
        if len(error.args) > 1 and isinstance(error.args[1], dict):
            code = error.args[1].get("error")
            if code in GOOGLE_OAUTH_ERROR_CODES:
                metadata["google_code"] = code
        return metadata

    @classmethod
    def _unknown_error_metadata(
        cls,
        error: Exception,
        stage: str,
    ) -> ProviderErrorMetadata:
        classifications: tuple[tuple[type[Exception], str, str], ...] = (
            (TimeoutError, "transport_timeout", "TimeoutError"),
            (ConnectionError, "transport_connection_error", "ConnectionError"),
            (ValueError, "invalid_sdk_input", "ValueError"),
        )
        for exception_type, category, exception_class in classifications:
            if isinstance(error, exception_type):
                return cls._base_error_metadata(
                    stage=stage,
                    category=category,
                    exception_class=exception_class,
                )
        return cls._base_error_metadata(
            stage=stage,
            category="unexpected_sdk_error",
            exception_class="Exception",
        )

    def _build_client(self, settings: YouTubeCredentialSettings) -> YouTubeClient:
        credentials = Credentials(  # type: ignore[no-untyped-call]
            token=None,
            refresh_token=settings.refresh_token.get_secret_value(),
            token_uri=YOUTUBE_TOKEN_URI,
            client_id=settings.client_id.get_secret_value(),
            client_secret=settings.client_secret.get_secret_value(),
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )
        return cast(
            YouTubeClient,
            build("youtube", "v3", credentials=credentials, cache_discovery=False),
        )

    async def _resolve_credentials(self) -> YouTubeCredentialSettings:
        if self._credential_source is not None:
            try:
                connected = await self._credential_source.resolve()
            except Exception as error:
                raise YouTubeCredentialResolutionError from error
            if connected is not None and connected.is_configured():
                return connected
        if self._credentials is not None and self._credentials.is_configured():
            return self._credentials
        raise YouTubeConfigurationError

    @staticmethod
    def _build_media_upload(stream: BytesIO, content_type: str) -> object:
        return MediaIoBaseUpload(stream, mimetype=content_type, resumable=False)
