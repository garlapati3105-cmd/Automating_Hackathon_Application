"""hackathon_hunter.automation package."""

from hackathon_hunter.automation.playwright_manager import PlaywrightManager
from hackathon_hunter.automation.form_detector import FormDetector, FieldMetadata, FieldCategory, QuestionComplexity
from hackathon_hunter.automation.field_mapper import FieldMapper
from hackathon_hunter.automation.form_filler import FormFiller
from hackathon_hunter.automation.page_analyzer import PageAnalyzer
from hackathon_hunter.automation.readiness_analyzer import ReadinessAnalyzer
from hackathon_hunter.automation.registration_report import RegistrationReport
from hackathon_hunter.automation.approval_engine import ApprovalEngine, ApprovalStatus

__all__ = [
    "PlaywrightManager",
    "FormDetector",
    "FieldMetadata",
    "FieldCategory",
    "QuestionComplexity",
    "FieldMapper",
    "FormFiller",
    "PageAnalyzer",
    "ReadinessAnalyzer",
    "RegistrationReport",
    "ApprovalEngine",
    "ApprovalStatus",
]
