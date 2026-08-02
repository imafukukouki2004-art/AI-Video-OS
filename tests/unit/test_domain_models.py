"""Unit tests for core domain models."""

from uuid import uuid4

from apps.api.domain.models import Job, JobStatus, Project, ProjectStatus, Video, Workflow


def test_project_instantiation() -> None:
    project = Project(name="Test Project", status=ProjectStatus.DRAFT)
    assert project.name == "Test Project"
    assert project.status == ProjectStatus.DRAFT


def test_video_instantiation() -> None:
    project_id = uuid4()
    video = Video(project_id=project_id, title="Test Video")
    assert video.project_id == project_id
    assert video.title == "Test Video"


def test_workflow_instantiation() -> None:
    project_id = uuid4()
    workflow = Workflow(project_id=project_id, workflow_type="short-form", config={"key": "value"})
    assert workflow.project_id == project_id
    assert workflow.workflow_type == "short-form"
    assert workflow.config == {"key": "value"}


def test_job_instantiation() -> None:
    workflow_id = uuid4()
    job = Job(workflow_id=workflow_id, name="Transcription", status=JobStatus.PENDING)
    assert job.workflow_id == workflow_id
    assert job.name == "Transcription"
    assert job.status == JobStatus.PENDING
