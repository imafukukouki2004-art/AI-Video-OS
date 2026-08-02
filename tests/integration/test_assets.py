"""Asset API foundation integration tests."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.application import create_app
from apps.api.assets.models import Asset
from apps.api.cache import RedisManager
from apps.api.config import Settings
from apps.api.database import Database
from apps.api.dependencies import get_database_session
from apps.api.storage import ObjectStorage, StoredObject


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, StoredObject] = {}

    async def ensure_bucket(self) -> None: ...

    async def check_connection(self) -> bool:
        return True

    async def upload(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = StoredObject(body=body, content_type=content_type)

    async def download(self, key: str) -> StoredObject:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def create_presigned_download_url(self, key: str, expires_in: int) -> str:
        return f"http://storage.local/{key}?expires={expires_in}"

    async def close(self) -> None: ...


def make_app(
    session: AsyncSession,
    storage: FakeStorage,
    *,
    max_upload_bytes: int = 1024,
) -> FastAPI:
    database = Mock(spec=Database)
    database.dispose = AsyncMock()
    redis = Mock(spec=RedisManager)
    redis.close = AsyncMock()
    app = create_app(
        Settings(
            app_env="test",
            log_level="CRITICAL",
            storage_max_upload_bytes=max_upload_bytes,
            _env_file=None,
        ),
        database=cast(Database, database),
        redis=cast(RedisManager, redis),
        storage=cast(ObjectStorage, storage),
    )

    async def provide_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_database_session] = provide_session
    return app


def make_session() -> AsyncSession:
    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()
    return cast(AsyncSession, session)


def make_asset() -> Asset:
    asset_id = uuid4()
    return Asset(
        id=asset_id,
        object_key=f"assets/{asset_id}/clip.mp4",
        filename="clip.mp4",
        content_type="video/mp4",
        size_bytes=5,
        created_at=datetime.now(UTC),
    )


def session_returning(asset: Asset | None) -> AsyncSession:
    session = make_session()
    result = Mock()
    result.scalar_one_or_none.return_value = asset
    session.execute = AsyncMock(return_value=result)
    return session


def test_upload_stores_safe_object_and_metadata() -> None:
    storage = FakeStorage()
    session = make_session()
    with TestClient(make_app(session, storage)) as client:
        response = client.post(
            "/assets",
            files={"file": ("../../unsafe clip.mp4", b"video", "video/mp4")},
        )

    assert response.status_code == 201
    assert response.json()["filename"] == "unsafe-clip.mp4"
    assert response.json()["size_bytes"] == 5
    assert len(storage.objects) == 1
    object_key = next(iter(storage.objects))
    assert ".." not in object_key
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


def test_upload_rejects_unsupported_or_oversized_content() -> None:
    storage = FakeStorage()
    session = make_session()
    with TestClient(make_app(session, storage, max_upload_bytes=4)) as client:
        unsupported = client.post(
            "/assets",
            files={"file": ("asset.txt", b"text", "text/plain")},
        )
        oversized = client.post(
            "/assets",
            files={"file": ("clip.mp4", b"video", "video/mp4")},
        )

    assert unsupported.status_code == 415
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_ASSET_TYPE"
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "ASSET_TOO_LARGE"
    assert storage.objects == {}


def test_metadata_download_and_presigned_url() -> None:
    asset = make_asset()
    storage = FakeStorage()
    storage.objects[asset.object_key] = StoredObject(body=b"video", content_type="video/mp4")
    session = session_returning(asset)
    with TestClient(make_app(session, storage)) as client:
        metadata = client.get(f"/assets/{asset.id}")
        download = client.get(f"/assets/{asset.id}/download")
        presigned = client.get(f"/assets/{asset.id}/presigned-url")

    assert metadata.status_code == 200
    assert metadata.json()["id"] == str(asset.id)
    assert download.status_code == 200
    assert download.content == b"video"
    assert download.headers["content-disposition"].endswith("clip.mp4")
    assert presigned.status_code == 200
    assert presigned.json()["expires_in"] == 900
    assert "assets/" in presigned.json()["url"]


def test_missing_asset_uses_safe_error_contract() -> None:
    with TestClient(make_app(session_returning(None), FakeStorage())) as client:
        response = client.get(f"/assets/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ASSET_NOT_FOUND"
