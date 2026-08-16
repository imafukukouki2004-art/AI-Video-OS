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
