"""Integration tests for the core domain API."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.application import create_app
from apps.api.config import Settings
from apps.api.dependencies import get_database_session
from apps.api.domain.models import Project, ProjectStatus


@pytest.fixture
def session() -> AsyncSession:
    session = AsyncMock(spec=AsyncSession)

    def mock_add(obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid4()
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.now(UTC)
        if hasattr(obj, "updated_at") and (
            not hasattr(obj, "updated_at") or obj.updated_at is None
        ):
            obj.updated_at = datetime.now(UTC)

    session.add = Mock(side_effect=mock_add)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def app(session: AsyncSession) -> FastAPI:
    app = create_app(
        Settings(
            app_env="test",
            log_level="CRITICAL",
            _env_file=None,
        )
    )

    async def provide_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_database_session] = provide_session
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_project_lifecycle(client: AsyncClient, session: AsyncMock):
    # 1. Create Project
    response = await client.post("/projects", json={"name": "Test Project"})
    assert response.status_code == status.HTTP_201_CREATED
    project_data = response.json()
    assert project_data["name"] == "Test Project"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()

    # 2. Get Project
    project = Project(name="Test Project", status=ProjectStatus.DRAFT)
    project.id = uuid4()
    project.created_at = datetime.now(UTC)
    project.updated_at = datetime.now(UTC)
    result = Mock()
    result.scalar_one_or_none.return_value = project
    session.execute.return_value = result

    response = await client.get(f"/projects/{project.id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "Test Project"


@pytest.mark.asyncio
async def test_video_creation(client: AsyncClient, session: AsyncMock):
    response = await client.post(
        "/videos", json={"project_id": str(uuid4()), "title": "Test Video"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["title"] == "Test Video"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_workflow_and_job_lifecycle(client: AsyncClient, session: AsyncMock):
    # 1. Create Workflow
    response = await client.post(
        "/workflows",
        json={
            "project_id": str(uuid4()),
            "workflow_type": "short-form",
            "config": {"model": "gpt-4"},
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["workflow_type"] == "short-form"

    # 2. Create Job
    response = await client.post(
        "/jobs",
        json={
            "workflow_id": str(uuid4()),
            "name": "Transcription",
            "input_data": {"audio_url": "http://example.com/audio.mp3"},
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == "Transcription"
