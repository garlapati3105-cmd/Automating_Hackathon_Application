from __future__ import annotations

import os
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class UserProfile(BaseModel):
    """
    Represents a user's registration details and profile information.
    Used to automatically populate forms in future automation modules.
    """

    full_name: str
    email: str
    phone: str
    college: str
    degree: str
    branch: str
    graduation_year: int
    github: str
    linkedin: str
    portfolio: Optional[str] = None
    resume_path: str

    @field_validator(
        "full_name",
        "email",
        "phone",
        "college",
        "degree",
        "branch",
        "github",
        "linkedin",
        "resume_path",
        mode="before",
    )
    @classmethod
    def strip_and_ensure_non_empty(cls, v: Any, info: Any) -> str:
        """Strip whitespace and raise ValueError if the field is empty."""
        if v is None:
            raise ValueError("Field is required and cannot be null.")
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        if not v:
            raise ValueError(f"Field '{info.field_name}' must be a non-empty string.")
        return v

    @field_validator("portfolio", mode="before")
    @classmethod
    def strip_optional_string(cls, v: Any) -> Optional[str]:
        """Strip whitespace from optional portfolio string."""
        if v is None:
            return None
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        return v if v else None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Verify that the email format is correct."""
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format.")
        return v

    @field_validator("github")
    @classmethod
    def validate_github(cls, v: str) -> str:
        """Verify that the GitHub URL is valid."""
        v_lower = v.lower()
        if "github.com/" not in v_lower:
            raise ValueError("Invalid GitHub URL format. Must contain github.com")
        
        parts = v_lower.split("github.com/")
        if len(parts) < 2 or not parts[1].strip():
            raise ValueError("Invalid GitHub URL. Missing username.")
        return v

    @field_validator("linkedin")
    @classmethod
    def validate_linkedin(cls, v: str) -> str:
        """Verify that the LinkedIn URL is valid."""
        v_lower = v.lower()
        if "linkedin.com/" not in v_lower:
            raise ValueError("Invalid LinkedIn URL format. Must contain linkedin.com")
        
        parts = v_lower.split("linkedin.com/")
        if len(parts) < 2 or not parts[1].strip():
            raise ValueError("Invalid LinkedIn URL. Missing profile identifier.")
        return v

    @field_validator("resume_path")
    @classmethod
    def validate_resume_path(cls, v: str) -> str:
        """Verify that the resume file exists on disk."""
        # Check standard path
        if os.path.exists(v):
            return v
        
        # Fallback to check relative to 'profile/' directory
        fallback = os.path.join("profile", os.path.basename(v))
        if os.path.exists(fallback):
            return v
        
        # Check relative fallback directly
        fallback_dir = os.path.join("profile", v)
        if os.path.exists(fallback_dir):
            return v
            
        raise ValueError(f"Resume file does not exist: {v}")
