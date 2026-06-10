from __future__ import annotations

import json
from pathlib import Path
from pydantic import ValidationError

from hackathon_hunter.models.team_profile import TeamProfile


class TeamProfileService:
    """
    Service for loading, saving, and validating team profiles.
    """

    def __init__(self, default_path: str | Path = "profile/team.json") -> None:
        self.default_path = Path(default_path)

    def load_team_profile(self, path: str | Path | None = None) -> TeamProfile:
        """
        Load the team profile from a JSON file.

        Args:
            path: Optional override path. Defaults to self.default_path.

        Returns:
            A TeamProfile instance.

        Raises:
            FileNotFoundError: If the team JSON file is missing.
            ValueError: If the file is not valid JSON or fails schema validation.
        """
        target_path = Path(path) if path is not None else self.default_path
        if not target_path.exists():
            raise FileNotFoundError(f"Team profile file not found at: {target_path}")

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Team profile file at {target_path} is not valid JSON: {exc}")

        try:
            return TeamProfile(**data)
        except ValidationError as exc:
            errors = []
            for err in exc.errors():
                loc = " -> ".join(str(loc) for loc in err["loc"])
                msg = err["msg"]
                errors.append(f"[{loc}]: {msg}")
            raise ValueError("Team profile validation failed:\n" + "\n".join(errors))

    def save_team_profile(self, team: TeamProfile, path: str | Path | None = None) -> None:
        """
        Save the TeamProfile back to a JSON file.

        Args:
            team: The TeamProfile instance to serialize.
            path: Optional override path. Defaults to self.default_path.
        """
        target_path = Path(path) if path is not None else self.default_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(team.model_dump(), f, indent=4)

    def validate_team_profile(self, team: TeamProfile) -> bool:
        """
        Perform validation checks on a TeamProfile.

        Returns:
            True if the team profile is valid.

        Raises:
            ValueError: If any validation rule is violated.
        """
        try:
            TeamProfile.model_validate(team.model_dump())
        except ValidationError as exc:
            errors = []
            for err in exc.errors():
                loc = " -> ".join(str(loc) for loc in err["loc"])
                msg = err["msg"]
                errors.append(f"[{loc}]: {msg}")
            raise ValueError("Team profile validation failed:\n" + "\n".join(errors))

        if not team.team_name.strip():
            raise ValueError("Team name cannot be empty.")

        if team.team_size < 1:
            raise ValueError("Team size must be at least 1.")

        return True
