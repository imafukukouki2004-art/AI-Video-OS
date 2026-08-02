# AI Video OS

AI Video OS is an implementation project for producing short-form social video through a traceable, human-approved AI workflow.

TICKET-002 through TICKET-004 provide executable backend, frontend, and PostgreSQL foundations. Queue, storage, provider, domain, and workflow features remain intentionally out of scope.

## Current Project State

| Field | Value |
| --- | --- |
| Product version | AI Video OS Version 2.0 |
| Phase | Implementation Execution Phase C |
| Current milestone | M1 — Development Environment Ready |
| Completed | TICKET-001, TICKET-002, TICKET-003, TICKET-004 |
| Current ticket | Awaiting TICKET-005 approval |
| Implementation progress | Approximately 35% |

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

Do not store secrets in `.env.example`, source files, images, or logs.

### Start the backend

Start PostgreSQL and apply the baseline migration first:

```bash
docker compose up -d postgres
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

`/health` reports process liveness. `/ready` returns HTTP 200 only when application startup is complete and PostgreSQL accepts a query; otherwise it returns HTTP 503.

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
alembic upgrade head --sql
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
apps/api/                 FastAPI application, database layer, and container definition
apps/web/                 Next.js application, tests, and container definition
docs/operations/          Current operational project state
migrations/               Alembic environment and baseline revision
tests/unit/               Isolated configuration and logging tests
tests/integration/        HTTP API and error-contract tests
packages/                 Reserved for later ticket-owned shared packages
infrastructure/           Reserved for later infrastructure tickets
compose.yaml              PostgreSQL service, health check, and persistent volume
```

## Current Implementation Boundaries

TICKET-004 does not implement domain tables, Redis, Celery, MinIO/S3, OpenAI integrations, media generation, FFmpeg, authentication, or the Workflow Engine.

## Security Rules

1. Never commit `.env`, API keys, access tokens, passwords, signing secrets, or private keys.
2. Log only approved operational metadata; never log authorization headers, request bodies, secrets, or personal information.
3. Return stable public error messages and keep internal exception details out of responses.
4. Do not bypass security controls to accelerate a feature ticket.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
