from __future__ import annotations

import json
import os
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from hackathon_hunter.automation import (
    FieldCategory,
    FieldMetadata,
    ReadinessAnalyzer,
    RegistrationReport,
    ApprovalEngine,
    ApprovalStatus,
    QuestionComplexity,
)
from hackathon_hunter.repositories.registration_analysis_repository import (
    RegistrationAnalysisRepository,
)


def test_readiness_analyzer_scoring():
    analyzer = ReadinessAnalyzer()

    # 1. High Score / Approves automatically
    # Profile: 10, Questions: 1 (deducts 8), Team: 0, Consent: 0, Unknown: 0 -> Score: 92
    fields = []
    for i in range(10):
        fields.append(FieldMetadata(f"p{i}", "text", "Name", "", False, FieldCategory.PROFILE, None))
    q_field = FieldMetadata("q1", "text", "Why join?", "", False, FieldCategory.QUESTION, None)
    q_field.question_complexity = QuestionComplexity.SIMPLE
    fields.append(q_field)

    res = analyzer.analyze(fields)
    assert res["automation_score"] == 92
    assert res["profile_count"] == 10
    assert res["question_count"] == 1
    assert res["requires_human_review"] is True  # True because question_count > 0

    # 2. Score under 85 / Medium
    # Profile: 5, Questions: 2 (deducts 16), Consent: 1 (deducts 2), Unknown: 1 (deducts 5) -> Score: 77
    fields = []
    for i in range(5):
        fields.append(FieldMetadata(f"p{i}", "text", "Name", "", False, FieldCategory.PROFILE, None))
    fields.append(FieldMetadata("q1", "text", "Why?", "", False, FieldCategory.QUESTION, None))
    fields.append(FieldMetadata("q2", "text", "Explain?", "", False, FieldCategory.QUESTION, None))
    fields.append(FieldMetadata("c1", "checkbox", "Agree?", "", False, FieldCategory.CONSENT, None))
    fields.append(FieldMetadata("u1", "text", "Extra?", "", False, FieldCategory.UNKNOWN, None))

    res = analyzer.analyze(fields)
    assert res["automation_score"] == 77
    assert res["profile_count"] == 5
    assert res["question_count"] == 2
    assert res["consent_count"] == 1
    assert res["unknown_count"] == 1
    assert res["requires_human_review"] is True


def test_registration_report_serialization():
    field_stats = {
        "profile": 10,
        "question": 1,
        "team": 0,
        "consent": 0,
        "unknown": 0
    }
    report = RegistrationReport(
        hackathon_name="Test Hackathon",
        registration_url="http://test.com/reg",
        field_statistics=field_stats,
        automation_score=92,
        requires_human_review=True,
        questions=[{"label": "Why join?", "complexity": "SIMPLE"}]
    )

    assert report.classification == "HIGH"
    assert report.recommendation == "AUTO_FILL_ONLY"

    dict_repr = report.to_dict()
    assert dict_repr["hackathon_name"] == "Test Hackathon"
    assert dict_repr["automation_score"] == 92
    assert dict_repr["readiness_classification"] == "HIGH"
    assert dict_repr["automation_recommendation"] == "AUTO_FILL_ONLY"
    assert dict_repr["questions"] == [{"label": "Why join?", "complexity": "SIMPLE"}]

    json_str = report.to_json()
    loaded = json.loads(json_str)
    assert loaded["automation_score"] == 92


def test_repository_and_approval_engine(tmp_path):
    db_file = tmp_path / "test_analysis.db"
    repo = RegistrationAnalysisRepository(db_path=str(db_file))
    repo.initialize()

    # Save placeholder
    url = "http://hackathon.io/apply"
    token = repo.save_placeholder(url, "Placeholder Hackathon")
    assert len(token) > 0

    analysis = repo.get_analysis(url)
    assert analysis is not None
    assert analysis["hackathon_name"] == "Placeholder Hackathon"
    assert analysis["analysis_status"] == "NOT_ANALYZED"
    assert analysis["approval_status"] == "PENDING"
    assert analysis["approval_token"] == token

    # Save complete analysis
    repo.save_analysis(
        url=url,
        hackathon_name="Analyzed Hackathon",
        profile_count=5,
        question_count=0,
        team_count=0,
        consent_count=1,
        unknown_count=0,
        score=98,
        requires_human_review=False,
        classification="HIGH",
        recommendation="AUTO_FILL_ONLY"
    )

    analysis2 = repo.get_analysis(url)
    assert analysis2["hackathon_name"] == "Analyzed Hackathon"
    assert analysis2["analysis_status"] == "ANALYZED"
    assert analysis2["automation_score"] == 98
    assert analysis2["classification"] == "HIGH"
    assert analysis2["automation_recommendation"] == "AUTO_FILL_ONLY"
    assert analysis2["approval_token"] == token  # token should be preserved

    # Approval Engine test
    engine = ApprovalEngine(repo)
    assert engine.get_status(url) == "PENDING"

    engine.approve(url)
    assert engine.get_status(url) == "APPROVED"

    engine.reject(url)
    assert engine.get_status(url) == "REJECTED"


def test_save_failed_analysis(tmp_path):
    db_file = tmp_path / "test_failed.db"
    repo = RegistrationAnalysisRepository(db_path=str(db_file))
    repo.initialize()

    url = "http://hackathon.io/bad-page"
    token = repo.save_failed_analysis(url, "Bad Page")
    assert len(token) > 0

    analysis = repo.get_analysis(url)
    assert analysis is not None
    assert analysis["analysis_status"] == "FAILED"
    assert analysis["automation_score"] == 0
    assert analysis["requires_human_review"] == 1
    assert analysis["approval_token"] == token
