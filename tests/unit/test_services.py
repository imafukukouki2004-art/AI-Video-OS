"""Unit tests for the application service layer."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.domain.models import Project
from apps.api.domain.schemas import ProjectCreate
from apps.api.repositories.sqlalchemy import ProjectRepository
from apps.api.services.domain import ProjectService


@pytest.fixture
def repository() -> ProjectRepository:
    return AsyncMock(spec=ProjectRepository)


@pytest.mark.asyncio
async def test_project_service_create(repository: AsyncMock):
    service = ProjectService(repository)
    project_in = ProjectCreate(name="Test Project")
    mock_project = Project(id=uuid4(), name="Test Project")
    repository.create.return_value = mock_project

    project = await service.create(project_in)

    assert project.name == "Test Project"
    assert project.id == mock_project.id
    repository.create.assert_awaited_once_with(project_in)


@pytest.mark.asyncio
async def test_project_service_get_by_id(repository: AsyncMock):
    service = ProjectService(repository)
    project_id = uuid4()
    mock_project = Project(id=project_id, name="Found Project")
    repository.get_by_id.return_value = mock_project

    project = await service.get_by_id(project_id)

    assert project is not None
    assert project.id == project_id
    repository.get_by_id.assert_awaited_once_with(project_id)
