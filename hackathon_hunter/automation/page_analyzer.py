from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from hackathon_hunter.automation.form_detector import FieldCategory, FieldMetadata

logger = logging.getLogger(__name__)


class PageAnalyzer:
    """
    Analyzes detected/filled form fields, generates human-readable reports,
    and exports JSON snapshots to snapshots/form_analysis.json.
    """

    def generate_report(
        self,
        url: str,
        detected_fields: List[FieldMetadata],
        filled_fields: List[FieldMetadata],
        skipped_fields: List[FieldMetadata],
        execution_time: float,
        dry_run: bool = False,
    ) -> str:
        """
        Generates a human-readable text report summarizing the form analysis.
        """
        # Count categories
        cat_counts = {cat: 0 for cat in FieldCategory}
        for field in detected_fields:
            cat_counts[field.category] += 1

        if dry_run:
            lines = [
                f"Detected Fields: {len(detected_fields)}",
                "",
                f"PROFILE: {cat_counts[FieldCategory.PROFILE]}",
                f"QUESTION: {cat_counts[FieldCategory.QUESTION]}",
                f"TEAM: {cat_counts[FieldCategory.TEAM]}",
                f"UNKNOWN: {cat_counts[FieldCategory.UNKNOWN]}",
                "",
                "Would Fill:"
            ]
            for f in filled_fields:
                lines.append(f"* {f.label_text or f.identifier}")

            lines.append("")
            lines.append("Requires Human Input:")
            question_fields = [f for f in detected_fields if f.category == FieldCategory.QUESTION]
            for f in question_fields:
                lines.append(f"* {f.label_text or f.identifier}")
        else:
            lines = [
                "Registration Analysis",
                "",
                f"Total Fields: {len(detected_fields)}",
                "",
                f"PROFILE: {cat_counts[FieldCategory.PROFILE]}",
                f"QUESTION: {cat_counts[FieldCategory.QUESTION]}",
                f"TEAM: {cat_counts[FieldCategory.TEAM]}",
                f"UNKNOWN: {cat_counts[FieldCategory.UNKNOWN]}",
                "",
                f"Filled: {len(filled_fields)}",
                f"Skipped: {len(skipped_fields)}",
                "",
                f"Execution Time: {execution_time:.1f} seconds"
            ]
        return "\n".join(lines)

    def export_snapshot(
        self,
        url: str,
        detected_fields: List[FieldMetadata],
        filled_fields: List[FieldMetadata],
        skipped_fields: List[FieldMetadata],
        execution_time: float,
        output_path: str | Path = "snapshots/form_analysis.json",
    ) -> None:
        """
        Saves a structured analysis JSON snapshot of all fields and execution summary.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        cat_counts = {cat.value: 0 for cat in FieldCategory}
        for field in detected_fields:
            cat_counts[field.category.value] += 1

        snapshot = {
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_fields": len(detected_fields),
                "profile_fields": cat_counts[FieldCategory.PROFILE.value],
                "question_fields": cat_counts[FieldCategory.QUESTION.value],
                "team_fields": cat_counts[FieldCategory.TEAM.value],
                "unknown_fields": cat_counts[FieldCategory.UNKNOWN.value],
                "filled": len(filled_fields),
                "skipped": len(skipped_fields),
                "execution_time_seconds": round(execution_time, 2),
            },
            "fields": [field.to_dict() for field in detected_fields],
        }

        logger.info("Exporting form analysis snapshot to %s", path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=4)
