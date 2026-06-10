from __future__ import annotations

import logging
from typing import List

from hackathon_hunter.automation.form_detector import FieldMetadata, FieldCategory

logger = logging.getLogger(__name__)


class ReadinessAnalyzer:
    """
    Analyzes detected registration form fields to evaluate automation readiness.
    """

    def analyze(self, fields: List[FieldMetadata]) -> dict:
        """
        Calculates field statistics, automation score, and human review necessity.
        """
        profile_count = 0
        question_count = 0
        team_count = 0
        consent_count = 0
        unknown_count = 0

        for field in fields:
            if field.category == FieldCategory.PROFILE:
                profile_count += 1
            elif field.category == FieldCategory.QUESTION:
                question_count += 1
            elif field.category == FieldCategory.TEAM:
                team_count += 1
            elif field.category == FieldCategory.CONSENT:
                consent_count += 1
            elif field.category == FieldCategory.UNKNOWN:
                unknown_count += 1

        total = len(fields)
        if total == 0:
            score = 0
        else:
            # Formula: start at 100, apply deductions
            score = 100 - (question_count * 8) - (unknown_count * 5) - (team_count * 5) - (consent_count * 2)
            score = max(0, min(100, score))

        # Human review is required if there is any question, team, or unknown fields,
        # or if the score is below 85.
        requires_human_review = (
            question_count > 0
            or team_count > 0
            or unknown_count > 0
            or score < 85
        )

        return {
            "profile_count": profile_count,
            "question_count": question_count,
            "team_count": team_count,
            "consent_count": consent_count,
            "unknown_count": unknown_count,
            "automation_score": score,
            "requires_human_review": requires_human_review,
        }
