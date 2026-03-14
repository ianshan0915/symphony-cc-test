"""Thread SQLAlchemy model and Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import GUID, JSONType

# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class Thread(Base):
    """Conversation thread."""

    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    assistant_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    metadata_: Mapped[dict] = mapped_column(  # type: ignore[assignment]
        "metadata", JSONType(), nullable=False, default=dict
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    messages: Mapped[List["Message"]] = relationship(  # noqa: F821
        "Message",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Thread id={self.id} title={self.title!r}>"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ThreadCreate(BaseModel):
    """Schema for creating a thread."""

    title: Optional[str] = None
    assistant_id: str = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ThreadUpdate(BaseModel):
    """Schema for updating a thread."""

    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageOut(BaseModel):
    """Nested message representation for thread detail responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    role: str
    content: str
    tool_calls: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime


class ThreadOut(BaseModel):
    """Schema for thread responses (list view)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: Optional[str]
    assistant_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class ThreadDetail(ThreadOut):
    """Schema for thread detail response (includes messages)."""

    messages: List[MessageOut] = Field(default_factory=list)


class ThreadListResponse(BaseModel):
    """Paginated response for thread list."""

    threads: List[ThreadOut]
    total: int
    offset: int
    limit: int


class DeleteResponse(BaseModel):
    """Response for delete operations."""

    ok: bool = True
    detail: str = "Thread deleted"
