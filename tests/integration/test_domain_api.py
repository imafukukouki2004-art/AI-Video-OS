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
from apps.api.domain.models import Job, JobStatus, Project, ProjectStatus, Video, Workflow


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

    # 3. Update Project
    response = await client.patch(f"/projects/{project.id}", json={"status": "processing"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "processing"

    # 4. Project Not Found
    result.scalar_one_or_none.return_value = None
    response = await client.get(f"/projects/{uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    # 5. Update Project Not Found
    response = await client.patch(f"/projects/{uuid4()}", json={"name": "New Name"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_video_lifecycle(client: AsyncClient, session: AsyncMock):
    # 1. Create Video
    response = await client.post(
        "/videos", json={"project_id": str(uuid4()), "title": "Test Video"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    video_data = response.json()
    assert video_data["title"] == "Test Video"

    # 2. Get Video
    video = Video(project_id=uuid4(), title="Test Video")
    video.id = uuid4()
    video.created_at = datetime.now(UTC)
    result = Mock()
    result.scalar_one_or_none.return_value = video
    session.execute.return_value = result

    response = await client.get(f"/videos/{video.id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "Test Video"

    # 3. Video Not Found
    result.scalar_one_or_none.return_value = None
    response = await client.get(f"/videos/{uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_workflow_lifecycle(client: AsyncClient, session: AsyncMock):
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

    # 2. Get Workflow
    workflow = Workflow(project_id=uuid4(), workflow_type="short-form")
    workflow.id = uuid4()
    workflow.created_at = datetime.now(UTC)
    workflow.config = {"model": "gpt-4"}
    result = Mock()
    result.scalar_one_or_none.return_value = workflow
    session.execute.return_value = result

    response = await client.get(f"/workflows/{workflow.id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["workflow_type"] == "short-form"

    # 3. Workflow Not Found
    result.scalar_one_or_none.return_value = None
    response = await client.get(f"/workflows/{uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_job_lifecycle(client: AsyncClient, session: AsyncMock):
    # 1. Create Job
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

    # 2. Get Job
    job = Job(workflow_id=uuid4(), name="Transcription")
    job.id = uuid4()
    job.created_at = datetime.now(UTC)
    job.status = JobStatus.PENDING
    job.input_data = {}
    job.output_data = {}
    result = Mock()
    result.scalar_one_or_none.return_value = job
    session.execute.return_value = result

    response = await client.get(f"/jobs/{job.id}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "Transcription"

    # 3. Job Not Found
    result.scalar_one_or_none.return_value = None
    response = await client.get(f"/jobs/{uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_validation_errors(client: AsyncClient):
    # Empty name for project
    response = await client.post("/projects", json={"name": ""})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Invalid UUID
    response = await client.get("/projects/not-a-uuid")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
