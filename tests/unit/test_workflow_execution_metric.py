from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.domain.models import WorkflowExecutionMetric
from apps.api.domain.schemas import WorkflowExecutionMetricCreate
from apps.api.repositories.sqlalchemy import WorkflowExecutionMetricRepository


@pytest.fixture
def session():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_workflow_execution_metric_entity():
    execution_id = uuid4()
    metric = WorkflowExecutionMetric(
        workflow_execution_id=execution_id,
        metric_type="duration_ms",
        metric_value=123.45
    )
    assert metric.workflow_execution_id == execution_id
    assert metric.metric_type == "duration_ms"
    assert metric.metric_value == 123.45

@pytest.mark.asyncio
async def test_workflow_execution_metric_repository_create(session: AsyncMock):
    repo = WorkflowExecutionMetricRepository(session)
    execution_id = uuid4()
    
    metric_in = WorkflowExecutionMetricCreate(
        workflow_execution_id=execution_id,
        metric_type="step_count",
        metric_value=5.0
    )
    
    def mock_refresh(obj):
        obj.id = uuid4()
        
    session.refresh.side_effect = mock_refresh
    metric = await repo.create(metric_in)
    
    assert metric.metric_type == "step_count"
    assert metric.metric_value == 5.0
    assert metric.id is not None
    session.add.assert_called_once()
    session.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_workflow_execution_metric_repository_list(session: AsyncMock):
    repo = WorkflowExecutionMetricRepository(session)
    execution_id = uuid4()
    mock_metrics = [
        WorkflowExecutionMetric(
            workflow_execution_id=execution_id, metric_type="m1", metric_value=1.0
        ),
        WorkflowExecutionMetric(
            workflow_execution_id=execution_id, metric_type="m2", metric_value=2.0
        ),
    ]
    
    result = Mock()
    result.scalars.return_value.all.return_value = mock_metrics
    session.execute.return_value = result
    
    metrics = await repo.list_by_execution(execution_id)
    assert len(metrics) == 2
    assert metrics[0].metric_type == "m1"
    assert metrics[1].metric_type == "m2"
