"""Persistence model for external publication requests."""

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.assets.models import Asset
from apps.api.database import Base


class PublicationStatus(str, enum.Enum):
    """Lifecycle states of one publishing request."""

    PENDING = "pending"
    QUEUED = "queued"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class PublishingConnectionStatus(str, enum.Enum):
    """Lifecycle states for an operator-managed provider connection."""

    PENDING = "pending"
    CONNECTED = "connected"
    FAILED = "failed"
    DISCONNECTED = "disconnected"


class Publication(Base):
    """Track publication of an existing asset through a named provider."""

    __tablename__ = "publications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[PublicationStatus] = mapped_column(
        Enum(PublicationStatus), default=PublicationStatus.PENDING, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    asset: Mapped[Asset] = relationship()


class PublishingConnection(Base):
    """Non-secret metadata for one operator-level publishing connection."""

    __tablename__ = "publishing_connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[PublishingConnectionStatus] = mapped_column(
        Enum(PublishingConnectionStatus),
        default=PublishingConnectionStatus.PENDING,
        nullable=False,
    )
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PublishingCredential(Base):
    """Encrypted provider credential kept separate from connection metadata."""

    __tablename__ = "publishing_credentials"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("publishing_connections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class PublishingOAuthState(Base):
    """Hashed, expiring, single-use OAuth state record."""

    __tablename__ = "publishing_oauth_states"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("publishing_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
