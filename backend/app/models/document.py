"""Document SQLAlchemy model and Pydantic schemas for knowledge base."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import GUID, JSONType

# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class Document(Base):
    """Knowledge-base document with optional vector embedding."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # The ``embedding`` column is a pgvector ``vector(1536)`` type managed via
    # raw SQL in the migration.  SQLAlchemy doesn't need to map it for writes;
    # similarity searches use raw SQL as well.
    source: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    metadata_: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONType(), nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} title={self.title!r}>"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class DocumentCreate(BaseModel):
    """Schema for creating a document."""

    title: Optional[str] = None
    content: str
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""

    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentOut(BaseModel):
    """Schema for document responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: Optional[str] = None
    content: str
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class DocumentSearchResult(BaseModel):
    """A single result from a similarity search."""

    id: uuid.UUID
    title: Optional[str] = None
    content: str
    source: Optional[str] = None
    score: float = Field(description="Cosine similarity score (0-1, higher is more similar)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentSearchResponse(BaseModel):
    """Response wrapper for similarity search results."""

    query: str
    results: List[DocumentSearchResult]
    count: int
