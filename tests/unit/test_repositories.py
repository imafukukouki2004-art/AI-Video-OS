"""Unit tests for the repository layer."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.domain.models import Project, ProjectStatus
from apps.api.domain.schemas import ProjectCreate, ProjectUpdate
from apps.api.repositories.sqlalchemy import ProjectRepository


@pytest.fixture
def session() -> AsyncSession:
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_project_repository_create(session: AsyncMock):
    repo = ProjectRepository(session)
    project_in = ProjectCreate(name="Test Project")

    # Mock refresh to set ID
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
