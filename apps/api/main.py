"""ASGI entry point for uvicorn."""

from apps.api.application import create_app

app = create_app()
