from __future__ import annotations

import json
import os
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

from hackathon_hunter.automation import (
    PlaywrightManager,
    FormDetector,
    FieldMapper,
    FormFiller,
    PageAnalyzer,
    FieldCategory,
    FieldMetadata,
)
from hackathon_hunter.models.profile import UserProfile
from hackathon_hunter.models.team_profile import TeamProfile
from hackathon_hunter.services.team_profile_service import TeamProfileService


@pytest.fixture
def dummy_html_path(tmp_path) -> Path:
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Registration</title></head>
    <body>
        <form>
            <label for="name_field">Full Name</label>
            <input type="text" id="name_field" placeholder="Enter your full name" required>

            <label for="email_field">Email Address</label>
            <input type="email" id="email_field" required>

            <label for="phone_field">Mobile Number</label>
            <input type="tel" id="phone_field">

            <label for="college_field">University</label>
            <input type="text" id="college_field">

            <label for="degree_field">Degree</label>
            <select id="degree_field">
                <option value="Btech">Btech</option>
                <option value="M.Tech">M.Tech</option>
            </select>

            <label for="branch_field">Branch / Major</label>
            <input type="text" id="branch_field">

            <label for="grad_field">Graduation Year</label>
            <input type="number" id="grad_field">

            <label for="github_field">GitHub Profile</label>
            <input type="url" id="github_field">

            <label for="linkedin_field">LinkedIn Profile</label>
            <input type="url" id="linkedin_field">

            <label for="portfolio_field">Portfolio Link</label>
            <input type="url" id="portfolio_field">

            <label for="resume_field">Upload Resume</label>
            <input type="file" id="resume_field">

            <label for="team_name_field">Team Name</label>
            <input type="text" id="team_name_field">

            <label for="question_1">Why do you want to participate in this hackathon?</label>
            <textarea id="question_1"></textarea>

            <label for="unknown_field">Unknown Extra Field</label>
            <input type="text" id="unknown_field">
        </form>
    </body>
    </html>
    """
    path = tmp_path / "test_form.html"
    path.write_text(html_content, encoding="utf-8")
    return path


@pytest.fixture
def mock_profile_dict(tmp_path) -> dict:
    resume = tmp_path / "resume_mock.pdf"
    resume.write_text("dummy resume")
    return {
        "full_name": "Garlapati saikiran",
        "email": "garlapati3105@gmail.com",
        "phone": "9959113105",
        "college": "Aurora University",
        "degree": "Btech",
        "branch": "Computer Science and Engineering",
        "graduation_year": 2029,
        "github": "https://github.com/garlapati3105-cmd",
        "linkedin": "https://www.linkedin.com/in/sai-kiran-garlapati-795710397/",
        "portfolio": None,
        "resume_path": str(resume),
    }


class TestFieldMapper:
    def test_mapping_rules(self):
        mapper = FieldMapper()

        def make_meta(label: str, placeholder: str = "", identifier: str = "") -> FieldMetadata:
            return FieldMetadata(identifier, "text", label, placeholder, False, FieldCategory.PROFILE, None)

        assert mapper.map_to_profile_field(make_meta("Full Name")) == "full_name"
        assert mapper.map_to_profile_field(make_meta("Email")) == "email"
        assert mapper.map_to_profile_field(make_meta("Mobile Number")) == "phone"
        assert mapper.map_to_profile_field(make_meta("University")) == "college"
        assert mapper.map_to_profile_field(make_meta("GitHub")) == "github"
        assert mapper.map_to_profile_field(make_meta("LinkedIn")) == "linkedin"
        assert mapper.map_to_profile_field(make_meta("Upload Resume")) == "resume_path"


class TestTeamProfileModel:
    def test_valid_team_profile(self):
        data = {
            "team_name": "Antigravities",
            "team_size": 3,
            "members": [
                {
                    "full_name": "Sai Kiran",
                    "email": "sai@gmail.com",
                    "github": "https://github.com/saikiran"
                }
            ]
        }
        team = TeamProfile(**data)
        assert team.team_name == "Antigravities"
        assert team.team_size == 3
        assert len(team.members) == 1

        service = TeamProfileService()
        assert service.validate_team_profile(team) is True


class TestFormAutoFillAutomation:
    def test_form_detection_and_filling(self, dummy_html_path, mock_profile_dict):
        profile = UserProfile(**mock_profile_dict)
        url = dummy_html_path.as_uri()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)

            detector = FormDetector()
            fields = detector.detect_fields(page)

            # Check detection counts
            assert len(fields) >= 14

            # Verify classification categories
            name_field = next(f for f in fields if "full name" in f.label_text.lower())
            assert name_field.category == FieldCategory.PROFILE
            assert name_field.required is True

            team_field = next(f for f in fields if "team name" in f.label_text.lower())
            assert team_field.category == FieldCategory.TEAM

            q_field = next(f for f in fields if "why do you" in f.label_text.lower())
            assert q_field.category == FieldCategory.QUESTION

            # Verify FormFiller logic
            mapper = FieldMapper()
            filler = FormFiller(mapper)

            # Test Dry Run
            filled, skipped = filler.fill_form(fields, profile, dry_run=True)
            assert len(filled) > 0
            assert any(f.category == FieldCategory.QUESTION for f in skipped)

            # Test Real Fill
            filled, skipped = filler.fill_form(fields, profile, dry_run=False)
            assert len(filled) > 0
            
            # Check value was typed into the page DOM
            inp_val = page.locator("#name_field").input_value()
            assert inp_val == "Garlapati saikiran"

            browser.close()
