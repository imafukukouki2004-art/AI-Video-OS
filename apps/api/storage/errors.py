"""Internal object storage exceptions."""


class StorageOperationError(Exception):
    """Represent an S3 operation failure without exposing provider details."""
