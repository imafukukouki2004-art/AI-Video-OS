# AI Video OS

AI Video OS is an implementation project for producing short-form social video through a traceable, human-approved AI workflow.

The Runtime MVP can generate text, create and store an image, render and store a video, and trace
the final Asset and WorkflowArtifact. Publishing is a separate bounded domain so future platform
adapters do not become WorkflowRuntime responsibilities.

## Current Project State

| Field | Value |
| --- | --- |
| Product version | AI Video OS Version 2.0 |
| Phase | M4 — Publishing & Distribution |
| Current milestone | Publishing Foundation |
| Completed | TICKET-001 through TICKET-035; Runtime MVP completed |
| Current ticket | TICKET-036 — Publishing Domain & Provider Foundation (In Review) |
| Implementation progress | Runtime MVP completed; Publishing Foundation in review |
| Next technology review | TR-02 after M4 completion |
| Technology review status | Pending |

See [Project State](docs/operations/PROJECT_STATE.md) for the operational record.

## Implemented Backend Foundation

- FastAPI application factory with lifespan startup and shutdown handling
- Pydantic Settings configuration from environment variables and `.env`
- `GET /health` and `GET /ready`
- OpenAPI JSON and interactive API documentation
- Common application, validation, HTTP, and unexpected error responses
- Safe `X-Request-ID` propagation or generation
- JSON structured application and request logging
- pytest, coverage, Ruff, and mypy configuration
- Python 3.12 non-root Docker image

## Implemented Frontend Foundation

- Next.js App Router with strict TypeScript
- Tailwind CSS and a responsive root layout
- Server-side FastAPI health client using `API_BASE_URL`
- Backend operational and unavailable states
- Minimal App Router error boundary
- ESLint, Vitest, and Playwright foundation
- Next.js standalone non-root Docker image

## Implemented PostgreSQL Foundation

- PostgreSQL 17 Compose service with health check and persistent volume
- SQLAlchemy 2.x async engine using psycopg
- Request-scoped `AsyncSession` dependency
- Alembic configuration and empty initial baseline revision
- Database-aware `GET /ready` response
- Secret-safe database settings and connectivity logging

## Implemented Redis and Celery Foundation

- Redis 7.4 Compose service with health check and persistent AOF volume
- Async Redis client with secret-safe connectivity logging
- Database- and Redis-aware `GET /ready` response
- Celery application using Redis broker and result backend
- JSON-only task serialization and worker reliability defaults
- Retry/backoff/jitter-enabled foundation test task
- Non-root Celery worker image and Compose worker health check

## Implemented Object Storage Foundation

- MinIO service, health check, persistent volume, and idempotent bucket initializer
- Provider-neutral asynchronous Object Storage Adapter over boto3
- Storage-aware `GET /ready` response
- Asset metadata model and Alembic migration
- Validated asset upload and metadata APIs
- Asset download and expiring presigned URL APIs
- Safe object keys, bounded uploads, and secret-safe provider error handling

## CI Foundation

GitHub Actions runs independent Python and Frontend quality jobs for pull requests targeting
`main` and pushes to `main`.

- Python: Ruff lint and format checks, mypy, pytest, and a 90% coverage gate
- Frontend: ESLint, Vitest, TypeScript, and the Next.js production build
- Python 3.12 and Node.js 22 with pinned pnpm 11.9.0
- pip and pnpm dependency caches keyed by their dependency definitions
- Read-only repository permissions and cancellation of superseded runs on the same ref

The workflow performs continuous integration only. It does not publish images, deploy services,
or access production environments.

## Prerequisites

- Python 3.12
- Node.js 22 or later
- pnpm 11
- Docker (optional, for the container workflow)

## Local Development

Create a virtual environment, install the runtime and development dependencies, and create a local environment file:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
```

The supported settings are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `ai-video-os-api` | Service name used by API responses and logs |
| `APP_ENV` | `development` | `development`, `test`, or `production` |
| `APP_VERSION` | `0.1.0` | Application metadata version |
| `APP_HOST` | `0.0.0.0` | Local bind host |
| `APP_PORT` | `8000` | Local bind port |
| `APP_DEBUG` | `false` | FastAPI debug mode |
| `LOG_LEVEL` | `INFO` | Structured logging threshold |
| `LOG_FORMAT` | `json` | `json` or local `console` output |
| `DATABASE_URL` | local PostgreSQL URL | SQLAlchemy psycopg connection URL (secret) |
| `DATABASE_POOL_SIZE` | `5` | Persistent connection pool size |
| `DATABASE_MAX_OVERFLOW` | `10` | Additional temporary connections |
| `DATABASE_POOL_TIMEOUT_SECONDS` | `5` | Pool checkout timeout |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | `3` | PostgreSQL connection timeout |
| `REDIS_URL` | local Redis URL | API Redis connection URL (secret) |
| `REDIS_CONNECT_TIMEOUT_SECONDS` | `3` | Redis connection timeout |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | `3` | Redis operation timeout |
| `CELERY_BROKER_URL` | local Redis DB 0 | Celery broker URL (secret) |
| `CELERY_RESULT_BACKEND` | local Redis DB 1 | Celery result backend URL (secret) |
| `CELERY_TASK_MAX_RETRIES` | `3` | Foundation task retry limit |
| `CELERY_RETRY_BACKOFF_MAX_SECONDS` | `60` | Maximum automatic retry backoff |
| `STORAGE_ENDPOINT_URL` | `http://127.0.0.1:9000` | S3-compatible endpoint |
| `STORAGE_ACCESS_KEY` | local placeholder | S3 access key (secret) |
| `STORAGE_SECRET_KEY` | local placeholder | S3 secret key (secret) |
| `STORAGE_BUCKET` | `ai-video-os-assets` | Asset bucket name |
| `STORAGE_REGION` | `us-east-1` | S3 signing and bucket region |
| `STORAGE_MAX_UPLOAD_BYTES` | `26214400` | Maximum accepted upload size |
| `STORAGE_PRESIGNED_EXPIRY_SECONDS` | `900` | Presigned download lifetime |
| `STORAGE_CONNECT_TIMEOUT_SECONDS` | `3` | S3 connection timeout |
| `STORAGE_READ_TIMEOUT_SECONDS` | `10` | S3 operation timeout |

Do not store secrets in `.env.example`, source files, images, or logs.
Replace the MinIO credential placeholders in the local `.env` before starting Compose.

### Start the backend

Start PostgreSQL, Redis, and MinIO, initialize the bucket, then apply migrations:

```bash
docker compose up -d postgres redis minio
docker compose run --rm minio-init
alembic upgrade head
```

Then start the API:

```bash
uvicorn apps.api.main:app --reload --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
```

Verify the service:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

`/health` reports process liveness. `/ready` returns HTTP 200 only when application startup is complete and PostgreSQL, Redis, and object storage accept checks; otherwise it returns HTTP 503.

### Asset API foundation

```bash
curl -F "file=@sample.mp4;type=video/mp4" http://localhost:8000/assets
curl http://localhost:8000/assets/{asset_id}
curl -OJ http://localhost:8000/assets/{asset_id}/download
curl http://localhost:8000/assets/{asset_id}/presigned-url
```

Uploads accept audio, image, or video content up to the configured size. Object keys are generated by the service; filenames cannot control bucket paths. Presigned URLs expire after the configured lifetime.

### Start the Celery worker

Locally:

```bash
celery -A apps.worker.celery_app:celery_app worker --loglevel=INFO
```

Or with Compose after Redis becomes healthy:

```bash
docker compose up -d celery-worker
```

The registered `apps.worker.tasks.foundation_test` task exists only to validate worker wiring and retry behavior. It contains no product workflow or business logic.

- API documentation: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

### Start the frontend

In another terminal:

```bash
cd apps/web
cp .env.local.example .env.local
pnpm install --frozen-lockfile
pnpm dev
```

Open <http://localhost:3000>. The page fetches the backend `GET /health` endpoint and displays its current state. `API_BASE_URL` is server-only and defaults to `http://127.0.0.1:8000`.

## Verification

Backend:

```bash
pytest
pytest --cov=apps.api --cov-report=term-missing
ruff check .
ruff format --check .
mypy apps/api
mypy apps/worker
alembic upgrade head --sql
python -c "from apps.worker.celery_app import celery_app; print(celery_app.main)"
```

Frontend:

```bash
cd apps/web
pnpm run lint
pnpm run test
pnpm run typecheck
pnpm run build
```

Playwright configuration is present for later end-to-end scenarios; TICKET-003 does not add product E2E flows or browser binaries.

### Prompt composition

Workflow text and image steps support runtime variable resolution in `prompt`, plus an optional
`system_prompt` for text generation. Prompt roles are represented by typed value models and are
composed before the existing provider interface is called. See
[Prompt Composition Foundation](docs/architecture/PROMPT_COMPOSITION.md) for the configuration
contract, supported variables, and explicit scope boundaries.

### Multi-step AI pipelines

The Workflow Runtime supports ordered AI pipelines such as text generation → text rewrite →
image generation. Completed results move between steps only through `WorkflowContext` and the
existing variable references; API and Celery worker execution share the same runtime path. See
[Multi-Step AI Pipeline Foundation](docs/architecture/MULTI_STEP_AI_PIPELINE.md) for execution,
failure, observability, and scope contracts.

### Video rendering

Workflow steps with `operation: video_render` can resolve a stored image Asset, render a
fixed-duration H.264 MP4 through the FFmpeg adapter, and register the result as an Asset and
WorkflowArtifact. Successful steps publish `video`, `asset`, and `artifact` Context references;
failed renders publish none. See [Video Rendering Foundation](docs/architecture/VIDEO_RENDERING.md)
for the step contract, registration order, temporary-file strategy, and FFmpeg setup.

### Runtime MVP

The production execution path can enqueue a persisted Workflow and run Text → Image → Video in
one Celery worker execution. Final image and video artifacts remain traceable from the
WorkflowExecution, while Context references connect each completed step. See
[AI Video Runtime MVP](docs/architecture/RUNTIME_MVP.md) for the exact WorkflowStep definitions,
enqueue flow, result-tracking endpoints, lifecycle contract, and scope boundary.

### Publishing foundation

An existing Video Asset can be registered as a Publication, executed through the provider-neutral
PublishingProvider contract, and tracked from `pending` through `published` or `failed`. TICKET-036
includes only a deterministic Mock provider; it performs no external social API communication.

```bash
curl -X POST http://localhost:8000/publications \
  -H 'Content-Type: application/json' \
  -d '{"asset_id":"<video-asset-uuid>","provider":"mock","title":"Launch video"}'
curl http://localhost:8000/publications/{publication_id}
curl http://localhost:8000/assets/{asset_id}/publications
curl -X POST http://localhost:8000/publications/{publication_id}/publish
```

See [Publishing Foundation](docs/architecture/PUBLISHING.md) for the domain boundary, provider
contract, lifecycle, security rules, and explicit scope exclusions.

## Docker

Build from the repository root:

```bash
docker build -f apps/api/Dockerfile -t ai-video-os-api .
```

Run the image:

```bash
docker run --rm -p 8000:8000 --env-file .env ai-video-os-api
```

The image runs as a non-root user, listens on `0.0.0.0:8000`, and includes a `/health` container health check.

Build and run the frontend image:

```bash
docker build -f apps/web/Dockerfile -t ai-video-os-web .
docker run --rm -p 3000:3000 --env API_BASE_URL=http://host.docker.internal:8000 ai-video-os-web
```

## Repository Structure

```text
apps/api/                 FastAPI application, infrastructure adapters, asset API, and container definition
apps/web/                 Next.js application, tests, and container definition
apps/worker/              Celery application, foundation task, and worker image
docs/operations/          Current operational project state
docs/architecture/        Runtime architecture contracts
migrations/               Alembic environment, baseline, and asset metadata revisions
tests/unit/               Isolated configuration and logging tests
tests/integration/        HTTP API and error-contract tests
packages/                 Reserved for later ticket-owned shared packages
infrastructure/           Reserved for later infrastructure tickets
compose.yaml              PostgreSQL, Redis, Celery worker, and MinIO services
.github/workflows/ci.yml  Python and Frontend continuous integration quality gates
```

## Current Implementation Boundaries

TICKET-007 does not implement continuous deployment, container publishing, Kubernetes, production deployment, providers, domain logic, or the Workflow Runtime.

## Security Rules

1. Never commit `.env`, API keys, access tokens, passwords, signing secrets, or private keys.
2. Log only approved operational metadata; never log authorization headers, request bodies, secrets, or personal information.
3. Return stable public error messages and keep internal exception details out of responses.
4. Do not bypass security controls to accelerate a feature ticket.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
