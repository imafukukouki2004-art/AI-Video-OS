"""Unit tests for the repository layer."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.domain.models import Job, Project, ProjectStatus, Video, Workflow
from apps.api.domain.schemas import (
    ProjectCreate,
    ProjectUpdate,
    VideoCreate,
)
from apps.api.repositories.sqlalchemy import (
    JobRepository,
    ProjectRepository,
    VideoRepository,
    WorkflowRepository,
)


@pytest.fixture
def session() -> AsyncSession:
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_project_repository_create(session: AsyncMock):
    repo = ProjectRepository(session)
    project_in = ProjectCreate(name="Test Project")

    def mock_refresh(obj):
        obj.id = uuid4()

    session.refresh.side_effect = mock_refresh
    project = await repo.create(project_in)

    assert project.name == "Test Project"
    assert project.id is not None
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_project_repository_get_by_id(session: AsyncMock):
    repo = ProjectRepository(session)
    project_id = uuid4()
    mock_project = Project(id=project_id, name="Found Project")

    result = Mock()
    result.scalar_one_or_none.return_value = mock_project
    session.execute.return_value = result

    project = await repo.get_by_id(project_id)

    assert project is not None
    assert project.id == project_id
    assert project.name == "Found Project"


@pytest.mark.asyncio
async def test_project_repository_list(session: AsyncMock):
    repo = ProjectRepository(session)
    mock_projects = [Project(name="P1"), Project(name="P2")]

    result = Mock()
    result.scalars.return_value.all.return_value = mock_projects
    session.execute.return_value = result

    projects = await repo.list()

    assert len(projects) == 2
    assert projects[0].name == "P1"
    assert projects[1].name == "P2"


@pytest.mark.asyncio
async def test_project_repository_update(session: AsyncMock):
    repo = ProjectRepository(session)
    project_id = uuid4()
    mock_project = Project(id=project_id, name="Old Name", status=ProjectStatus.DRAFT)

    result = Mock()
    result.scalar_one_or_none.return_value = mock_project
    session.execute.return_value = result

    update_in = ProjectUpdate(name="New Name", status=ProjectStatus.PROCESSING)
    updated_project = await repo.update(project_id, update_in)

    assert updated_project is not None
    assert updated_project.name == "New Name"
    assert updated_project.status == ProjectStatus.PROCESSING
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_other_repositories_smoke(session: AsyncMock):
    # Verify that other repositories correctly instantiate and use their models
    video_repo = VideoRepository(session)
    workflow_repo = WorkflowRepository(session)
    job_repo = JobRepository(session)

    assert video_repo.model == Video
    assert workflow_repo.model == Workflow
    assert job_repo.model == Job

    # Smoke test for create on VideoRepository
    video_in = VideoCreate(project_id=uuid4(), title="V1")
    await video_repo.create(video_in)
    session.add.assert_called()
    session.commit.assert_awaited()
