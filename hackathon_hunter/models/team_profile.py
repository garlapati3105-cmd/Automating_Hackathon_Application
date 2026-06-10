from __future__ import annotations

import re
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class TeamMemberProfile(BaseModel):
    """
    Represents a member of a team.
    """
    full_name: str
    email: str
    phone: Optional[str] = None
    college: Optional[str] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    graduation_year: Optional[int] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None
    portfolio: Optional[str] = None
    resume_path: Optional[str] = None

    @field_validator("full_name", "email", mode="before")
    @classmethod
    def strip_and_ensure_non_empty(cls, v: Any, info: Any) -> str:
        if v is None:
            raise ValueError(f"Field '{info.field_name}' is required.")
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        if not v:
            raise ValueError(f"Field '{info.field_name}' cannot be empty.")
        return v

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format.")
        return v


class TeamProfile(BaseModel):
    """
    Represents a team profile, preparing the architecture for team registrations.
    """
    team_name: str
    team_size: int = 1
    members: List[TeamMemberProfile] = Field(default_factory=list)

    @field_validator("team_name", mode="before")
    @classmethod
    def strip_team_name(cls, v: Any) -> str:
        if v is None:
            raise ValueError("team_name is required.")
        v = str(v).strip()
        if not v:
            raise ValueError("team_name cannot be empty.")
        return v

    @field_validator("team_size")
    @classmethod
    def validate_team_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("team_size must be at least 1.")
        return v
