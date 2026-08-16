# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app \
    && useradd --system --gid app --create-home app

COPY pyproject.toml README.md ./
COPY apps/__init__.py apps/__init__.py
# The API imports Celery task definitions to enqueue workflow and publishing jobs.
# Copying this module does not start a worker process; that remains the separate
# Railway Worker service defined in deploy/railway/worker.
COPY apps/api apps/api
COPY apps/worker apps/worker
COPY alembic.ini alembic.ini
COPY migrations migrations

RUN pip install --no-cache-dir .

USER app

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
