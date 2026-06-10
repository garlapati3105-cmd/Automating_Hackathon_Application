"""hackathon_hunter.automation package."""

from hackathon_hunter.automation.playwright_manager import PlaywrightManager
from hackathon_hunter.automation.form_detector import FormDetector, FieldMetadata, FieldCategory
from hackathon_hunter.automation.field_mapper import FieldMapper
from hackathon_hunter.automation.form_filler import FormFiller
from hackathon_hunter.automation.page_analyzer import PageAnalyzer

__all__ = [
    "PlaywrightManager",
    "FormDetector",
    "FieldMetadata",
    "FieldCategory",
    "FieldMapper",
    "FormFiller",
    "PageAnalyzer",
]
