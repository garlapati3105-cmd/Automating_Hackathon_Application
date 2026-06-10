from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from hackathon_hunter.models.profile import UserProfile


class ProfileService:
    """
    Service for loading, saving, and validating user profiles.
    """

    def __init__(self, default_path: str | Path = "profile/profile.json") -> None:
        self.default_path = Path(default_path)

    def load_profile(self, path: str | Path | None = None) -> UserProfile:
        """
        Load the user profile from a JSON file.

        Args:
            path: Optional override path. Defaults to self.default_path.

        Returns:
            A UserProfile instance.

        Raises:
            FileNotFoundError: If the profile JSON file is missing.
            ValueError: If the file is not valid JSON or fails schema validation.
        """
        target_path = Path(path) if path is not None else self.default_path
        if not target_path.exists():
            raise FileNotFoundError(f"Profile file not found at: {target_path}")

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Profile file at {target_path} is not valid JSON: {exc}")

        try:
            return UserProfile(**data)
        except ValidationError as exc:
            # Format Pydantic errors to make them cleaner
            errors = []
            for err in exc.errors():
                loc = " -> ".join(str(loc) for loc in err["loc"])
                msg = err["msg"]
                errors.append(f"[{loc}]: {msg}")
            raise ValueError("Profile validation failed:\n" + "\n".join(errors))

    def save_profile(self, profile: UserProfile, path: str | Path | None = None) -> None:
        """
        Save the UserProfile back to a JSON file.

        Args:
            profile: The UserProfile instance to serialize.
            path: Optional override path. Defaults to self.default_path.
        """
        target_path = Path(path) if path is not None else self.default_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=4)

    def validate_profile(self, profile: UserProfile) -> bool:
        """
        Perform validation checks on a UserProfile.

        Validation rules:
        - Required fields present (enforced by Pydantic model structure).
        - Email format valid (enforced by UserProfile email validator).
        - Resume file exists (enforced by UserProfile resume_path validator).
        - GitHub URL valid (enforced by UserProfile github validator).
        - LinkedIn URL valid (enforced by UserProfile linkedin validator).

        Returns:
            True if profile is valid.

        Raises:
            ValueError: If any validation rule is violated.
        """
        # Trigger model validation again to ensure runtime consistency (e.g. if files were deleted)
        try:
            # Re-validate fields using model_validate
            UserProfile.model_validate(profile.model_dump())
        except ValidationError as exc:
            errors = []
            for err in exc.errors():
                loc = " -> ".join(str(loc) for loc in err["loc"])
                msg = err["msg"]
                errors.append(f"[{loc}]: {msg}")
            raise ValueError("Profile validation failed:\n" + "\n".join(errors))

        # Explicitly double-check fields again for safety
        required_fields = [
            "full_name",
            "email",
            "phone",
            "college",
            "degree",
            "branch",
            "graduation_year",
            "github",
            "linkedin",
            "resume_path",
        ]
        for field in required_fields:
            val = getattr(profile, field, None)
            if val is None or (isinstance(val, str) and not val.strip()):
                raise ValueError(f"Missing required field: {field}")

        # Validate Email
        email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_regex, profile.email):
            raise ValueError("Invalid email format.")

        # Validate GitHub URL
        if "github.com/" not in profile.github.lower():
            raise ValueError("Invalid GitHub URL format. Must contain github.com")

        # Validate LinkedIn URL
        if "linkedin.com/" not in profile.linkedin.lower():
            raise ValueError("Invalid LinkedIn URL format. Must contain linkedin.com")

        # Validate Resume path on filesystem
        if not os.path.exists(profile.resume_path):
            # Try fallback relative to profile directory
            fallback = os.path.join("profile", os.path.basename(profile.resume_path))
            if not os.path.exists(fallback):
                fallback_dir = os.path.join("profile", profile.resume_path)
                if not os.path.exists(fallback_dir):
                    raise ValueError(f"Resume file does not exist: {profile.resume_path}")

        return True
