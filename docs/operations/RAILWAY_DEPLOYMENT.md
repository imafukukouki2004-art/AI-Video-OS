# Railway Production Deployment Guide

## Purpose and boundary

This guide defines the repository-side deployment package for **AI Video OS on Railway**. Production uses a Railway Storage Bucket as the S3-compatible object store, while local development and CI retain the existing MinIO path-style configuration. The guide prepares a human operator to create Railway services and configure variables, but it does **not** authorize Railway UI operations by Manus, Secret injection, YouTube OAuth authorization, OpenAI generation, YouTube uploads, or Production E2E execution.

> Only the FastAPI API service is public. The Celery Worker, PostgreSQL, Redis, and Railway Storage Bucket remain private to the Railway project.

## Target topology

```text
Internet
   │
   ▼
Railway public HTTPS domain
   │
   ▼
FastAPI API ──► PostgreSQL
   │     └──► Redis / Celery broker
   │     └──► Railway Storage Bucket (S3 compatible)
   ▼
Celery Worker ─► PostgreSQL / Redis / Railway Storage Bucket / FFmpeg
```

| Railway resource | Role | Exposure | Source |
|---|---|---|---|
| `api` | FastAPI API, health endpoint, future OAuth callback | Public HTTPS only | GitHub repository + `deploy/railway/api/railway.toml` |
| `worker` | Always-on Celery worker for workflow and publishing jobs | Private | GitHub repository + `deploy/railway/worker/railway.toml` |
| `postgres` | Durable application database | Private | Railway managed PostgreSQL |
| `redis` | Celery broker and result backend | Private | Railway managed Redis |
| `storage-bucket` | Durable asset and artifact objects | Private, S3-compatible | Railway Storage Bucket |

Railway maps a multi-service Compose-style application to separate services in one project. It provides private networking for internal services and recommends a separate background-worker service for continuous queue processing.[1] [2]

## Storage compatibility

| Environment | Provider | `STORAGE_ADDRESSING_STYLE` | Endpoint style | Expected behavior |
|---|---|---:|---|---|
| Development / CI | Existing MinIO | `path` | Path-style | Existing upload, download, delete, and presigned URL behavior remains unchanged |
| Railway Production | Railway Storage Bucket | `virtual` | Virtual-hosted style | S3-compatible upload, download, delete, and presigned URL behavior |

The repository retains the existing `ObjectStorage` protocol and `S3ObjectStorage` adapter. The only production code extension is the `STORAGE_ADDRESSING_STYLE` setting, whose allowed values are `path` and `virtual`. Railway documents Storage Buckets as private S3-compatible buckets supporting Put, Get, Head, Delete, multipart uploads, and presigned URLs; newly created buckets use virtual-hosted-style addressing.[3]

## Repository configuration

| Service | Railway Config File Path | Dockerfile | Runtime command |
|---|---|---|---|
| API | `/deploy/railway/api/railway.toml` | `deploy/railway/api/Dockerfile` | `uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}` |
| Worker | `/deploy/railway/worker/railway.toml` | `deploy/railway/worker/Dockerfile` | `celery -A apps.worker.celery_app:celery_app worker --loglevel=INFO` |

Keep the GitHub source root at `/` for both services and set the service's **Config File Path** to the exact absolute path above. Railway config files are evaluated independently of a service root directory, so a nested configuration file must be explicitly selected in the Railway UI.[4]

The API Dockerfile intentionally copies `apps/worker` as well as `apps/api`: API queue modules import `apps.worker.celery_app` in order to enqueue jobs. This does not start a second worker; the Celery process is still started only by the private `worker` service.

### Migration strategy

The API `railway.toml` uses Railway's `preDeployCommand` to run `alembic upgrade head` before API startup. The Worker has no migration command. This prevents concurrent API/Worker migration attempts and prevents the API from becoming healthy when the migration command fails. No migration or schema change is introduced by this Railway package.

### Health and restart strategy

The API service binds `0.0.0.0` and Railway's runtime `PORT`, has a `/health` check with a 120-second timeout, and uses `ON_FAILURE` restart behavior. The Worker is an always-on private service with `ALWAYS` restart behavior. Before public DNS is generated, verify API health only through the Railway deployment health status; do not expose the Worker, PostgreSQL, Redis, or Storage Bucket publicly.

## Deployment order

1. Create one Railway project without duplicating an existing project or service.
2. Create private Railway managed PostgreSQL and Redis resources.
3. Create one private Railway Storage Bucket named for the production environment.
4. Create the private `worker` service from the GitHub repository.
5. Create the `api` service from the GitHub repository and configure the API config-file path.
6. Add non-secret variables and reference variables. Enter Secret values only through the human-operated Railway variable UI, then seal them.
7. Deploy API and Worker. Confirm the API deployment applies migrations and the Worker reaches a stable running state.
8. Generate a public domain for **API only**.
9. Stop. The exact OAuth callback URI and Google Cloud registration require later human action after the actual API domain is known.

## Environment-variable specification

The repository's `apps/api/config.py` is the source of truth for application setting names. Railway reference-variable values below assume service names `postgres`, `redis`, and `storage-bucket`; update only the reference prefix if an operator chooses different Railway service names.

### Non-secret variables

| Variable | API | Worker | Production value / purpose |
|---|---:|---:|---|
| `APP_ENV` | Yes | Yes | `production` |
| `APP_DEBUG` | Yes | Yes | `false` |
| `LOG_FORMAT` | Yes | Yes | `json` |
| `LOG_LEVEL` | Yes | Yes | `INFO` or approved operational level |
| `DATABASE_POOL_SIZE` | Yes | Yes | Start from repository default unless capacity planning changes it |
| `DATABASE_MAX_OVERFLOW` | Yes | Yes | Start from repository default |
| `DATABASE_POOL_TIMEOUT_SECONDS` | Yes | Yes | Start from repository default |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | Yes | Yes | Start from repository default |
| `REDIS_CONNECT_TIMEOUT_SECONDS` | Yes | Yes | Start from repository default |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | Yes | Yes | Start from repository default |
| `CELERY_TASK_MAX_RETRIES` | Yes | Yes | Start from repository default |
| `CELERY_RETRY_BACKOFF_MAX_SECONDS` | Yes | Yes | Start from repository default |
| `STORAGE_ADDRESSING_STYLE` | Yes | Yes | **`virtual`** |
| `STORAGE_PRESIGNED_EXPIRY_SECONDS` | Yes | Yes | Start from repository default |
| `STORAGE_CONNECT_TIMEOUT_SECONDS` | Yes | Yes | Start from repository default |
| `STORAGE_READ_TIMEOUT_SECONDS` | Yes | Yes | Start from repository default |
| `STORAGE_MAX_UPLOAD_BYTES` | Yes | Yes | Set within repository validation limit |
| `YOUTUBE_PRIVACY_STATUS` | Yes | Yes | **`private`** |
| `YOUTUBE_OAUTH_REDIRECT_URI` | API | No | Pending actual API public domain; do not invent a value |
| `AI_VIDEO_OS_RUN_PRODUCTION_E2E` | Yes | Yes | **`false`** |

### Railway-provided reference variables

| Application variable | API | Worker | Railway reference |
|---|---:|---:|---|
| `DATABASE_URL` | Yes | Yes | `postgresql+psycopg://${{postgres.PGUSER}}:${{postgres.PGPASSWORD}}@${{postgres.PGHOST}}:${{postgres.PGPORT}}/${{postgres.PGDATABASE}}` |
| `REDIS_URL` | Yes | Yes | `${{redis.REDIS_URL}}` |
| `CELERY_BROKER_URL` | Yes | Yes | `${{redis.REDIS_URL}}` |
| `CELERY_RESULT_BACKEND` | Yes | Yes | `${{redis.REDIS_URL}}` |
| `STORAGE_ENDPOINT_URL` | Yes | Yes | `${{storage-bucket.ENDPOINT}}` |
| `STORAGE_BUCKET` | Yes | Yes | `${{storage-bucket.BUCKET}}` |
| `STORAGE_REGION` | Yes | Yes | `${{storage-bucket.REGION}}` |
| `STORAGE_ACCESS_KEY` | Yes | Yes | `${{storage-bucket.ACCESS_KEY_ID}}` |
| `STORAGE_SECRET_KEY` | Yes | Yes | `${{storage-bucket.SECRET_ACCESS_KEY}}` |

The PostgreSQL template exposes `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, and `PGDATABASE`; the composed URL preserves this repository's async SQLAlchemy `postgresql+psycopg` driver requirement.[5] Railway Redis provides `REDIS_URL` for private project connections.[6] Storage Buckets expose `ENDPOINT`, `BUCKET`, `REGION`, `ACCESS_KEY_ID`, and `SECRET_ACCESS_KEY` for reference-variable use.[3]

### Human-provided Secret variables

Set the following only in Railway's Variables UI. Use sealed variables where Railway supports sealing; do not place values in Git, `.env.example`, logs, messages, or reports.

| Variable | API | Worker | Classification |
|---|---:|---:|---|
| `OPENAI_API_KEY` | Yes | Yes | Secret — human-provided |
| `YOUTUBE_CLIENT_ID` | Yes | Yes | Secret — human-provided |
| `YOUTUBE_CLIENT_SECRET` | Yes | Yes | Secret — human-provided |
| `YOUTUBE_CREDENTIAL_ENCRYPTION_KEY` | Yes | Yes | Secret — existing value only; do not regenerate, rotate, or delete |

Do not set `YOUTUBE_REFRESH_TOKEN` manually. The existing OAuth callback flow is responsible for encrypted persistence of a connected credential after a future, separately approved user authorization.

## Human Railway UI setup guide

### 1. PostgreSQL

| Field | Instruction |
|---|---|
| Service | `postgres` |
| Railway screen | Project Canvas → **Create** → **Database** → **PostgreSQL** |
| Action | Create one managed PostgreSQL service; leave it private and do not add public TCP access |
| Variables | Railway provides `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, and `DATABASE_URL` |
| Classification | Railway-provided; connection fields are secret-bearing references |
| Expected result | `postgres` appears as a running private service and variables are available for API/Worker references |

### 2. Redis

| Field | Instruction |
|---|---|
| Service | `redis` |
| Railway screen | Project Canvas → **Create** → **Database** → **Redis** |
| Action | Create one managed Redis service; leave it private and do not generate public TCP access |
| Variables | Railway provides `REDIS_URL` |
| Classification | Railway-provided, secret-bearing reference |
| Expected result | `redis` is running and its `REDIS_URL` is referenceable by API and Worker |

### 3. Storage Bucket

| Field | Instruction |
|---|---|
| Service | `storage-bucket` |
| Railway screen | Project Canvas → **Create** → **Bucket** |
| Action | Create one bucket in the chosen production region. Do not make storage public. Record only its Railway service name, not credentials. |
| Variables | `ENDPOINT`, `BUCKET`, `REGION`, `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY` |
| Classification | Endpoint/bucket/region are Railway-provided; access values are secret-bearing references |
| Expected result | A private bucket exists and is referenceable by API/Worker variables. Set `STORAGE_ADDRESSING_STYLE=virtual` on both services. |

### 4. API

| Field | Instruction |
|---|---|
| Service | `api` |
| Railway screen | Project Canvas → **Create** → **GitHub Repo**, then API service **Settings** and **Variables** |
| Action | Connect `imafukukouki2004-art/AI-Video-OS`; choose the approved infrastructure branch; set Config File Path to `/deploy/railway/api/railway.toml`; set the variable references above. |
| Variables | Non-secret, reference, and human-provided Secret categories listed above |
| Classification | Use sealed variables for human-provided Secrets; do not put values in Raw Editor unless the operator is authorized to enter them there |
| Expected result | API deployment runs migrations, starts Uvicorn on Railway `PORT`, and passes `/health` deployment health check. |

### 5. Worker

| Field | Instruction |
|---|---|
| Service | `worker` |
| Railway screen | Project Canvas → **Create** → **GitHub Repo**, then Worker service **Settings** and **Variables** |
| Action | Connect the same repository and branch; set Config File Path to `/deploy/railway/worker/railway.toml`; set the same database, Redis, storage, OpenAI, and YouTube variables as required by the worker. |
| Variables | Same as API except `YOUTUBE_OAUTH_REDIRECT_URI` is not required by the Worker |
| Classification | Secrets are human-provided and sealed; all database, Redis, and Bucket credential values are references |
| Expected result | Celery runs continuously, connects to Redis, and receives no public domain. |

### 6. Public API domain

| Field | Instruction |
|---|---|
| Service | `api` only |
| Railway screen | API service → **Settings** → **Networking** → **Generate Domain** |
| Action | Generate one Railway public domain after API health succeeds. Do not generate domains for Worker, PostgreSQL, Redis, or Storage Bucket. |
| Variables | `RAILWAY_PUBLIC_DOMAIN` becomes available to API service |
| Classification | Railway-provided, non-secret |
| Expected result | HTTPS API URL is available; the future callback is exactly `https://<actual-api-domain>/publishing/connections/youtube/callback`. |

### 7. Health check

| Field | Instruction |
|---|---|
| Service | `api` |
| Railway screen | API service → **Deployments** / **Healthcheck** |
| Action | Confirm the repository configuration uses `/health`; inspect deployment logs for successful migration then health status. |
| Variables | None |
| Classification | Non-secret |
| Expected result | API health check reports healthy. A migration failure must prevent a healthy API start. |

## OAuth preparation and stop point

When the API public domain exists, the exact production callback becomes:

```text
https://<actual-api-domain>/publishing/connections/youtube/callback
```

A human must register that exact URI in Google Cloud and set the identical value for `YOUTUBE_OAUTH_REDIRECT_URI` in Railway. Do not register a guessed domain, start OAuth, or perform any external generation/upload as part of this deployment package.

## Rollback and troubleshooting

| Symptom | Check | Safe remediation |
|---|---|---|
| `ModuleNotFoundError: apps.worker` in API | Verify API Config File Path and deployed commit contain the `apps/worker` COPY line | Redeploy the approved API branch; do not collapse API and Worker into one service |
| Migration fails | Review migration logs before API startup | Correct the non-secret database reference mapping or migration issue; do not start Worker migrations |
| Worker crash loop | Verify `REDIS_URL`, Celery broker/result references, and Worker Config File Path | Correct Railway reference variables and redeploy Worker |
| Bucket 403 or invalid URL | Verify Bucket reference variables and `STORAGE_ADDRESSING_STYLE=virtual` | Correct references; keep the bucket private |
| Presigned URL fails | Confirm Bucket endpoint and virtual addressing mode | Verify client contract; do not expose bucket publicly as a workaround without approval |

## References

[1]: https://docs.railway.com/guides/docker-compose "Railway: Deploy a Docker Compose App to Production"
[2]: https://docs.railway.com/guides/cron-workers-queues "Railway Background Workers and Queues"
[3]: https://docs.railway.com/storage-buckets "Railway Storage Buckets"
[4]: https://docs.railway.com/deployments/monorepo "Railway Monorepo Deployment"
[5]: https://docs.railway.com/databases/postgresql "Railway PostgreSQL"
[6]: https://docs.railway.com/databases/redis "Railway Redis"


## Parallel preparation supplement

> This supplement is repository-based preparation only. It does not assert current Railway state, create a Railway resource, deploy a service, mutate a variable, inspect a Secret, perform OAuth, or execute Production E2E. Where a Railway service name or provided variable name depends on the human-created project, the required operator status is **VERIFY IN RAILWAY UI**.

### Production Variables Matrix

The variable names below come directly from `apps/api/config.py`. The API and Worker both load the same Settings model; a variable is marked `Not required` for a service only where the repository start path does not require it. Defaults are suitable for local development, not evidence that the variable may be omitted in production.

#### Application, logging, and runtime settings

| Variable | API | Worker | Classification | Production specification |
|---|---:|---:|---|---|
| `APP_NAME` | Optional | Optional | NON-SECRET | Keep repository default unless an approved service identity is required. |
| `APP_ENV` | Required | Required | NON-SECRET | `production` |
| `APP_VERSION` | Optional | Optional | NON-SECRET | Repository default or approved release version. |
| `APP_HOST` / `API_HOST` | Optional | Not required | NON-SECRET | API container already binds `0.0.0.0`; do not set unless troubleshooting requires it. |
| `APP_PORT` / `API_PORT` | Optional | Not required | NON-SECRET | Railway start command uses runtime `PORT`; do not override without approval. |
| `PORT` | Railway runtime | Not required | RAILWAY-PROVIDED | Railway assigns this to the API process. Do not set manually. |
| `APP_DEBUG` | Required | Required | NON-SECRET | `false` |
| `LOG_LEVEL` | Required | Required | NON-SECRET | `INFO`, unless an approved operational level is needed. |
| `LOG_FORMAT` | Required | Required | NON-SECRET | `json` |

#### Database settings

| Variable | API | Worker | Classification | Production specification |
|---|---:|---:|---|---|
| `DATABASE_URL` | Required | Required | REFERENCE VARIABLE CANDIDATE | Use the PostgreSQL private connection inputs with the `postgresql+psycopg` driver. **VERIFY IN RAILWAY UI**. |
| `DATABASE_POOL_SIZE` | Optional | Optional | NON-SECRET | Repository default unless capacity planning changes it. |
| `DATABASE_MAX_OVERFLOW` | Optional | Optional | NON-SECRET | Repository default unless capacity planning changes it. |
| `DATABASE_POOL_TIMEOUT_SECONDS` | Optional | Optional | NON-SECRET | Repository default unless an approved timeout adjustment is needed. |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | Optional | Optional | NON-SECRET | Repository default unless an approved timeout adjustment is needed. |

#### Redis and Celery settings

| Variable | API | Worker | Classification | Production specification |
|---|---:|---:|---|---|
| `REDIS_URL` | Required | Required | REFERENCE VARIABLE CANDIDATE | Reference the managed Redis private URL. **VERIFY IN RAILWAY UI**. |
| `REDIS_CONNECT_TIMEOUT_SECONDS` | Optional | Optional | NON-SECRET | Repository default unless an approved timeout adjustment is needed. |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | Optional | Optional | NON-SECRET | Repository default unless an approved timeout adjustment is needed. |
| `CELERY_BROKER_URL` | Required | Required | REFERENCE VARIABLE CANDIDATE | Reference the same managed Redis private URL. **VERIFY IN RAILWAY UI**. |
| `CELERY_RESULT_BACKEND` | Required | Required | REFERENCE VARIABLE CANDIDATE | Reference the same managed Redis private URL. **VERIFY IN RAILWAY UI**. |
| `CELERY_TASK_MAX_RETRIES` | Optional | Optional | NON-SECRET | Repository default unless an approved retry policy changes it. |
| `CELERY_RETRY_BACKOFF_MAX_SECONDS` | Optional | Optional | NON-SECRET | Repository default unless an approved retry policy changes it. |

#### Object storage settings

| Variable | API | Worker | Classification | Production specification |
|---|---:|---:|---|---|
| `STORAGE_ENDPOINT_URL` | Required | Required | REFERENCE VARIABLE CANDIDATE | Reference the Railway Storage Bucket endpoint. **VERIFY IN RAILWAY UI**. |
| `STORAGE_ACCESS_KEY` | Required | Required | REFERENCE VARIABLE CANDIDATE | Reference the Bucket access-key variable; it is secret-bearing. **VERIFY IN RAILWAY UI**. |
| `STORAGE_SECRET_KEY` | Required | Required | REFERENCE VARIABLE CANDIDATE | Reference the Bucket secret-key variable; it is secret-bearing. **VERIFY IN RAILWAY UI**. |
| `STORAGE_BUCKET` | Required | Required | REFERENCE VARIABLE CANDIDATE | Reference the Bucket name. **VERIFY IN RAILWAY UI**. |
| `STORAGE_REGION` | Required | Required | REFERENCE VARIABLE CANDIDATE | Reference the Bucket region. **VERIFY IN RAILWAY UI**. |
| `STORAGE_ADDRESSING_STYLE` | Required | Required | NON-SECRET | `virtual` for Railway Storage Bucket. |
| `STORAGE_MAX_UPLOAD_BYTES` | Optional | Optional | NON-SECRET | Set only within repository validation bounds. |
| `STORAGE_PRESIGNED_EXPIRY_SECONDS` | Optional | Optional | NON-SECRET | Repository default unless an approved expiry is required. |
| `STORAGE_CONNECT_TIMEOUT_SECONDS` | Optional | Optional | NON-SECRET | Repository default unless an approved timeout adjustment is needed. |
| `STORAGE_READ_TIMEOUT_SECONDS` | Optional | Optional | NON-SECRET | Repository default unless an approved timeout adjustment is needed. |

#### OpenAI and YouTube settings

| Variable | API | Worker | Classification | Production specification |
|---|---:|---:|---|---|
| `OPENAI_API_KEY` | Required for AI work | Required for AI work | SECRET / HUMAN-PROVIDED | Human enters a sealed value. This preparation does not request or inspect it. |
| `OPENAI_MODEL` | Optional | Optional | NON-SECRET | Repository default or separately approved model. |
| `YOUTUBE_CLIENT_ID` | Required for OAuth/publishing | Required for OAuth/publishing | SECRET / HUMAN-PROVIDED | Human enters a sealed value. |
| `YOUTUBE_CLIENT_SECRET` | Required for OAuth/publishing | Required for OAuth/publishing | SECRET / HUMAN-PROVIDED | Human enters a sealed value. |
| `YOUTUBE_REFRESH_TOKEN` | Do not set manually | Do not set manually | SECRET / PROHIBITED MANUAL INPUT | Existing callback flow persists an encrypted connected credential after a later approved OAuth action. |
| `YOUTUBE_PRIVACY_STATUS` | Required | Required | NON-SECRET | `private` |
| `YOUTUBE_OAUTH_REDIRECT_URI` | Required after domain exists | Not required | HUMAN-PROVIDED NON-SECRET CONFIGURATION | Pending actual public API domain. Do not invent a value. |
| `YOUTUBE_OAUTH_STATE_TTL_SECONDS` | Optional | Not required | NON-SECRET | Repository default unless separately approved. |
| `YOUTUBE_CREDENTIAL_ENCRYPTION_KEY` | Required for OAuth credential persistence | Required for credential resolution | SECRET / HUMAN-PROVIDED | Preserve the existing value. Do not generate, rotate, display, or delete it. |
| `AI_VIDEO_OS_RUN_PRODUCTION_E2E` | Required safety setting | Required safety setting | NON-SECRET | `false` |

### Railway Reference Variable Mapping

The following mapping is a reference-variable specification, not a record of the human operator's Railway project. Railway service labels and exact provided-variable identifiers must be confirmed in the human-operated Railway UI before any setting is entered.

| Destination service | Application variable | Source service | Repository-required value form | Status |
|---|---|---|---|---|
| API | `DATABASE_URL` | PostgreSQL | A private PostgreSQL connection constructed with the repository's `postgresql+psycopg` scheme. | **VERIFY IN RAILWAY UI** |
| Worker | `DATABASE_URL` | PostgreSQL | A private PostgreSQL connection constructed with the repository's `postgresql+psycopg` scheme. | **VERIFY IN RAILWAY UI** |
| API | `REDIS_URL` | Redis | Managed Redis private URL. | **VERIFY IN RAILWAY UI** |
| Worker | `REDIS_URL` | Redis | Managed Redis private URL. | **VERIFY IN RAILWAY UI** |
| API | `CELERY_BROKER_URL` | Redis | Same managed Redis private URL. | **VERIFY IN RAILWAY UI** |
| Worker | `CELERY_BROKER_URL` | Redis | Same managed Redis private URL. | **VERIFY IN RAILWAY UI** |
| API | `CELERY_RESULT_BACKEND` | Redis | Same managed Redis private URL. | **VERIFY IN RAILWAY UI** |
| Worker | `CELERY_RESULT_BACKEND` | Redis | Same managed Redis private URL. | **VERIFY IN RAILWAY UI** |
| API | `STORAGE_ENDPOINT_URL` | Storage Bucket | Bucket endpoint. | **VERIFY IN RAILWAY UI** |
| Worker | `STORAGE_ENDPOINT_URL` | Storage Bucket | Bucket endpoint. | **VERIFY IN RAILWAY UI** |
| API | `STORAGE_BUCKET` | Storage Bucket | Bucket name. | **VERIFY IN RAILWAY UI** |
| Worker | `STORAGE_BUCKET` | Storage Bucket | Bucket name. | **VERIFY IN RAILWAY UI** |
| API | `STORAGE_REGION` | Storage Bucket | Bucket region. | **VERIFY IN RAILWAY UI** |
| Worker | `STORAGE_REGION` | Storage Bucket | Bucket region. | **VERIFY IN RAILWAY UI** |
| API | `STORAGE_ACCESS_KEY` | Storage Bucket | Secret-bearing access-key reference. | **VERIFY IN RAILWAY UI** |
| Worker | `STORAGE_ACCESS_KEY` | Storage Bucket | Secret-bearing access-key reference. | **VERIFY IN RAILWAY UI** |
| API | `STORAGE_SECRET_KEY` | Storage Bucket | Secret-bearing secret-key reference. | **VERIFY IN RAILWAY UI** |
| Worker | `STORAGE_SECRET_KEY` | Storage Bucket | Secret-bearing secret-key reference. | **VERIFY IN RAILWAY UI** |

The earlier examples in this guide use `postgres`, `redis`, and `storage-bucket` as descriptive service labels only. If the human-created Railway project uses different labels, update the Railway reference syntax in the UI without changing repository code. Do not copy a rendered connection string, credential, or any Secret into documentation, Git, chat, or logs.

### Variable readiness status

| Category | Repository specification status | Human Railway UI status |
|---|---|---|
| API variable inventory | COMPLETE | PENDING HUMAN CONFIGURATION |
| Worker variable inventory | COMPLETE | PENDING HUMAN CONFIGURATION |
| Secret classification | COMPLETE | PENDING HUMAN SECRET INPUT |
| Reference mapping | COMPLETE as specification | **VERIFY IN RAILWAY UI** |
| Production E2E safety flag | COMPLETE — must remain `false` | PENDING HUMAN CONFIRMATION |


### Railway Service Configuration Matrix

| Service | Role and exposure | Repository source / config | Start and health behavior | Dependencies | Required configuration | Expected healthy state |
|---|---|---|---|---|---|---|
| API | FastAPI public HTTPS service after a human creates a domain. | GitHub branch approved for PR #77; `/deploy/railway/api/railway.toml`; `deploy/railway/api/Dockerfile`. | `alembic upgrade head` runs before deploy; Uvicorn starts on Railway `PORT`; Railway health path is `/health`. | PostgreSQL, Redis, Storage Bucket. | Database, Redis, storage, application/logging variables, and required human Secrets. `YOUTUBE_OAUTH_REDIRECT_URI` remains pending until the real domain exists. | Deployment succeeds, migration succeeds, `/health` reports `status: ok`, and `/ready` reports all dependencies connected. |
| Worker | Always-on private Celery process for workflow and publishing jobs. | Same GitHub branch; `/deploy/railway/worker/railway.toml`; `deploy/railway/worker/Dockerfile`. | Celery starts with `celery -A apps.worker.celery_app:celery_app worker --loglevel=INFO`; restart policy is `ALWAYS`. No HTTP health endpoint is configured. | PostgreSQL, Redis, Storage Bucket; OpenAI and YouTube Secrets are needed only when those jobs are later authorized. | Same database, Redis, storage, application/logging settings as API. No OAuth redirect URI is required. | Stable running deployment with no crash-loop and broker-connected Celery startup log. |
| PostgreSQL | Private durable application database. | Railway managed PostgreSQL; no repository Dockerfile. | Railway managed lifecycle. | None. | Must provide private connection inputs that can be mapped to repository `DATABASE_URL`. | Online in Railway UI; API migration succeeds; API and Worker can connect. |
| Redis | Private broker and result backend. | Railway managed Redis; no repository Dockerfile. | Railway managed lifecycle. | None. | Must provide a private URL reference for `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND`. | Online in Railway UI; API Redis readiness and Worker broker connection succeed. |
| Storage Bucket | Private S3-compatible production object store. | Railway Storage Bucket; no repository Dockerfile. | Railway managed lifecycle. | None. | Must expose referenceable endpoint, bucket, region, and secret-bearing credentials; API and Worker must use `STORAGE_ADDRESSING_STYLE=virtual`. | API and Worker can upload, read, delete, and produce a usable presigned URL without making the Bucket public. |

### Production Infrastructure Validation Runbook

This Runbook is for the human operator after Railway UI construction is complete. It uses observations, non-secret URLs, deployment status, and sanitized logs only. It must not print values of variables, credentials, authorization codes, tokens, or ciphertext. An API domain is required only for public HTTP checks; until then, use Railway deployment health and logs.

| Check | Purpose | Command, endpoint, or observation | Expected result | Failure indication | Safe troubleshooting |
|---|---|---|---|---|---|
| API deployment | Confirm the API image and config file deploy. | Railway API deployment status and sanitized deploy log. | Latest deployment succeeds. | Failed build, pre-deploy failure, or restart loop. | Confirm branch, Config File Path, and Dockerfile path. Do not redeploy or alter settings from Manus. |
| API migration | Confirm the sole migration owner ran successfully. | API pre-deploy log; non-secret Alembic revision output if Railway displays it. | `alembic upgrade head` completes before API start. | Migration error or health never starts. | Human verifies private database mapping and migration log; Worker must not run migrations. |
| API process health | Confirm process liveness. | `GET https://<actual-api-domain>/health` only after human supplies the real domain, or Railway health status before domain generation. | HTTP 200 with `status: ok`. | Non-200, health timeout, or crash-loop. | Human checks API deployment logs and `PORT` binding; no public domain is created for non-API services. |
| API dependency readiness | Confirm API-to-infrastructure connections. | `GET https://<actual-api-domain>/ready` only after domain exists. | HTTP 200 with `database`, `redis`, and `storage` all `connected`. | HTTP 503 or any dependency `unavailable`. | Human verifies the relevant private reference variable, service status, and `STORAGE_ADDRESSING_STYLE=virtual`. |
| Worker deployment | Confirm Worker image and command start. | Railway Worker deployment status and sanitized startup log. | Stable running service. | Immediate exit or repeated restart. | Human verifies Worker Config File Path and start command. |
| Worker crash-loop | Confirm queue processor stays available. | Railway Worker deployment history and restart count. | No unexpected repeating restart. | Increasing restart count or repeated stack trace. | Human checks database/Redis/storage references and logs without exposing values. |
| PostgreSQL connectivity | Confirm API and Worker can reach the database. | API `/ready` database state; Worker sanitized startup or task log. | `connected` for API; no connection exception for Worker. | SQLAlchemy connection error or worker database error. | Human verifies private PostgreSQL reference mapping and driver scheme. |
| Redis connectivity | Confirm API can reach Redis. | API `/ready` Redis state. | `redis: connected`. | HTTP 503 or `redis: unavailable`. | Human verifies managed Redis status and `REDIS_URL` reference. |
| Celery broker connectivity | Confirm Worker can consume from Redis. | Worker sanitized startup log. | Broker connection succeeds; Worker remains running. | Broker connection/refused/auth error. | Human verifies all three Redis-related variable mappings. |
| Celery worker readiness | Confirm the Worker registers its tasks. | Sanitized Worker startup log listing ready/registered task state. | Worker is ready and idle without loop. | Task-import error or queue connection failure. | Human verifies the deployed commit includes `apps/worker` and does not expose the Worker publicly. |
| Storage upload | Confirm private object creation. | A future approved non-production storage validation action recorded by application logs or a controlled internal validation flow. | Object operation reports success. | S3 client exception, access denied, or invalid endpoint. | Human verifies Bucket references and virtual addressing; do not make Bucket public. |
| Storage read | Confirm object retrieval. | Controlled internal storage validation observation. | Previously uploaded object can be retrieved. | NoSuchKey, access denied, or endpoint error. | Human confirms matching Bucket, endpoint, region, and credentials references. |
| Storage delete | Confirm object cleanup. | Controlled internal storage validation observation. | Test object is removed and subsequent lookup reports absent. | Delete error or retained object. | Human verifies Bucket reference mapping. Do not delete production assets. |
| Presigned URL generation | Confirm signed URL creation. | Controlled internal validation returns a URL without logging query credentials. | URL is produced for a private object. | Client-side signing error or malformed host. | Human confirms `STORAGE_ADDRESSING_STYLE=virtual` and Bucket endpoint reference. |
| Presigned URL accessibility | Confirm the generated URL reaches the intended object. | Access the generated URL only in the approved operator validation context; record HTTP status, never the signed query string. | Expected object response succeeds during the configured expiry. | Host/DNS/signature mismatch, 403, or 404. | Human verifies virtual-hosted addressing and endpoint configuration; do not expose Bucket generally. |

The storage upload/read/delete/presigned checks are infrastructure validation activities only. They must not invoke OpenAI, OAuth, publication, YouTube upload, or the Production E2E runner.

### OAuth Production Preparation Runbook

| Item | Repository-confirmed specification | Human Google Cloud action | Validation point | Current status |
|---|---|---|---|---|
| OAuth callback route | `GET /publishing/connections/youtube/callback` | None until a real API domain is available. | Route is registered in the FastAPI publishing router. | READY |
| OAuth initiation route | `POST /publishing/connections/youtube/authorize` | Do not invoke in this preparation phase. | Route is registered but unused. | NOT EXECUTED |
| Production domain | Must be the actual public HTTPS domain of the API service. | Generate and provide only the actual API domain through Railway UI. | Non-secret domain is known. | PENDING HUMAN SETUP |
| Redirect URI | `https://<actual-api-domain>/publishing/connections/youtube/callback` | In Google Cloud Console, add the exact URI to the OAuth Web Client's Authorized redirect URIs; set the same value as `YOUTUBE_OAUTH_REDIRECT_URI` in Railway API variables. | Exact equality between Google Cloud and Railway configuration. | PENDING DOMAIN |
| Google Cloud API | YouTube Data API v3 is required by the existing provider. | Confirm the API is enabled for the existing project. | API appears enabled in Google Cloud Console. | VERIFY BY HUMAN |
| OAuth consent screen | Existing OAuth flow requests the repository-defined YouTube upload scope. | Confirm consent screen configuration allows the intended account and scope. | Consent screen is ready for a later approval. | VERIFY BY HUMAN |
| Credential security | Callback encrypts the refresh token before persistence; connection status becomes `CONNECTED` only after successful persistence. | Do not paste, export, or inspect token values. | Later evidence can show encrypted credential record exists without revealing ciphertext. | READY FOR FUTURE AUTHORIZATION |

The production domain must not be guessed. This document intentionally does not produce an authorization URL, invoke the initiate endpoint, execute a callback, exchange a code, or create a connected credential.

### PR #77 Pre-Merge Evidence Checklist

The following evidence must be gathered by the human operator after the Railway UI deployment and before a merge decision. This checklist is not evidence that the current Railway environment is healthy.

| Required condition | Evidence to submit | Pass criterion |
|---|---|---|
| API deployed | Railway deployment status and sanitized deployment log. | Latest API deployment succeeds. |
| API health PASS | HTTP status and non-secret response summary from `/health`, or Railway healthcheck status before domain exists. | HTTP 200 / healthy status. |
| API readiness PASS | HTTP status and non-secret `/ready` dependency summary after domain exists. | HTTP 200; database, Redis, and storage connected. |
| Worker running | Railway Worker status and sanitized startup log. | Stable running state. |
| No crash-loop | Railway restart/deployment history. | No unexpected repeated restart. |
| PostgreSQL connected | API readiness evidence plus migration log summary. | Connected and migration current. |
| Alembic migration current | API pre-deploy log or non-secret revision observation. | `upgrade head` successful. |
| Redis connected | API readiness evidence. | Redis connected. |
| Celery connected | Sanitized Worker broker-connected startup observation. | Worker remains ready. |
| Storage R/W/Delete PASS | Controlled internal validation result with object identifiers redacted as appropriate. | All operations succeed. |
| Presigned URL PASS | HTTP result and expiry observation; never the signed URL query. | Accessible within expiry. |
| Production domain confirmed | Non-secret HTTPS API domain. | API-only public domain exists. |
| OAuth callback reachable | Route response observation only after a separately approved OAuth-related validation. | Callback route is reachable; no OAuth is performed for PR #77 evidence alone. |
| Secrets not exposed | Git diff / secret scan / sanitized log review. | No Secret values in Git, PR text, report, or logs. |
| Production E2E OFF | Railway variable metadata or human assertion without value dump. | `AI_VIDEO_OS_RUN_PRODUCTION_E2E=false` or unset. |
| Production OpenAI calls | Operational record. | `0` for this infrastructure PR. |
| YouTube uploads | Operational record. | `0` for this infrastructure PR. |
| GitHub CI SUCCESS | PR #77 GitHub Actions URL and job results. | Python quality, Frontend quality, and Development Environment Acceptance succeed. |
| Working Tree clean | Git status summary from the reviewed branch. | Clean and remote-synchronized. |

### Human-action boundaries

| Condition | Required action | Manus status |
|---|---|---|
| Add a variable, reference, or Secret | Human Railway UI action. | Not performed. |
| Create, modify, redeploy, or expose a Railway service | Human Railway UI action. | Not performed. |
| Generate production domain | Human Railway UI action. | Not performed. |
| Register Google Cloud redirect URI or grant OAuth consent | Human Google Cloud action. | Not performed. |
| Run Production E2E, OpenAI generation, or YouTube upload | Separate CEO authorization required. | Not performed. |

### Preparation completion criteria

Repository-based variables, mapping, service configuration, validation runbook, OAuth runbook, and PR #77 evidence criteria are complete when this document is committed and CI remains successful. Actual production readiness requires both this repository specification and human-verified Railway state; neither source alone is sufficient.
