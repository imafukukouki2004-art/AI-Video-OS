import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, Mock
from datetime import UTC, datetime
from fastapi import FastAPI
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.application import create_app
from apps.api.config import Settings
from apps.api.dependencies import get_database_session
from apps.api.domain.models import WorkflowExecutionMetric

@pytest.fixture
def session() -> AsyncSession:
    session = AsyncMock()
    def mock_add(obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid4()
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.now(UTC)
    session.add = Mock(side_effect=mock_add)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session

@pytest.fixture
def app(session) -> FastAPI:
    app = create_app(
        Settings(
            app_env="test",
            log_level="CRITICAL",
            _env_file=None,
        )
    )
    async def provide_session() -> AsyncIterator:
        yield session
    app.dependency_overrides[get_database_session] = provide_session
    return app

@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_get_execution_metrics_api(client: AsyncClient, session: AsyncMock):
    execution_id = uuid4()
    metric = WorkflowExecutionMetric(
        id=uuid4(),
        workflow_execution_id=execution_id,
        metric_type="duration_ms",
        metric_value=500.0,
        created_at=datetime.now(UTC)
    )
    
    result = Mock()
    result.scalars.return_value.all.return_value = [metric]
    session.execute.return_value = result
    
    response = await client.get(f"/workflow-executions/{execution_id}/metrics")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["metric_type"] == "duration_ms"
    assert data[0]["metric_value"] == 500.0

@pytest.mark.asyncio
async def test_get_execution_metrics_empty(client: AsyncClient, session: AsyncMock):
    execution_id = uuid4()
    result = Mock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    
    response = await client.get(f"/workflow-executions/{execution_id}/metrics")
    assert response.status_code == 200
    assert response.json() == []
