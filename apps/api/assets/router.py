"""Asset upload, download, metadata, and presigned URL endpoints."""

import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, UploadFile, status
from sqlalchemy import select
from starlette.responses import Response

from apps.api.assets.models import Asset
from apps.api.assets.schemas import AssetResponse, PresignedUrlResponse
from apps.api.dependencies import DatabaseSessionDependency, SettingsDependency, StorageDependency
from apps.api.errors.exceptions import ApplicationError
from apps.api.logging import get_logger
from apps.api.storage import StorageOperationError

router = APIRouter(prefix="/assets", tags=["assets"])
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
ALLOWED_CONTENT_TYPE_PREFIXES = ("audio/", "image/", "video/")


def safe_filename(filename: str | None) -> str:
    """Remove path components and unsafe object-key characters."""

    basename = Path(filename or "upload.bin").name
    sanitized = SAFE_FILENAME.sub("-", basename).strip(".-")
    return (sanitized or "upload.bin")[:255]


def storage_unavailable() -> ApplicationError:
    return ApplicationError(
        code="STORAGE_UNAVAILABLE",
        message="Object storage is currently unavailable.",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


async def get_asset(asset_id: UUID, session: DatabaseSessionDependency) -> Asset:
    result = await session.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise ApplicationError(
            code="ASSET_NOT_FOUND",
            message="The requested asset was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return asset


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile,
    settings: SettingsDependency,
    session: DatabaseSessionDependency,
    storage: StorageDependency,
) -> AssetResponse:
    """Validate and persist one object plus its minimal metadata."""

    content_type = file.content_type or "application/octet-stream"
    if not content_type.startswith(ALLOWED_CONTENT_TYPE_PREFIXES):
        raise ApplicationError(
            code="UNSUPPORTED_ASSET_TYPE",
            message="The uploaded asset type is not supported.",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    try:
        body = await file.read(settings.storage_max_upload_bytes + 1)
    finally:
        await file.close()
    if not body:
        raise ApplicationError(code="EMPTY_ASSET", message="The uploaded asset is empty.")
    if len(body) > settings.storage_max_upload_bytes:
        raise ApplicationError(
            code="ASSET_TOO_LARGE",
            message="The uploaded asset exceeds the size limit.",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    asset_id = uuid4()
    filename = safe_filename(file.filename)
    object_key = f"assets/{asset_id}/{filename}"
    try:
        await storage.upload(object_key, body, content_type)
    except StorageOperationError as error:
        raise storage_unavailable() from error

    asset = Asset(
        id=asset_id,
        object_key=object_key,
        filename=filename,
        content_type=content_type,
        size_bytes=len(body),
        created_at=datetime.now(UTC),
    )
    session.add(asset)
    try:
        await session.commit()
        await session.refresh(asset)
    except Exception:
        try:
            await storage.delete(object_key)
        except StorageOperationError:
            get_logger().warning("storage_cleanup_failed", asset_id=str(asset_id))
        raise
    return AssetResponse.model_validate(asset)


@router.get("/{asset_id}", response_model=AssetResponse)
async def asset_metadata(asset_id: UUID, session: DatabaseSessionDependency) -> AssetResponse:
    return AssetResponse.model_validate(await get_asset(asset_id, session))


@router.get("/{asset_id}/download", response_class=Response)
async def download_asset(
    asset_id: UUID,
    session: DatabaseSessionDependency,
    storage: StorageDependency,
) -> Response:
    asset = await get_asset(asset_id, session)
    try:
        stored_object = await storage.download(asset.object_key)
    except StorageOperationError as error:
        raise storage_unavailable() from error
    encoded_filename = quote(asset.filename, safe="")
    return Response(
        content=stored_object.body,
        media_type=asset.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )


@router.get("/{asset_id}/presigned-url", response_model=PresignedUrlResponse)
async def presigned_download_url(
    asset_id: UUID,
    settings: SettingsDependency,
    session: DatabaseSessionDependency,
    storage: StorageDependency,
) -> PresignedUrlResponse:
    asset = await get_asset(asset_id, session)
    expires_in = settings.storage_presigned_expiry_seconds
    try:
        url = await storage.create_presigned_download_url(asset.object_key, expires_in)
    except StorageOperationError as error:
        raise storage_unavailable() from error
    return PresignedUrlResponse(url=url, expires_in=expires_in)
