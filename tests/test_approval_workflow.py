from __future__ import annotations

import json
import sqlite3
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi.testclient import TestClient

from hackathon_hunter.approval.token_manager import TokenManager
from hackathon_hunter.approval.approval_service import ApprovalService, TokenValidationError
from hackathon_hunter.approval.approval_routes import app, get_service
from hackathon_hunter.repositories.registration_analysis_repository import (
    RegistrationAnalysisRepository,
)


def test_token_manager_generation_and_expiration():
    token, expires = TokenManager.generate_token(expires_in_days=3)
    assert len(token) > 0
    
    # Verify not expired yet
    assert TokenManager.is_expired(expires) is False

    # Verify expiration
    past_expiration = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert TokenManager.is_expired(past_expiration) is True


def test_approval_service_and_history(tmp_path):
    db_file = tmp_path / "test_approval.db"
    repo = RegistrationAnalysisRepository(db_path=str(db_file))
    repo.initialize()

    # Initial save of placeholder (this automatically calls TokenManager)
    url = "https://hackathon.com/join"
    token = repo.save_placeholder(url, "My Hackathon")
    
    service = ApprovalService(repo)

    # Initial status is PENDING
    status = service.get_status(token)
    assert status["approval_status"] == "PENDING"
    assert status["analysis_status"] == "NOT_ANALYZED"

    # Approve with notes
    notes = "Approved for automation test."
    approved = service.approve(token, notes)
    assert approved["approval_status"] == "APPROVED"
    assert approved["approval_notes"] == notes
    assert approved["approved_at"] is not None

    # Verify database logs
    with repo._connect() as conn:
        logs = conn.execute("SELECT * FROM approval_history WHERE token = ?", (token,)).fetchall()
        assert len(logs) == 1
        assert logs[0]["action"] == "APPROVE"
        assert logs[0]["notes"] == notes


def test_approval_rejection_and_history(tmp_path):
    db_file = tmp_path / "test_rejection.db"
    repo = RegistrationAnalysisRepository(db_path=str(db_file))
    repo.initialize()

    url = "https://hackathon.com/join-2"
    token = repo.save_placeholder(url, "My Hackathon 2")
    service = ApprovalService(repo)

    # Reject with notes
    notes = "Rejected due to too many unknown questions."
    rejected = service.reject(token, notes)
    assert rejected["approval_status"] == "REJECTED"
    assert rejected["approval_notes"] == notes
    assert rejected["rejected_at"] is not None

    # Verify history logs
    with repo._connect() as conn:
        logs = conn.execute("SELECT * FROM approval_history WHERE token = ?", (token,)).fetchall()
        assert len(logs) == 1
        assert logs[0]["action"] == "REJECT"
        assert logs[0]["notes"] == notes


def test_expired_token_handling(tmp_path):
    db_file = tmp_path / "test_expiration.db"
    repo = RegistrationAnalysisRepository(db_path=str(db_file))
    repo.initialize()

    # Save a record and manually force its expiration timestamp to the past
    url = "https://hackathon.com/expired"
    token = repo.save_placeholder(url, "Expired Hackathon")

    past_expiration = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with repo._connect() as conn:
        conn.execute("UPDATE registration_analysis SET token_expires_at = ? WHERE approval_token = ?", (past_expiration, token))
        conn.commit()

    service = ApprovalService(repo)

    # Calling get_status should dynamically check and transition status to EXPIRED
    status = service.get_status(token)
    assert status["approval_status"] == "EXPIRED"

    # Attempting to approve/reject on expired token should raise TokenValidationError
    with pytest.raises(TokenValidationError) as exc_info:
        service.approve(token, "Approval note")
    assert "expired" in str(exc_info.value).lower()

    with pytest.raises(TokenValidationError) as exc_info:
        service.reject(token, "Rejection note")
    assert "expired" in str(exc_info.value).lower()


def test_fastapi_endpoints(tmp_path):
    # Override app get_service dependency to use temporary DB path
    db_file = tmp_path / "test_routes.db"
    repo = RegistrationAnalysisRepository(db_path=str(db_file))
    repo.initialize()

    def override_get_service():
        return ApprovalService(repo)

    app.dependency_overrides[get_service] = override_get_service

    client = TestClient(app)

    # Insert a placeholder
    url = "https://test.com/endpoint"
    token = repo.save_placeholder(url, "FastAPI Test Hackathon")

    # 1. Test GET /approve/{token} confirmation page
    response = client.get(f"/approve/{token}")
    assert response.status_code == 200
    assert "Confirm Registration Approve" in response.text
    assert "FastAPI Test Hackathon" in response.text

    # 2. Test GET /reject/{token} confirmation page
    response = client.get(f"/reject/{token}")
    assert response.status_code == 200
    assert "Confirm Registration Reject" in response.text

    # 3. Test POST /api/approve/{token} state change via Form data
    post_response = client.post(f"/api/approve/{token}", data={"notes": "Form approved!"})
    assert post_response.status_code == 200
    json_data = post_response.json()
    assert json_data["status"] == "success"
    assert json_data["details"]["approval_status"] == "APPROVED"
    assert json_data["details"]["approval_notes"] == "Form approved!"

    # 4. Test GET /api/status/{token} JSON response
    status_response = client.get(f"/api/status/{token}")
    assert status_response.status_code == 200
    assert status_response.json()["approval_status"] == "APPROVED"

    # Clean dependency override
    app.dependency_overrides.clear()
