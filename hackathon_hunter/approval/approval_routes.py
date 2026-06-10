from __future__ import annotations

import logging
from typing import Optional
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, Form, status
from fastapi.responses import HTMLResponse

from hackathon_hunter.approval.approval_service import ApprovalService, TokenValidationError
from hackathon_hunter.approval.approval_models import ApprovalStatusResponse, ApprovalActionResponse
from hackathon_hunter.repositories.registration_analysis_repository import RegistrationAnalysisRepository
from hackathon_hunter.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Hackathon Hunter Approval Server")


def get_service() -> ApprovalService:
    repo = RegistrationAnalysisRepository(db_path=settings.DATABASE_PATH)
    repo.initialize()
    return ApprovalService(repo)


@app.get("/approve/{token}", response_class=HTMLResponse)
def get_approve_page(token: str, service: ApprovalService = Depends(get_service)):
    try:
        record = service.get_status(token)
        return _render_confirmation_html(token, "APPROVE", record)
    except TokenValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/reject/{token}", response_class=HTMLResponse)
def get_reject_page(token: str, service: ApprovalService = Depends(get_service)):
    try:
        record = service.get_status(token)
        return _render_confirmation_html(token, "REJECT", record)
    except TokenValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/approve/{token}", response_model=ApprovalActionResponse)
def post_approve(
    token: str,
    notes: Optional[str] = Form(None),
    notes_query: Optional[str] = Query(None, alias="notes"),
    service: ApprovalService = Depends(get_service)
):
    resolved_notes = notes or notes_query
    try:
        record = service.approve(token, resolved_notes)
        return {
            "status": "success",
            "message": "Registration approved successfully.",
            "details": record
        }
    except TokenValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/reject/{token}", response_model=ApprovalActionResponse)
def post_reject(
    token: str,
    notes: Optional[str] = Form(None),
    notes_query: Optional[str] = Query(None, alias="notes"),
    service: ApprovalService = Depends(get_service)
):
    resolved_notes = notes or notes_query
    try:
        record = service.reject(token, resolved_notes)
        return {
            "status": "success",
            "message": "Registration rejected successfully.",
            "details": record
        }
    except TokenValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/status/{token}", response_model=ApprovalStatusResponse)
def get_status_api(token: str, service: ApprovalService = Depends(get_service)):
    try:
        record = service.get_status(token)
        return record
    except TokenValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def _render_confirmation_html(token: str, action: str, details: dict) -> str:
    title = f"Confirm {action.title()} - Hackathon Hunter"
    action_url = f"/api/{action.lower()}/{token}"
    action_color = "#16A34A" if action.upper() == "APPROVE" else "#DC2626"
    button_text = f"Confirm {action.title()}"
    
    score = details.get("automation_score", 0)
    cls = details.get("classification", "LOW")
    rec = details.get("automation_recommendation", "MANUAL_ONLY")

    # Rejection notes text input or standard notes
    notes_placeholder = "Enter rejection reason / comments (optional)" if action.upper() == "REJECT" else "Add approval notes (optional)"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #F1F5F9;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1E293B;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .container {{
      background-color: #FFFFFF;
      border-radius: 16px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
      padding: 32px;
      max-width: 500px;
      width: 100%;
      box-sizing: border-box;
      border-top: 6px solid {action_color};
    }}
    h1 {{
      font-size: 24px;
      font-weight: 800;
      margin-top: 0;
      margin-bottom: 8px;
      color: #0F172A;
    }}
    p.subtitle {{
      color: #64748B;
      font-size: 14px;
      margin-top: 0;
      margin-bottom: 24px;
    }}
    .card {{
      background-color: #F8FAFC;
      border: 1px solid #E2E8F0;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
    }}
    .card-title {{
      font-weight: 700;
      font-size: 16px;
      margin-top: 0;
      margin-bottom: 8px;
      color: #1E293B;
    }}
    .card-url {{
      font-size: 13px;
      color: #2563EB;
      text-decoration: none;
      word-break: break-all;
      display: block;
      margin-bottom: 12px;
    }}
    .metric-row {{
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      padding: 4px 0;
      color: #475569;
    }}
    .metric-val {{
      font-weight: 600;
    }}
    .form-group {{
      margin-bottom: 24px;
    }}
    label {{
      display: block;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 8px;
      color: #334155;
    }}
    input[type="text"] {{
      width: 100%;
      padding: 10px 12px;
      border: 1px solid #CBD5E1;
      border-radius: 6px;
      font-size: 14px;
      box-sizing: border-box;
      transition: border-color 0.2s;
    }}
    input[type="text"]:focus {{
      outline: none;
      border-color: #2563EB;
    }}
    .actions {{
      display: flex;
      gap: 12px;
    }}
    button {{
      flex: 1;
      background-color: {action_color};
      color: #FFFFFF;
      border: none;
      border-radius: 6px;
      padding: 12px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.2s;
    }}
    button:hover {{
      opacity: 0.9;
    }}
    .btn-cancel {{
      background-color: #E2E8F0;
      color: #475569;
      text-align: center;
      text-decoration: none;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Confirm Registration {action.title()}</h1>
    <p class="subtitle">Please review the details below before executing the action.</p>
    
    <div class="card">
      <div class="card-title">{details.get("hackathon_name", "Unknown Hackathon")}</div>
      <a class="card-url" href="{details.get("url")}" target="_blank">{details.get("url")}</a>
      
      <div class="metric-row">
        <span>Automation Score</span>
        <span class="metric-val" style="color: #2563EB;">{score}%</span>
      </div>
      <div class="metric-row">
        <span>Classification</span>
        <span class="metric-val">{cls}</span>
      </div>
      <div class="metric-row">
        <span>Recommendation</span>
        <span class="metric-val">{rec}</span>
      </div>
    </div>
    
    <form action="{action_url}" method="post">
      <div class="form-group">
        <label for="notes">Action Notes</label>
        <input type="text" id="notes" name="notes" placeholder="{notes_placeholder}">
      </div>
      
      <div class="actions">
        <a href="/api/status/{token}" class="button btn-cancel" style="display: flex; align-items: center; justify-content: center; border-radius: 6px; padding: 12px; font-size: 14px; font-weight: 600; box-sizing: border-box;">View Status</a>
        <button type="submit">{button_text}</button>
      </div>
    </form>
  </div>
</body>
</html>"""
