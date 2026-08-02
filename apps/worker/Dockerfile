# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system worker && useradd --system --gid worker --create-home worker

COPY pyproject.toml README.md ./
COPY apps/__init__.py apps/__init__.py
COPY apps/api apps/api
COPY apps/worker apps/worker
RUN pip install --no-cache-dir .

USER worker

CMD ["celery", "-A", "apps.worker.celery_app:celery_app", "worker", "--loglevel=INFO"]
