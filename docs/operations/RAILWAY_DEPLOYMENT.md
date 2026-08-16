# Railway Production Deployment Guide

## Purpose and scope

This document defines the Railway deployment topology for **AI Video OS**. It deploys the FastAPI API and Celery Worker as separate long-running services, provisions PostgreSQL and Redis through Railway database services, and runs MinIO as a private S3-compatible storage service backed by a Railway Volume. It does **not** authorize YouTube OAuth, run Production E2E validation, or store any credential values in the repository.

> Only the **API** service receives a public domain. PostgreSQL, Redis, MinIO, the bucket-initialization service, and the Celery Worker must remain private to the Railway project network.

## Service topology

| Railway service name | Source | Execution role | Network exposure | Persistence |
|---|---|---|---|---|
| `api` | GitHub repository, `deploy/railway/api/Dockerfile` | FastAPI HTTP API and OAuth callback endpoint | Public domain required | No local volume |
| `worker` | GitHub repository, `deploy/railway/worker/Dockerfile` | Always-on Celery Worker for workflow and publishing jobs | Private only | No local volume |
| `postgres` | Railway PostgreSQL database service | Workflow, asset, artifact, and publication data | Private only | Railway database storage |
| `redis` | Railway Redis database service | Celery broker and result backend | Private only | Railway database storage |
| `minio` | GitHub repository, `deploy/railway/minio/Dockerfile` | Private S3-compatible object storage | Private only | Railway Volume mounted at `/data` |
| `minio-init` | GitHub repository, `deploy/railway/minio-init/Dockerfile` | One-time, idempotent bucket creation | Private only | None |

Railway maps Docker Compose-style workloads to separate services in one project. The managed PostgreSQL and Redis services provide connection variables, and private service-to-service networking requires no public exposure.[1] [2] A continuous Celery Worker is deployed as a separate always-on service from the API.[3]

## Repository deployment files

Each application service uses a service-specific Railway configuration file:

| Service | Railway configuration file | Dockerfile path |
|---|---|---|
| API | `/deploy/railway/api/railway.toml` | `deploy/railway/api/Dockerfile` |
| Worker | `/deploy/railway/worker/railway.toml` | `deploy/railway/worker/Dockerfile` |
| MinIO | `/deploy/railway/minio/railway.toml` | `deploy/railway/minio/Dockerfile` |
| MinIO init | `/deploy/railway/minio-init/railway.toml` | `deploy/railway/minio-init/Dockerfile` |

For every GitHub-backed service, retain the repository root directory as `/` and set the service's **Config File Path** to the corresponding absolute path above. Railway treats its config file independently of a configured root directory; therefore, do not assume nested configuration is discovered automatically.[4]

## Railway project setup

Create one Railway project and add the services in the following order:

1. Add a Railway **PostgreSQL** service and name it `postgres`.
2. Add a Railway **Redis** service and name it `redis`.
3. Add the `minio` GitHub service. Set Config File Path to `/deploy/railway/minio/railway.toml`, then attach a Railway Volume at `/data`.
4. Add the `minio-init` GitHub service. Set Config File Path to `/deploy/railway/minio-init/railway.toml`.
5. Add the `api` GitHub service. Set Config File Path to `/deploy/railway/api/railway.toml`.
6. Add the `worker` GitHub service. Set Config File Path to `/deploy/railway/worker/railway.toml`.
7. Generate a public domain for **only** the `api` service. Do not generate public domains for the remaining services.

The `api` configuration runs `alembic upgrade head` as its pre-deploy command, binds Uvicorn to Railway's `PORT`, and checks `/health`. The Worker and MinIO are configured as persistent services; `minio-init` exits successfully after creating the configured bucket and is safe to run again.

## Railway variables and secrets

Use **Project Settings → Shared Variables** for values that must be referenced by more than one service. Use service-level variables for service-specific references. Seal all values marked **Secret** after entering them; Railway sealed variables are supplied to builds and deployments but cannot subsequently be viewed in the UI or retrieved through the API.[5]

### Shared variables

| Variable | Classification | Value source / required value | Services |
|---|---|---|---|
| `APP_ENV` | Configuration | `production` | API, Worker |
| `APP_DEBUG` | Configuration | `false` | API, Worker |
| `LOG_FORMAT` | Configuration | `json` | API, Worker |
| `STORAGE_BUCKET` | Configuration | `ai-video-os-assets` or approved replacement | API, Worker, MinIO init |
| `STORAGE_REGION` | Configuration | `us-east-1` | API, Worker |
| `YOUTUBE_PRIVACY_STATUS` | Safety configuration | **`private`** | API, Worker |
| `AI_VIDEO_OS_RUN_PRODUCTION_E2E` | Safety configuration | **`false`** | API, Worker |
| `OPENAI_API_KEY` | **Secret** | Production OpenAI key, entered only in Railway | API, Worker |
| `MINIO_ROOT_USER` | **Secret** | Operator-selected MinIO root user | MinIO, MinIO init |
| `MINIO_ROOT_PASSWORD` | **Secret** | Operator-selected MinIO root password | MinIO, MinIO init |
| `STORAGE_ACCESS_KEY` | **Secret** | Reference the same value as `MINIO_ROOT_USER` | API, Worker, MinIO init |
| `STORAGE_SECRET_KEY` | **Secret** | Reference the same value as `MINIO_ROOT_PASSWORD` | API, Worker, MinIO init |
| `YOUTUBE_CLIENT_ID` | **Secret** | Google OAuth Web Client ID | API, Worker |
| `YOUTUBE_CLIENT_SECRET` | **Secret** | Google OAuth Web Client Secret | API, Worker |
| `YOUTUBE_CREDENTIAL_ENCRYPTION_KEY` | **Secret** | **Existing Fernet key only; do not rotate or replace** | API, Worker |

Do not set `YOUTUBE_REFRESH_TOKEN` manually. The existing TICKET-038 Authorization Code Flow stores a refresh token as encrypted connected-credential data after the user approves the upload scope.

### API service reference variables

Set the following in the `api` service's **Variables** tab. Replace the service-name portions if your Railway project uses different names.

| Variable | Railway reference or value | Classification |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://${{postgres.PGUSER}}:${{postgres.PGPASSWORD}}@${{postgres.PGHOST}}:${{postgres.PGPORT}}/${{postgres.PGDATABASE}}` | Reference / secret-bearing |
| `REDIS_URL` | `${{redis.REDIS_URL}}` | Reference / secret-bearing |
| `CELERY_BROKER_URL` | `${{redis.REDIS_URL}}` | Reference / secret-bearing |
| `CELERY_RESULT_BACKEND` | `${{redis.REDIS_URL}}` | Reference / secret-bearing |
| `STORAGE_ENDPOINT_URL` | `http://${{minio.RAILWAY_PRIVATE_DOMAIN}}:9000` | Private-network configuration |
| `YOUTUBE_OAUTH_REDIRECT_URI` | Exact API public callback URL; see the next section | Configuration |

Railway PostgreSQL exposes `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, and `PGDATABASE`; composing the SQLAlchemy `postgresql+psycopg` URL from those references preserves the repository's async-driver requirement.[2] Railway Redis exposes `REDIS_URL`, which should be shared by the API and Celery Worker.[6]

### Worker service reference variables

Set the same values in the `worker` service, except it does not need `YOUTUBE_OAUTH_REDIRECT_URI`. The Worker must have `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `STORAGE_ENDPOINT_URL`, the storage access secrets, OpenAI secret, and YouTube provider secrets so queued workflow and publishing work uses the same durable state.

### MinIO and MinIO-init variables

The `minio` service receives `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` only. The `minio-init` service receives `STORAGE_ENDPOINT_URL`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, and `STORAGE_SECRET_KEY`. Set its endpoint to `http://${{minio.RAILWAY_PRIVATE_DOMAIN}}:9000`.

## Production YouTube OAuth redirect URI

After the `api` service has a generated Railway domain, copy the real domain and configure the exact callback in **both** locations:

1. In Google Cloud Console, add this exact value to the OAuth Web Client's authorized redirect URIs:

   ```text
   https://<api-public-domain>/publishing/connections/youtube/callback
   ```

2. Set `YOUTUBE_OAUTH_REDIRECT_URI` on the Railway `api` service to the same exact value.

Do not use the earlier localhost redirect URI in production. Do not put an OAuth client secret, authorization code, access token, refresh token, or encryption key into GitHub, documentation, logs, or chat.

## Deployment and safety sequence

1. Deploy `postgres`, `redis`, and `minio`; confirm MinIO has its `/data` volume attached.
2. Add the shared and service variables. Enter all secrets only in Railway, then seal them.
3. Deploy `minio-init` and confirm its one-time bucket creation succeeds.
4. Deploy `api`, confirm migrations and `/health` pass, then generate its public domain.
5. Register the exact generated API callback URL in Google Cloud and set `YOUTUBE_OAUTH_REDIRECT_URI` accordingly.
6. Deploy `worker` and verify it remains healthy and connected to Redis.
7. Stop here. Keep `AI_VIDEO_OS_RUN_PRODUCTION_E2E=false`; do not begin OAuth authorization, YouTube upload, or Production E2E without a separate approval.

## Operational limitations

MinIO is private in this design. As a result, direct browser use of S3 presigned URLs requires a later, explicitly approved public storage or proxy design. This deployment uses the API as the public entry point and keeps raw object storage inaccessible from the internet by default.

## References

[1]: https://docs.railway.com/guides/docker-compose "Railway: Deploy a Docker Compose App to Production"
[2]: https://docs.railway.com/databases/postgresql "Railway PostgreSQL"
[3]: https://docs.railway.com/guides/cron-workers-queues "Railway Background Workers and Queues"
[4]: https://docs.railway.com/deployments/monorepo "Railway Monorepo Deployment"
[5]: https://docs.railway.com/variables "Railway Variables and Sealed Variables"
[6]: https://docs.railway.com/databases/redis "Railway Redis"
