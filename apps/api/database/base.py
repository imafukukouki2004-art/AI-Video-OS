"""Shared SQLAlchemy declarative base for later domain tickets."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base metadata registry; TICKET-004 intentionally defines no domain models."""
