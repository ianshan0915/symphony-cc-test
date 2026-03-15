"""Assistant configuration SQLAlchemy model and Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import GUID, JSONType

# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class Assistant(Base):
    """Agent / assistant configuration stored in the database."""

    __tablename__ = "assistants"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-4o")
    system_prompt: Mapped[Optional[str]] = mapped_column(String(10000), nullable=True)
    tools_enabled: Mapped[list] = mapped_column(  # type: ignore[type-arg]
        JSONType(), nullable=False, default=list
    )
    metadata_: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONType(), nullable=False, default=dict
    )
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Assistant id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AssistantCreate(BaseModel):
    """Schema for creating an assistant configuration."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    model: str = Field("gpt-4o", max_length=100)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    tools_enabled: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=200000)


class AssistantUpdate(BaseModel):
    """Schema for updating an assistant configuration."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    model: Optional[str] = Field(None, max_length=100)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    tools_enabled: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=200000)
    is_active: Optional[bool] = None


class AssistantOut(BaseModel):
    """Schema for assistant configuration responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    model: str
    system_prompt: Optional[str]
    tools_enabled: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    temperature: Optional[float]
    max_tokens: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssistantListResponse(BaseModel):
    """Paginated response for assistant list."""

    assistants: List[AssistantOut]
    total: int
    offset: int
    limit: int
