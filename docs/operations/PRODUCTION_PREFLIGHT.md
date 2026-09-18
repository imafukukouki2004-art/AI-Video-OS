# TICKET-043 — Production Preflight and Controlled E2E Gate

## Purpose

Determine whether the current `main` lineage is ready for one separately approved Controlled Production E2E without using OpenAI generation or YouTube publishing during preflight.

Historical Production E2E evidence and current verification are separate concepts. A historical run never makes the current revision `VERIFIED`.

## Preflight layers

### A — configuration only

The default validator performs no network access and verifies secret presence without printing values, production environment mode, Railway storage addressing, YouTube privacy fixed to `private`, and that `AI_VIDEO_OS_RUN_PRODUCTION_E2E` remains disabled.

### B — safe live infrastructure

`--live` is allowed before Production API approval because it does not execute a Workflow, OpenAI generation, OAuth authorization, or YouTube upload. It verifies:

- API health/readiness when an API URL is explicitly supplied
- PostgreSQL connectivity
- Alembic revision at repository head
- Production E2E Project UUID exists
- Redis connectivity
- Celery Worker can execute a secret-free preflight task
- FFmpeg is executable on the Worker
- Storage bucket connectivity
- optional temporary-key storage upload/read/presigned/delete probe
- active encrypted YouTube OAuth credential can be decrypted locally

The report never prints database URLs, Redis URLs, API keys, OAuth tokens, encryption keys, presigned URLs, or raw provider exceptions.

### C — deliberately not checkable before approval

Preflight must report these as `NOT_CHECKABLE`, not as false READY claims:

- OpenAI production generation authorization/quota/billing and actual text generation
- GPT Image production generation authorization/quota/billing and actual image generation
- YouTube refresh-token validity against Google and actual upload authorization
- YouTube private upload result

Those are verified only by the Controlled Production E2E.

## Preflight READY gate

Preflight is READY for CEO approval when:

1. all A checks are PASS/CONFIGURED and the Production E2E opt-in remains disabled;
2. all requested B checks PASS;
3. the only unresolved results are explicitly `NOT_CHECKABLE` items assigned to Controlled Production E2E;
4. `YOUTUBE_PRIVACY_STATUS=private`;
5. an existing Production Project is selected;
6. no Production generation or publishing API has been invoked.

## Controlled Production E2E approval boundary

Do not set `AI_VIDEO_OS_RUN_PRODUCTION_E2E=true` and do not run `scripts/production_e2e_validation.py` until the CEO/user gives explicit approval immediately before execution.

Once approved, execute exactly one controlled validation against the reviewed revision:

Workflow Start
→ real OpenAI text
→ real GPT Image
→ video render
→ Asset / Artifact persistence
→ Storage
→ Publication creation
→ Queue / Worker
→ YouTube API
→ PRIVATE upload
→ Publication PUBLISHED
→ YouTube video ID and canonical URL verification.

Public and unlisted validation uploads are prohibited.

## PRODUCTION E2E = VERIFIED

The current revision may be marked `PRODUCTION E2E = VERIFIED` only when one controlled run proves all of the following:

- the report identifies the tested git commit SHA;
- Workflow reaches COMPLETED;
- real OpenAI text generation succeeds;
- real GPT Image generation succeeds;
- generated image and video Assets/Artifacts persist and are retrievable;
- FFmpeg video is non-empty and passes the existing visual non-black validation;
- automatic Publication is created for the final video;
- Publication is queued and executed by the Worker path;
- YouTube provider returns success;
- returned/recorded privacy status is exactly `private`;
- Publication reaches `PUBLISHED`;
- non-empty YouTube video ID is persisted;
- canonical YouTube URL is persisted/confirmed;
- no duplicate Publication/upload is observed for the execution;
- no secret appears in logs or the validation evidence;
- a sanitized validation report is committed to the repository.

A historical run, a mock E2E, a successful OpenAI-only run, a successful YouTube-only smoke test, or a local PC history is insufficient.

## Evidence

After a successful controlled run, store a secret-free report under:

`docs/evidence/production-e2e/<UTC timestamp>-<short commit sha>.json`

The report should contain stable IDs and results only: tested commit SHA, timestamps, workflow/execution/asset/artifact/publication IDs, final statuses, model names, YouTube video ID/canonical URL, privacy status, visual validation result, and sanitized check results.

Never include prompts if they can contain sensitive input, API keys, refresh/access tokens, OAuth codes, client secrets, encryption keys, raw exception bodies, authorization headers, database/Redis URLs, or presigned URLs.
