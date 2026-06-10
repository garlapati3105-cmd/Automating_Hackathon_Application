from __future__ import annotations

import logging
from typing import Optional

from hackathon_hunter.automation.form_detector import FieldMetadata

logger = logging.getLogger(__name__)


class FieldMapper:
    """
    Maps registration form fields semantically to UserProfile attributes.
    """

    def map_to_profile_field(self, field: FieldMetadata) -> Optional[str]:
        """
        Takes a FieldMetadata and returns the matching UserProfile field name,
        or None if no match is found.
        """
        combined = f"{field.label_text} {field.placeholder_text} {field.identifier}".lower().strip()

        # GitHub
        if "github" in combined or "git " in combined:
            return "github"

        # LinkedIn
        if "linkedin" in combined or "ln " in combined:
            return "linkedin"

        # Resume/CV
        if "resume" in combined or " cv" in combined or "cv " in combined:
            return "resume_path"

        # Portfolio/Website
        if "portfolio" in combined or "website" in combined or "personal site" in combined:
            return "portfolio"

        # Email
        if "email" in combined or "mail" in combined:
            return "email"

        # Phone / Mobile
        if "phone" in combined or "mobile" in combined or "contact" in combined or "tel" in combined:
            return "phone"

        # Full Name
        if "name" in combined:
            # Avoid mapping if it's a team name or college name
            if "team" not in combined and "college" not in combined and "university" not in combined:
                return "full_name"

        # College / University
        if "college" in combined or "university" in combined or "institute" in combined or "school" in combined:
            return "college"

        # Degree
        if "degree" in combined or "course" in combined or "qualification" in combined:
            return "degree"

        # Branch
        if "branch" in combined or "stream" in combined or "specialization" in combined or "major" in combined:
            return "branch"

        # Graduation Year
        if "graduation" in combined or "grad year" in combined or "passing year" in combined or "year of passing" in combined:
            return "graduation_year"

        return None
