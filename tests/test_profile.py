from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from hackathon_hunter.cli import main
from hackathon_hunter.models.profile import UserProfile
from hackathon_hunter.services.profile_service import ProfileService


@pytest.fixture
def valid_profile_dict(tmp_path) -> dict:
    # Create a dummy resume.pdf file
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_text("dummy pdf contents")

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
        "portfolio": "https://garlapati.dev",
        "resume_path": str(resume_file),
    }


class TestUserProfileModel:
    def test_valid_profile_creation(self, valid_profile_dict):
        profile = UserProfile(**valid_profile_dict)
        assert profile.full_name == "Garlapati saikiran"
        assert profile.email == "garlapati3105@gmail.com"
        assert profile.graduation_year == 2029
        assert profile.portfolio == "https://garlapati.dev"

    def test_strip_whitespace(self, valid_profile_dict):
        valid_profile_dict["full_name"] = "  Garlapati saikiran  "
        profile = UserProfile(**valid_profile_dict)
        assert profile.full_name == "Garlapati saikiran"

    def test_empty_required_field_raises(self, valid_profile_dict):
        valid_profile_dict["full_name"] = "   "
        with pytest.raises(ValidationError) as exc_info:
            UserProfile(**valid_profile_dict)
        assert "Field 'full_name' must be a non-empty string" in str(exc_info.value)

    def test_invalid_email_format_raises(self, valid_profile_dict):
        valid_profile_dict["email"] = "not_an_email"
        with pytest.raises(ValidationError) as exc_info:
            UserProfile(**valid_profile_dict)
        assert "Invalid email format" in str(exc_info.value)

    def test_invalid_github_url_raises(self, valid_profile_dict):
        valid_profile_dict["github"] = "https://gitlab.com/username"
        with pytest.raises(ValidationError) as exc_info:
            UserProfile(**valid_profile_dict)
        assert "Must contain github.com" in str(exc_info.value)

    def test_invalid_linkedin_url_raises(self, valid_profile_dict):
        valid_profile_dict["linkedin"] = "https://facebook.com/username"
        with pytest.raises(ValidationError) as exc_info:
            UserProfile(**valid_profile_dict)
        assert "Must contain linkedin.com" in str(exc_info.value)

    def test_missing_resume_raises(self, valid_profile_dict):
        valid_profile_dict["resume_path"] = "non_existent_file.pdf"
        with pytest.raises(ValidationError) as exc_info:
            UserProfile(**valid_profile_dict)
        assert "Resume file does not exist" in str(exc_info.value)

    def test_portfolio_optional(self, valid_profile_dict):
        valid_profile_dict["portfolio"] = None
        profile = UserProfile(**valid_profile_dict)
        assert profile.portfolio is None


class TestProfileService:
    def test_load_and_save_profile(self, tmp_path, valid_profile_dict):
        profile_file = tmp_path / "profile.json"
        
        # Test loading missing file
        service = ProfileService(default_path=profile_file)
        with pytest.raises(FileNotFoundError):
            service.load_profile()

        # Save profile
        profile = UserProfile(**valid_profile_dict)
        service.save_profile(profile)
        assert profile_file.exists()

        # Load profile
        loaded_profile = service.load_profile()
        assert loaded_profile.full_name == profile.full_name
        assert loaded_profile.email == profile.email

    def test_validate_profile(self, valid_profile_dict):
        profile = UserProfile(**valid_profile_dict)
        service = ProfileService()
        assert service.validate_profile(profile) is True


class TestProfileCLI:
    @patch("sys.argv", ["hackathon_hunter", "profile", "validate"])
    @patch("hackathon_hunter.services.profile_service.ProfileService.load_profile")
    @patch("hackathon_hunter.services.profile_service.ProfileService.validate_profile")
    def test_cli_success(self, mock_validate, mock_load, capsys):
        mock_load.return_value = "dummy_profile"
        mock_validate.return_value = True

        with pytest.raises(SystemExit) as sys_exit:
            main()

        assert sys_exit.value.code == 0
        captured = capsys.readouterr()
        assert "✅ Profile is valid!" in captured.out

    @patch("sys.argv", ["hackathon_hunter", "profile", "validate"])
    @patch("hackathon_hunter.services.profile_service.ProfileService.load_profile")
    def test_cli_failure(self, mock_load, capsys):
        mock_load.side_effect = ValueError("Missing required fields")

        with pytest.raises(SystemExit) as sys_exit:
            main()

        assert sys_exit.value.code == 1
        captured = capsys.readouterr()
        assert "❌ Profile validation failed" in captured.err
