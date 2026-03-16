"""FileArtifact SQLAlchemy model and Pydantic schemas.

Stores file artifacts created by the agent so they can be retrieved,
listed, and managed through the file tools.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import GUID, JSONType

# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class FileArtifact(Base):
    """A file artifact persisted by agent file tools."""

    __tablename__ = "file_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONType(), nullable=False, default=dict
    )
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_file_artifacts_thread_path", "thread_id", "file_path"),)

    def __repr__(self) -> str:
        return f"<FileArtifact id={self.id} path={self.file_path!r}>"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class FileArtifactCreate(BaseModel):
    """Schema for creating a file artifact."""

    thread_id: uuid.UUID
    file_path: str
    content: str = ""
    mime_type: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileArtifactOut(BaseModel):
    """Schema for file artifact responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    file_path: str
    content: str
    mime_type: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime
