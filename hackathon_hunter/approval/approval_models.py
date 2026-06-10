from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ApprovalStatusResponse(BaseModel):
    id: int
    url: str
    hackathon_name: Optional[str] = None
    profile_field_count: int
    question_field_count: int
    team_field_count: int
    consent_field_count: int
    unknown_field_count: int
    automation_score: int
    requires_human_review: bool
    classification: str
    automation_recommendation: str
    approval_status: str
    analysis_status: str
    approval_token: str
    token_expires_at: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_at: Optional[str] = None
    approval_notes: Optional[str] = None
    created_at: str
    updated_at: str


class ApprovalActionResponse(BaseModel):
    status: str
    message: str
    details: ApprovalStatusResponse
