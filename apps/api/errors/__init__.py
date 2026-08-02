"""Application error contracts."""

from apps.api.errors.exceptions import ApplicationError
from apps.api.errors.handlers import register_error_handlers

__all__ = ["ApplicationError", "register_error_handlers"]
