"""S3-compatible object storage foundation."""

from apps.api.storage.adapter import ObjectStorage, S3ObjectStorage, StoredObject
from apps.api.storage.errors import StorageOperationError

__all__ = ["ObjectStorage", "S3ObjectStorage", "StorageOperationError", "StoredObject"]
