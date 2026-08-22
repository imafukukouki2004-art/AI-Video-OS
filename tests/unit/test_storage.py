"""S3-compatible object storage adapter tests."""

from io import BytesIO
from typing import cast
from unittest.mock import Mock

import pytest
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from apps.api.config import Settings
from apps.api.storage import S3ObjectStorage, StoredObject


def make_storage() -> S3ObjectStorage:
    return S3ObjectStorage(
        Settings(
            app_env="test",
            storage_endpoint_url="http://storage:9000",
            storage_access_key="test-access",
            storage_secret_key="test-secret",  # noqa: S106 - isolated test credential
            storage_bucket="test-assets",
            _env_file=None,
        )
    )


def attach_client(storage: S3ObjectStorage) -> Mock:
    # boto3 adds service operations dynamically, so BaseClient cannot provide a strict spec.
    client = Mock()
    storage._client = cast(BaseClient, client)
    return client


def make_virtual_storage() -> S3ObjectStorage:
    return S3ObjectStorage(
        Settings(
            app_env="production",
            storage_endpoint_url="https://storage.railway.app",
            storage_access_key="test-access",
            storage_secret_key="test-secret",  # noqa: S106 - isolated test credential
            storage_bucket="railway-assets",
            storage_addressing_style="virtual",
            _env_file=None,
        )
    )


def test_storage_defaults_to_path_style_for_minio() -> None:
    storage = make_storage()

    assert storage._client.meta.config.s3["addressing_style"] == "path"


def test_storage_supports_virtual_style_for_railway_buckets() -> None:
    storage = make_virtual_storage()

    assert storage._client.meta.config.s3["addressing_style"] == "virtual"


@pytest.mark.asyncio
async def test_ensure_bucket_creates_missing_bucket() -> None:
    storage = make_storage()
    client = attach_client(storage)
    client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
        "HeadBucket",
    )

    await storage.ensure_bucket()

    client.create_bucket.assert_called_once_with(Bucket="test-assets")


@pytest.mark.asyncio
async def test_storage_health_check_is_safe() -> None:
    storage = make_storage()
    client = attach_client(storage)

    assert await storage.check_connection() is True

    client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "500"}, "ResponseMetadata": {"HTTPStatusCode": 500}},
        "HeadBucket",
    )
    assert await storage.check_connection() is False


@pytest.mark.asyncio
async def test_upload_download_delete_and_presigned_url() -> None:
    storage = make_storage()
    client = attach_client(storage)
    client.get_object.return_value = {
        "Body": BytesIO(b"asset-bytes"),
        "ContentType": "video/mp4",
    }
    client.generate_presigned_url.return_value = "http://storage/presigned"

    await storage.upload("assets/id/video.mp4", b"asset-bytes", "video/mp4")
    downloaded = await storage.download("assets/id/video.mp4")
    url = await storage.create_presigned_download_url("assets/id/video.mp4", 900)
    await storage.delete("assets/id/video.mp4")

    assert downloaded == StoredObject(body=b"asset-bytes", content_type="video/mp4")
    assert url == "http://storage/presigned"
    client.put_object.assert_called_once()
    client.delete_object.assert_called_once()


@pytest.mark.asyncio
async def test_virtual_style_storage_preserves_object_operation_contracts() -> None:
    storage = make_virtual_storage()
    client = attach_client(storage)
    client.get_object.return_value = {
        "Body": BytesIO(b"railway-asset"),
        "ContentType": "image/png",
    }
    client.generate_presigned_url.return_value = "https://bucket.storage.railway.app/object"

    await storage.upload("assets/id/image.png", b"railway-asset", "image/png")
    downloaded = await storage.download("assets/id/image.png")
    url = await storage.create_presigned_download_url("assets/id/image.png", 900)
    await storage.delete("assets/id/image.png")

    assert downloaded == StoredObject(body=b"railway-asset", content_type="image/png")
    assert url == "https://bucket.storage.railway.app/object"
    client.put_object.assert_called_once_with(
        Bucket="railway-assets",
        Key="assets/id/image.png",
        Body=b"railway-asset",
        ContentType="image/png",
    )
    client.get_object.assert_called_once_with(
        Bucket="railway-assets",
        Key="assets/id/image.png",
    )
    client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "railway-assets", "Key": "assets/id/image.png"},
        ExpiresIn=900,
    )
    client.delete_object.assert_called_once_with(
        Bucket="railway-assets",
        Key="assets/id/image.png",
    )
