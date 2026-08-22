"""S3-compatible object storage adapter."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import ParamSpec, Protocol, TypeVar

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from apps.api.config import Settings
from apps.api.logging import get_logger
from apps.api.storage.errors import StorageOperationError

P = ParamSpec("P")
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Downloaded object bytes and response metadata."""

    body: bytes
    content_type: str


class ObjectStorage(Protocol):
    """Provider-neutral operations required by the asset API."""

    async def ensure_bucket(self) -> None: ...

    async def check_connection(self) -> bool: ...

    async def upload(self, key: str, body: bytes, content_type: str) -> None: ...

    async def download(self, key: str) -> StoredObject: ...

    async def delete(self, key: str) -> None: ...

    async def create_presigned_download_url(self, key: str, expires_in: int) -> str: ...

    async def close(self) -> None: ...


class S3ObjectStorage:
    """Hide boto3 and MinIO-specific connection details behind an async boundary."""

    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.storage_bucket
        self.region = settings.storage_region
        self._client: BaseClient = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url,
            aws_access_key_id=settings.storage_access_key.get_secret_value(),
            aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
            region_name=settings.storage_region,
            config=Config(
                connect_timeout=settings.storage_connect_timeout_seconds,
                read_timeout=settings.storage_read_timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
                s3={"addressing_style": settings.storage_addressing_style},
                signature_version="s3v4",
            ),
        )

    async def ensure_bucket(self) -> None:
        """Create the configured bucket when it does not already exist."""

        def ensure() -> None:
            try:
                self._client.head_bucket(Bucket=self.bucket)
            except ClientError as error:
                status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if status_code != 404:
                    raise
                parameters: dict[str, object] = {"Bucket": self.bucket}
                if self.region != "us-east-1":
                    parameters["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
                self._client.create_bucket(**parameters)

        await self._run(ensure)

    async def check_connection(self) -> bool:
        """Return whether the configured bucket is reachable."""

        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self.bucket)
        except (BotoCoreError, ClientError) as error:
            get_logger().warning("storage_connection_failed", error_type=type(error).__name__)
            return False
        return True

    async def upload(self, key: str, body: bytes, content_type: str) -> None:
        await self._run(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    async def download(self, key: str) -> StoredObject:
        def get() -> StoredObject:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            stream = response["Body"]
            try:
                body = stream.read()
            finally:
                stream.close()
            return StoredObject(
                body=body,
                content_type=str(response.get("ContentType", "application/octet-stream")),
            )

        return await self._run(get)

    async def delete(self, key: str) -> None:
        await self._run(self._client.delete_object, Bucket=self.bucket, Key=key)

    async def create_presigned_download_url(self, key: str, expires_in: int) -> str:
        def generate() -> str:
            return str(
                self._client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=expires_in,
                )
            )

        return await self._run(generate)

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)

    async def _run(self, operation: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await asyncio.to_thread(operation, *args, **kwargs)
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError from error
