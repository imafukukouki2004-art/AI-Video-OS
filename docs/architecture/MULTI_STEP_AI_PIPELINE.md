# Multi-Step AI Pipeline Foundation

TICKET-033 verifies and hardens the existing Workflow Runtime as the orchestration foundation
for practical sequential AI pipelines. It does not add a second pipeline engine or change the
provider interface.

## Execution flow

Each configured AI step follows the same runtime path:

```text
WorkflowStep
    -> WorkflowContext
    -> VariableResolver
    -> PromptBuilder
    -> AIProvider
    -> Job / Asset / WorkflowArtifact
```

The step repository supplies steps in their persisted `order`. A completed step publishes its
result to the execution-local `WorkflowContext`; the next step resolves that value while its
prompt is composed. Both API-triggered and Celery worker-triggered executions use the same
`WorkflowRuntime` and `PromptBuilder` implementation.

Example:

```json
[
  {
    "name": "GenerateScript",
    "config": {
      "provider": "mock",
      "operation": "text_generation",
      "prompt": "Generate a launch script"
    }
  },
  {
    "name": "RewriteScript",
    "config": {
      "provider": "mock",
      "operation": "text_generation",
      "prompt": "Rewrite: {{GenerateScript.output}}"
    }
  },
  {
    "name": "GenerateImage",
    "config": {
      "provider": "mock",
      "operation": "image_generation",
      "prompt": "Key visual for {{RewriteScript.output}}"
    }
  }
]
```

## Data handoff

The pipeline uses only the existing context references:

- `{{step.output}}` for completed step results
- `{{step.image}}` for stored image references
- `{{step.asset}}` for registered assets
- `{{step.artifact}}` for workflow artifacts

No additional expression language or cross-execution context store is introduced.

## Failure and observability contract

If a step fails, the runtime marks the active Job and WorkflowExecution as failed, records a
`WorkflowExecutionError` and history transition, emits the existing metrics, and returns without
selecting another step. The failed step publishes no output, and execution responses do not
expose the internal context. Previously completed persisted jobs and observability records remain
available for diagnosis.

Successful multi-step execution continues to record per-step Job and History state, final
Execution state, duration and count metrics, and image Asset / WorkflowArtifact records.

## Compatibility and boundaries

Sequential fallback, conditional branches, loops, queue/worker execution, text generation, image
generation, storage, and PromptBuilder behavior remain unchanged. This foundation does not add
parallel execution, a DAG engine, dynamic planning, agents, RAG, retries, provider failover,
rendering, scheduling, cost management, or UI behavior.
