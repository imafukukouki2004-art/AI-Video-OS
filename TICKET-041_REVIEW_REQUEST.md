# TICKET-041 Modernization Review Request

**Status:** Draft modernization; Production E2E execution not authorized

## Scope

PR #75 is being modernized against the latest `main`, including the merged GPT Image 2
default. This phase is limited to code compatibility, external-call-free regression tests,
and CI verification.

## Current Safety Decision

- Production E2E execution: **NO-GO until separate CEO approval**
- PR merge: **NO-GO during modernization**
- Ready-for-review transition: **not authorized**
- `AI_VIDEO_OS_RUN_PRODUCTION_E2E`: default **false**
- YouTube validation privacy: hard-coded **private** at the provider boundary

## Modernized Contracts

- The runner uses the current `AutomaticPublishingCoordinator` dependency contract.
- `PublishingQueueService` receives `PublicationRepository`.
- `PromptBuilder` is created without a session argument.
- Storage uses `S3ObjectStorage` and the current `Settings` contract.
- Workflow configuration uses top-level `auto_publish: true` and `provider: youtube`.
- An explicit existing Project ID is required; the validation runner never creates a Project.
- Unexpected exception details are excluded from reports and logs.

## Evidence

The authoritative Head SHA, latest CI run, results, remaining Production prerequisites, and
final preflight recommendation are recorded in the PR #75 conversation after the latest Head
finishes CI. Older CI runs are not modernization evidence.
