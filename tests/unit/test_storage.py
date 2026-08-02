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
