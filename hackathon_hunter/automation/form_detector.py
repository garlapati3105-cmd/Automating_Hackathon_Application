from __future__ import annotations

import logging
from enum import Enum
from typing import Any, List, Optional
from playwright.sync_api import Page, Locator

logger = logging.getLogger(__name__)


class FieldCategory(str, Enum):
    PROFILE = "PROFILE"
    QUESTION = "QUESTION"
    TEAM = "TEAM"
    UNKNOWN = "UNKNOWN"


class FieldMetadata:
    """
    Holds metadata and classification for a detected form field.
    """

    def __init__(
        self,
        identifier: str,
        field_type: str,
        label_text: str,
        placeholder_text: str,
        required: bool,
        category: FieldCategory,
        locator: Locator,
    ) -> None:
        self.identifier = identifier
        self.field_type = field_type
        self.label_text = label_text
        self.placeholder_text = placeholder_text
        self.required = required
        self.category = category
        self.locator = locator

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary format for JSON export."""
        return {
            "identifier": self.identifier,
            "type": self.field_type,
            "label": self.label_text,
            "placeholder": self.placeholder_text,
            "required": self.required,
            "category": self.category.value,
        }


class FormDetector:
    """
    Detects and extracts metadata from form fields on a registration page.
    """

    def detect_fields(self, page: Page) -> List[FieldMetadata]:
        """
        Scans the page for standard input, textarea, and select elements,
        extracting metadata and classifying their category.
        """
        detected_fields: List[FieldMetadata] = []

        # Target standard form elements
        elements = page.locator("input, textarea, select").all()
        logger.info("Found %d raw form elements on page.", len(elements))

        for el in elements:
            # Check if element is visible and not hidden/disabled/submit type
            el_type = el.get_attribute("type") or ""
            if el_type in ("submit", "button", "hidden", "image"):
                continue

            tag_name = el.evaluate("el => el.tagName.toLowerCase()")
            field_type = tag_name if tag_name != "input" else (el_type or "text")

            # Extract identifier (id, name, or placeholder/aria label fallback)
            el_id = el.get_attribute("id") or ""
            el_name = el.get_attribute("name") or ""
            identifier = el_id or el_name or f"xpath={el.evaluate('el => el.name || el.id || el.tagName')}"

            # Extract required status
            required = el.get_attribute("required") is not None or el.evaluate("el => el.required")

            # Extract placeholder
            placeholder = el.get_attribute("placeholder") or ""

            # Extract Label Text using heuristics:
            label_text = self._find_label_for_element(page, el, el_id)

            # Classify field
            category = self._classify_field(label_text, placeholder, identifier, field_type)

            meta = FieldMetadata(
                identifier=identifier,
                field_type=field_type,
                label_text=label_text,
                placeholder_text=placeholder,
                required=required,
                category=category,
                locator=el,
            )
            detected_fields.append(meta)

        return detected_fields

    def _find_label_for_element(self, page: Page, el: Locator, el_id: str) -> str:
        """
        Finds the associated label text for an element using various heuristics.
        """
        # 1. Label tag with 'for' attribute matching id
        if el_id:
            label_for = page.locator(f"label[for='{el_id}']")
            if label_for.count() > 0:
                text = label_for.first.text_content() or ""
                if text.strip():
                    return text.strip()

        # 2. Parent label element wrapping the input
        parent_label = el.locator("xpath=ancestor::label")
        if parent_label.count() > 0:
            text = parent_label.first.text_content() or ""
            if text.strip():
                return text.strip()

        # 3. Aria-label / Aria-labelledby
        aria_label = el.get_attribute("aria-label") or ""
        if aria_label.strip():
            return aria_label.strip()

        # 4. Check for preceding text or label element close in DOM
        # Evaluate standard browser query for closest text
        closest_text = el.evaluate(
            """el => {
                // Look for preceding sibling labels
                let sibling = el.previousElementSibling;
                while (sibling) {
                    if (sibling.tagName.toLowerCase() === 'label' || sibling.innerText) {
                        return sibling.innerText || sibling.textContent;
                    }
                    sibling = sibling.previousElementSibling;
                }
                // Check closest div preceding text
                let parent = el.parentElement;
                if (parent) {
                    let text = parent.innerText || parent.textContent;
                    if (text && text.length < 100) {
                        return text;
                    }
                }
                return "";
            }"""
        )
        if closest_text.strip():
            # Clean up nested child inputs/texts from label if necessary
            # For simplicity, strip trailing/leading spaces and return
            cleaned = closest_text.replace("\n", " ").strip()
            if cleaned:
                return cleaned

        # 5. Fallback to name/id
        return el.get_attribute("name") or el.get_attribute("id") or ""

    def _classify_field(self, label: str, placeholder: str, identifier: str, field_type: str) -> FieldCategory:
        """
        Classifies a field based on its text, label, placeholder, and attribute markers.
        """
        combined = f"{label} {placeholder} {identifier}".lower()

        # 1. Check QUESTION category first (essay/long form questions)
        question_words = [
            "why", "describe", "explain", "interest", "project", 
            "technologies", "motivation", "tell us", "about yourself",
            "experience", "idea", "skills", "details"
        ]
        if "?" in label or len(label) > 40 or any(q in combined for q in question_words) or field_type == "textarea":
            # Avoid profile fields (e.g. "tell us your github" or "GitHub Profile URL") classifying as question
            profile_override_words = ["github", "linkedin", "resume", "portfolio", "email", "phone"]
            if not any(p in combined for p in profile_override_words):
                return FieldCategory.QUESTION

        # 2. Check TEAM category
        team_words = ["team", "group", "co-founder", "partner", "member"]
        if any(t in combined for t in team_words):
            return FieldCategory.TEAM

        # 3. Check PROFILE category
        profile_words = [
            "name", "email", "mail", "phone", "contact", "mobile", "number", "tel",
            "college", "university", "school", "institution", "degree", "course",
            "branch", "graduation", "grad year", "passing year", "github", "linkedin",
            "portfolio", "website", "resume", "cv", "first name", "last name", "branch"
        ]
        if any(p in combined for p in profile_words):
            return FieldCategory.PROFILE

        return FieldCategory.UNKNOWN
