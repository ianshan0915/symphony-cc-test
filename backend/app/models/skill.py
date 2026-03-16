"""User-created skill SQLAlchemy model and Pydantic schemas."""

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import GUID, JSONType

# ---------------------------------------------------------------------------
# Name validation per agentskills.io spec
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")


def validate_skill_name(name: str) -> str:
    """Validate a skill name per the agentskills.io specification.

    Rules:
    - Lowercase letters, digits, and hyphens only
    - Must start with a letter and end with a letter or digit
    - No consecutive hyphens
    - Max 64 characters
    """
    if not name or len(name) > 64:
        raise ValueError("Skill name must be between 1 and 64 characters")
    if "--" in name:
        raise ValueError("Skill name must not contain consecutive hyphens")
    if not _NAME_RE.match(name):
        raise ValueError(
            "Skill name must start with a lowercase letter, end with a letter or digit, "
            "and contain only lowercase letters, digits, and hyphens"
        )
    return name


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class Skill(Base):
    """User-created or system-wide agent skill stored in the database."""

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONType(), nullable=False, default=dict
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship to User (optional, for eager loading)
    user = relationship("User", lazy="select")

    def __repr__(self) -> str:
        return f"<Skill id={self.id} name={self.name!r} user_id={self.user_id}>"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SkillCreate(BaseModel):
    """Schema for creating a user skill."""

    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=1024)
    instructions: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_skill_name(v)


class SkillUpdate(BaseModel):
    """Schema for updating a user skill."""

    name: Optional[str] = Field(None, min_length=1, max_length=64)
    description: Optional[str] = Field(None, min_length=1, max_length=1024)
    instructions: Optional[str] = Field(None, min_length=1)
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_skill_name(v)
        return v


class SkillOut(BaseModel):
    """Schema for skill responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    name: str
    description: str
    instructions: str
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SkillListResponse(BaseModel):
    """Paginated response for skill list."""

    skills: List[SkillOut]
    total: int
    offset: int
    limit: int
