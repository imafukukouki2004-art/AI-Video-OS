# AI Video OS

AI Video OS is an implementation project for producing short-form social video through a traceable, human-approved AI workflow.

This repository currently contains the foundation created by **TICKET-001: Repository Initialization**. Application code and infrastructure services are intentionally not implemented in this ticket.

## MVP Goal

The Version 2.0 MVP will accept a Business Strategy and Trend Brief, then produce one post-ready vertical short video through the following controlled workflow:

1. Generate a content plan.
2. Generate and review a script.
3. Generate scene prompts.
4. Generate media and voice assets.
5. Assemble a 9:16 video.
6. Perform technical quality validation.
7. Require final human approval.
8. Export the MP4 and associated publishing package.

The MVP is considered validated when the same workflow produces three consecutive short videos with execution history, recoverable failures, approval records, and per-video cost tracking.

## Technology Stack

The planned MVP stack is:

| Area | Technology |
| --- | --- |
| Backend language | Python |
| Backend API | FastAPI |
| Frontend | Next.js App Router and TypeScript |
| API contracts | OpenAPI and Pydantic |
| Database | PostgreSQL |
| ORM and migration | SQLAlchemy and Alembic |
| Asynchronous jobs | Celery |
| Message broker and cache | Redis |
| Workflow state | PostgreSQL-backed internal state machine |
| Object storage | S3-compatible storage; MinIO for local development |
| Text generation | OpenAI Responses API |
| Image generation | OpenAI Image API |
| Voice generation | OpenAI Speech API |
| Media processing | FFmpeg and ffprobe |
| Local runtime | Docker Compose |
| Testing | pytest, Vitest, and Playwright |
| CI/CD | GitHub Actions |

These technologies are documented as planned selections. Their application code and runtime services will be introduced only in the corresponding implementation tickets.

## Directory Structure

```text
ai-video-os/
├── apps/
│   ├── api/                    # FastAPI application
│   ├── web/                    # Next.js operator interface
│   └── workers/                # Asynchronous worker entry points
├── packages/
│   ├── contracts/              # API, agent, event, and provider contracts
│   ├── domain/                 # Domain entities and business rules
│   ├── providers/              # External provider adapters
│   └── shared/                 # Shared utilities and common definitions
├── infrastructure/
│   ├── docker/                 # Container-related configuration
│   └── local/                  # Local environment configuration
├── migrations/                 # Database migrations
├── tests/
│   ├── unit/                   # Isolated domain and component tests
│   ├── integration/            # Database, queue, storage, and API tests
│   └── e2e/                    # End-to-end workflow tests
├── scripts/                    # Development and operational scripts
├── docs/
│   ├── architecture/           # Approved architecture documents
│   ├── decisions/              # Architecture decision records
│   └── operations/             # Operational procedures and runbooks
├── compose.yaml                # Minimal Compose skeleton
├── .env.example                # Environment variable names without secrets
├── .gitignore
├── .editorconfig
├── README.md
└── LICENSE
```

Empty directories contain `.gitkeep` so the repository structure is preserved by Git.

## Local Setup

TICKET-001 does not yet include executable backend, frontend, database, worker, or storage services. The current setup verifies the repository foundation only.

### Prerequisites

- Git
- Docker with Docker Compose support
- A code editor that respects `.editorconfig`

### Clone and prepare the environment

```bash
git clone <repository-url> ai-video-os
cd ai-video-os
cp .env.example .env
```

Leave secret fields empty until the ticket responsible for that integration provides setup instructions. Never place production credentials in a local development file.

### Validate the Compose skeleton

```bash
docker compose config
```

The file is intentionally minimal and contains no services. TICKET-002 through TICKET-007 will add the backend, frontend, PostgreSQL, Redis, workers, MinIO, and their runtime configuration.

## Development Conventions

Recommended branch naming:

```text
feature/<ticket-id>-<description>
fix/<ticket-id>-<description>
```

Recommended commit prefixes:

```text
feat:
fix:
refactor:
test:
docs:
chore:
```

Each implementation change should reference its ticket, include verification steps, and remain within the approved ticket scope.

## Security Rules

1. Never commit `.env`, API keys, access tokens, passwords, signing secrets, or private keys.
2. `.env.example` must contain variable names and safe placeholders only.
3. External provider credentials must be injected through environment variables or a managed secret store.
4. Generated media and large binary files must not be committed to Git.
5. Production data must not be copied into development or test environments without authorization and anonymization.
6. Logs must not contain secrets, credentials, raw binary assets, or unnecessary personal information.
7. Object storage must be private by default; time-limited signed access should be used when asset access is implemented.
8. Dependency, container, and secret scanning will be introduced through the CI foundation ticket.
9. Security controls must not be bypassed to accelerate a feature ticket.
10. Suspected credential exposure must result in immediate credential rotation and incident documentation.

## Current Project State

| Field | Value |
| --- | --- |
| Product version | AI Video OS Version 2.0 |
| Phase | Implementation Execution Phase C |
| Current milestone | M1: Development Environment Ready |
| Current ticket | TICKET-001: Repository Initialization |
| Planning progress | 100% |
| Implementation progress | Repository foundation initialized |
| Next approved ticket | TICKET-002: Python Backend Foundation |

### TICKET-001 boundaries

Included:

- Repository directory structure
- Root configuration placeholders
- Security-safe environment template
- Minimal Compose skeleton
- Repository documentation
- Git initialization

Not included:

- Backend application code
- Frontend application code
- Worker implementation
- Database or migration implementation
- Redis or Celery configuration
- Object-storage services
- CI workflows
- New architecture documents

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
