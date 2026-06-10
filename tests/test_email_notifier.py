"""
Unit tests for EmailNotifier.

Tests use unittest.mock to patch smtplib.SMTP so no real network calls
are made. All 58 existing tests remain completely unaffected.
"""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch, call

import pytest

from hackathon_hunter.models.hackathon import Hackathon
from hackathon_hunter.notifications.email_notifier import EmailNotifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_notifier(**kwargs) -> EmailNotifier:
    defaults = dict(
        sender="sender@gmail.com",
        password="testapppassword",
        recipients=["recipient@example.com"],
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        subject_prefix="[Test]",
    )
    defaults.update(kwargs)
    return EmailNotifier(**defaults)


def make_hackathon(url: str = "https://example.com/h1", platform: str = "devpost") -> Hackathon:
    return Hackathon(
        platform=platform,
        name="Test Hackathon",
        url=url,
        location="Online",
        deadline="Jun 30, 2026",
        is_online=True,
    )


# ---------------------------------------------------------------------------
# channel_name
# ---------------------------------------------------------------------------

class TestChannelName:
    def test_channel_name_is_email(self):
        notifier = make_notifier()
        assert notifier.channel_name == "email"


# ---------------------------------------------------------------------------
# send_batch — empty list
# ---------------------------------------------------------------------------

class TestSendBatchEmpty:
    def test_empty_batch_returns_true_without_smtp(self):
        notifier = make_notifier()
        with patch("smtplib.SMTP") as mock_smtp:
            result = notifier.send_batch([])
        assert result is True
        mock_smtp.assert_not_called()


# ---------------------------------------------------------------------------
# send_batch — no recipients
# ---------------------------------------------------------------------------

class TestSendBatchNoRecipients:
    def test_no_recipients_returns_false(self):
        notifier = make_notifier(recipients=[])
        h = make_hackathon()
        with patch("smtplib.SMTP") as mock_smtp:
            result = notifier.send_batch([h])
        assert result is False
        mock_smtp.assert_not_called()


# ---------------------------------------------------------------------------
# send_batch — success
# ---------------------------------------------------------------------------

class TestSendBatchSuccess:
    def _patched_send(self, hackathons, notifier):
        """Run send_batch with a fully mocked SMTP server."""
        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server) as mock_smtp_cls:
            # Support context manager usage: `with smtplib.SMTP(...) as server`
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = notifier.send_batch(hackathons)
        return result, mock_smtp_cls, mock_server

    def test_returns_true_on_success(self):
        notifier = make_notifier()
        h = make_hackathon()
        result, _, _ = self._patched_send([h], notifier)
        assert result is True

    def test_smtp_constructed_with_correct_host_port(self):
        notifier = make_notifier(smtp_host="smtp.gmail.com", smtp_port=587)
        h = make_hackathon()
        _, mock_smtp_cls, _ = self._patched_send([h], notifier)
        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=30)

    def test_starttls_called(self):
        notifier = make_notifier()
        h = make_hackathon()
        _, _, mock_server = self._patched_send([h], notifier)
        mock_server.starttls.assert_called_once()

    def test_login_called_with_credentials(self):
        notifier = make_notifier(sender="sender@gmail.com", password="pass word")
        h = make_hackathon()
        _, _, mock_server = self._patched_send([h], notifier)
        # App Password spaces should be stripped
        mock_server.login.assert_called_once_with("sender@gmail.com", "password")

    def test_sendmail_called_with_correct_sender_and_recipients(self):
        recipients = ["a@example.com", "b@example.com"]
        notifier = make_notifier(sender="sender@gmail.com", recipients=recipients)
        h = make_hackathon()
        _, _, mock_server = self._patched_send([h], notifier)
        args = mock_server.sendmail.call_args[0]
        assert args[0] == "sender@gmail.com"
        assert args[1] == recipients

    def test_multiple_hackathons_one_send_call(self):
        """One email per batch, not one per hackathon."""
        notifier = make_notifier()
        hackathons = [
            make_hackathon(f"https://example.com/{i}") for i in range(5)
        ]
        _, _, mock_server = self._patched_send(hackathons, notifier)
        assert mock_server.sendmail.call_count == 1


# ---------------------------------------------------------------------------
# send_batch — SMTP failures
# ---------------------------------------------------------------------------

class TestSendBatchFailures:
    def _send_with_smtp_error(self, exc_class, notifier=None):
        if notifier is None:
            notifier = make_notifier()
        h = make_hackathon()
        mock_server = MagicMock()
        # SMTPAuthenticationError(code, msg) requires 2 args; other subclasses need 1
        if exc_class is smtplib.SMTPAuthenticationError:
            mock_server.login.side_effect = exc_class(535, b"auth failed")
        else:
            mock_server.login.side_effect = exc_class("test error")
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = notifier.send_batch([h])
        return result


    def test_auth_error_returns_false(self):
        result = self._send_with_smtp_error(smtplib.SMTPAuthenticationError)
        assert result is False

    def test_connect_error_returns_false(self):
        notifier = make_notifier()
        h = make_hackathon()
        with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "test")):
            result = notifier.send_batch([h])
        assert result is False

    def test_smtp_exception_returns_false(self):
        result = self._send_with_smtp_error(smtplib.SMTPException)
        assert result is False

    def test_os_error_returns_false(self):
        notifier = make_notifier()
        h = make_hackathon()
        with patch("smtplib.SMTP", side_effect=OSError("network error")):
            result = notifier.send_batch([h])
        assert result is False

    def test_unexpected_exception_returns_false(self):
        result = self._send_with_smtp_error(RuntimeError)
        assert result is False


# ---------------------------------------------------------------------------
# App Password normalisation
# ---------------------------------------------------------------------------

class TestAppPasswordNormalisation:
    def test_spaces_stripped_from_password(self):
        notifier = make_notifier(password="abcd efgh ijkl mnop")
        mock_server = MagicMock()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            notifier.send_batch([make_hackathon()])
        mock_server.login.assert_called_once_with("sender@gmail.com", "abcdefghijklmnop")
