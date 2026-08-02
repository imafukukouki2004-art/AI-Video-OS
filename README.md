# AI Video OS

AI Video OS is an implementation project for producing short-form social video through a traceable, human-approved AI workflow.

TICKET-002 provides the executable Python backend foundation. Database, queue, storage, frontend, provider, and workflow features remain intentionally out of scope.

## Current Project State

| Field | Value |
| --- | --- |
| Product version | AI Video OS Version 2.0 |
| Phase | Implementation Execution Phase C |
| Current milestone | M1 — Development Environment Ready |
| Completed | TICKET-001, TICKET-002 |
| Current ticket | TICKET-003 — Next.js Frontend Foundation |
| Implementation progress | Python backend foundation complete |

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

## Prerequisites

- Python 3.12
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

Do not store secrets in `.env.example`, source files, images, or logs.

### Start the backend

```bash
uvicorn apps.api.main:app --reload --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
```

Verify the service:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

- API documentation: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

## Verification

```bash
pytest
pytest --cov=apps.api --cov-report=term-missing
ruff check .
ruff format --check .
mypy apps/api
```

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

## Repository Structure

```text
apps/api/                 FastAPI application and container definition
docs/operations/          Current operational project state
tests/unit/               Isolated configuration and logging tests
tests/integration/        HTTP API and error-contract tests
packages/                 Reserved for later ticket-owned shared packages
infrastructure/           Reserved for later infrastructure tickets
migrations/               Reserved for the database ticket
compose.yaml              Empty service skeleton; unchanged in TICKET-002
```

## TICKET-002 Boundaries

This ticket does not implement Next.js, PostgreSQL, SQLAlchemy, Alembic, Redis, Celery, MinIO/S3, OpenAI integrations, media generation, FFmpeg, authentication, domain entities, or the Workflow Engine.

## Security Rules

1. Never commit `.env`, API keys, access tokens, passwords, signing secrets, or private keys.
2. Log only approved operational metadata; never log authorization headers, request bodies, secrets, or personal information.
3. Return stable public error messages and keep internal exception details out of responses.
4. Do not bypass security controls to accelerate a feature ticket.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
