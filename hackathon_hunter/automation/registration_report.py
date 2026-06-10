from __future__ import annotations

import json
from typing import Any, Dict, List


class RegistrationReport:
    """
    Generates structured reports for form automation readiness.
    """

    def __init__(
        self,
        hackathon_name: str,
        registration_url: str,
        field_statistics: Dict[str, int],
        automation_score: int,
        requires_human_review: bool,
        analysis_status: str = "ANALYZED",
        questions: List[Dict[str, str]] = None,
    ) -> None:
        self.hackathon_name = hackathon_name
        self.registration_url = registration_url
        self.field_statistics = field_statistics
        self.automation_score = automation_score
        self.requires_human_review = requires_human_review
        self.analysis_status = analysis_status
        self.questions = questions or []

    @property
    def classification(self) -> str:
        """
        Returns the readiness classification based on score.
        """
        if self.automation_score >= 85:
            return "HIGH"
        elif self.automation_score >= 50:
            return "MEDIUM"
        else:
            return "LOW"

    @property
    def recommendation(self) -> str:
        """
        Returns the automation recommendation based on classification.
        """
        cls = self.classification
        if cls == "HIGH":
            return "AUTO_FILL_ONLY"
        elif cls == "MEDIUM":
            return "AUTO_FILL_AND_REVIEW"
        else:
            return "MANUAL_ONLY"

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to JSON serializable dictionary."""
        return {
            "hackathon_name": self.hackathon_name,
            "registration_url": self.registration_url,
            "field_statistics": self.field_statistics,
            "automation_score": self.automation_score,
            "requires_human_review": self.requires_human_review,
            "readiness_classification": self.classification,
            "automation_recommendation": self.recommendation,
            "analysis_status": self.analysis_status,
            "questions": self.questions,
        }

    def to_json(self, indent: int = 4) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
