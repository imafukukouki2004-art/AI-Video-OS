# AI Video Runtime MVP

TICKET-035 validates the existing runtime foundations as one production execution path. It does
not introduce another runtime: synchronous API execution and queued Celery execution both reach
the same `WorkflowRuntime` orchestration.

## Execution path

```text
POST /workflows/{workflow_id}/enqueue
    -> WorkflowExecution (pending)
    -> Celery queue
    -> execute_workflow_execution worker
    -> WorkflowRuntime
    -> text_generation / PromptBuilder
    -> WorkflowContext
    -> image_generation / ObjectStorage / Asset / WorkflowArtifact
    -> WorkflowContext
    -> video_render / VideoRenderer / ObjectStorage / Asset / WorkflowArtifact
    -> WorkflowContext
    -> WorkflowExecution (completed)
```

The API and Worker construct the same provider, renderer, storage, repository, and prompt-builder
boundaries. Runtime coordinates them and retains the lifecycle, error, history, and metrics behavior
established by the earlier foundation tickets.

## Sample workflow

Create the Workflow with `POST /workflows`, then persist each definition below with
`POST /workflow-steps`. The values match the current WorkflowStep schema exactly; UUIDs are
examples and must refer to the created Workflow.

```json
[
  {
    "workflow_id": "11111111-1111-1111-1111-111111111111",
    "name": "GenerateScript",
    "step_type": "ai",
    "order": 1,
    "config": {
      "provider": "mock",
      "operation": "text_generation",
      "system_prompt": "Write concise social video scripts.",
      "prompt": "Create a three-scene launch script."
    }
  },
  {
    "workflow_id": "11111111-1111-1111-1111-111111111111",
    "name": "GenerateImage",
    "step_type": "ai",
    "order": 2,
    "config": {
      "provider": "mock",
      "operation": "image_generation",
      "prompt": "Create the hero frame for {{GenerateScript.output}}"
    }
  },
  {
    "workflow_id": "11111111-1111-1111-1111-111111111111",
    "name": "RenderVideo",
    "step_type": "render",
    "order": 3,
    "config": {
      "operation": "video_render",
      "input_asset": "{{GenerateImage.asset}}",
      "duration": 3,
      "fps": 30,
      "width": 1280,
      "height": 720
    }
  }
]
```

Use `provider: openai` only when explicitly running with a configured secret. Automated tests and
normal CI use the deterministic Mock provider and never call an external OpenAI API.

## Context and persistence chain

The script is published as `{{GenerateScript.output}}`. Image generation publishes
`{{GenerateImage.image}}`, `{{GenerateImage.asset}}`, and `{{GenerateImage.artifact}}` only after
the image is stored and both persistence records succeed. Video rendering consumes the image Asset
ID and publishes:

- `{{RenderVideo.video}}` — presigned MP4 reference
- `{{RenderVideo.asset}}` — final video Asset ID
- `{{RenderVideo.artifact}}` — final video WorkflowArtifact ID
- `{{RenderVideo.output}}` — structured final step result

The WorkflowArtifact owns the relationship between WorkflowExecution, WorkflowStep, and Asset.
This makes final output traceable without expanding Asset responsibility.

## Enqueue and result tracking

Start the persisted Workflow through:

```http
POST /workflows/{workflow_id}/enqueue
```

The response supplies the WorkflowExecution ID and queue task ID. Track lifecycle and observability
through the existing execution endpoints:

```text
GET /workflow-executions/{execution_id}
GET /workflow-executions/{execution_id}/history
GET /workflow-executions/{execution_id}/errors
GET /workflow-executions/{execution_id}/metrics
GET /workflow-executions/{execution_id}/artifacts
```

The last endpoint returns the ordered image and video WorkflowArtifacts. The final artifact with
`artifact_type: video` supplies both the final WorkflowArtifact ID and Video Asset ID; Asset metadata
and download endpoints then resolve the stored MP4.

## Lifecycle and failure contract

Successful executions transition `pending -> running -> completed`. Each required Job transitions
`pending -> running -> completed`, with two history records per step and terminal execution metrics.

On any step failure, the active Job and WorkflowExecution become failed, a
WorkflowExecutionError and failure History are recorded, terminal Metrics are emitted, and the next
step is not executed. A failing operation never publishes its incomplete Context values. Outputs
from fully completed earlier steps remain valid.

## Runtime MVP boundary

The Runtime MVP ends with a stored, traceable MP4. Social publishing, scheduling, approval/editor
UI, audio/TTS/music, subtitles, timelines, advanced transitions, text-to-video providers, GPU or
parallel execution, failover/retry redesign, billing, analytics, and deployment redesign remain
outside TICKET-035.
