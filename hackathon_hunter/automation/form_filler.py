from __future__ import annotations

import logging
import os
from typing import List, Tuple

from hackathon_hunter.automation.field_mapper import FieldMapper
from hackathon_hunter.automation.form_detector import FieldCategory, FieldMetadata
from hackathon_hunter.models.profile import UserProfile

logger = logging.getLogger(__name__)


class FormFiller:
    """
    Fills form fields using UserProfile data. Handles dry-run configurations
    and prevents overwriting pre-populated fields.
    """

    def __init__(self, mapper: FieldMapper) -> None:
        self.mapper = mapper

    def fill_form(
        self,
        fields: List[FieldMetadata],
        profile: UserProfile,
        dry_run: bool = False,
    ) -> Tuple[List[FieldMetadata], List[FieldMetadata]]:
        """
        Processes detected fields, maps them, and fills PROFILE category fields.
        Returns a tuple of (filled_fields, skipped_fields).
        """
        filled_fields: List[FieldMetadata] = []
        skipped_fields: List[FieldMetadata] = []

        for field in fields:
            logger.info("Field detected: label='%s', id/name='%s', category='%s'",
                        field.label_text, field.identifier, field.category.value)

            # Check if field is already populated
            is_populated = False
            if not dry_run:
                try:
                    val = field.locator.input_value()
                    if val and val.strip():
                        is_populated = True
                except Exception:
                    # Select dropdowns or elements that don't support input_value()
                    pass

            if is_populated:
                logger.info("Skipping field '%s': already populated with value.", field.label_text)
                skipped_fields.append(field)
                continue

            # Only fill PROFILE fields
            if field.category != FieldCategory.PROFILE:
                logger.info("Skipping field '%s': not a PROFILE category field (%s).",
                            field.label_text, field.category.value)
                skipped_fields.append(field)
                continue

            # Find matching profile attribute
            profile_attr = self.mapper.map_to_profile_field(field)
            if not profile_attr:
                logger.info("Skipping profile field '%s': could not map to profile attribute.", field.label_text)
                skipped_fields.append(field)
                continue

            # Get value from profile
            value = getattr(profile, profile_attr, None)
            if value is None:
                logger.info("Skipping field '%s': value for '%s' is null in profile.", field.label_text, profile_attr)
                skipped_fields.append(field)
                continue

            # Log attempt
            if dry_run:
                logger.info("[Dry Run] Would fill field '%s' with value '%s'", field.label_text, value)
                filled_fields.append(field)
                continue

            # Fill element using Playwright locator API
            try:
                if field.field_type == "select":
                    # For select, try to match by value first, then label
                    try:
                        field.locator.select_option(value=str(value))
                    except Exception:
                        field.locator.select_option(label=str(value))
                elif field.field_type == "file":
                    # Set file upload for resume
                    if profile_attr == "resume_path" and os.path.exists(str(value)):
                        field.locator.set_input_files(str(value))
                    else:
                        # Fallback for relative paths
                        fallback = os.path.join("profile", os.path.basename(str(value)))
                        if os.path.exists(fallback):
                            field.locator.set_input_files(fallback)
                        else:
                            fallback_dir = os.path.join("profile", str(value))
                            if os.path.exists(fallback_dir):
                                field.locator.set_input_files(fallback_dir)
                            else:
                                raise FileNotFoundError(f"File not found: {value}")
                else:
                    # Standard input typing
                    field.locator.fill(str(value))

                logger.info("Successfully filled field '%s' with profile data.", field.label_text)
                filled_fields.append(field)

            except Exception as exc:
                logger.error("Failed to fill field '%s': %s", field.label_text, exc)
                skipped_fields.append(field)

        return filled_fields, skipped_fields
