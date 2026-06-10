"""
EmailNotifier — Gmail SMTP notification channel.

Sends one summary HTML email per batch using Gmail's SMTP server
with STARTTLS and App Password authentication.

Authentication:
    Uses Gmail App Passwords only (standard Gmail passwords are not
    supported after Google's 2022 less-secure-apps policy change).
    How to generate: Google Account → Security → 2-Step Verification
    → App Passwords → Select app: "Mail".

Error handling:
    All exceptions are caught, logged, and return False.
    The scraper pipeline is never interrupted by an email failure.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from hackathon_hunter.notifications.base import BaseNotifier
from hackathon_hunter.notifications.templates.summary_email import (
    build_subject,
    render_html,
    render_plain,
)

if TYPE_CHECKING:
    from hackathon_hunter.models.hackathon import Hackathon

logger = logging.getLogger(__name__)


class EmailNotifier(BaseNotifier):
    """
    Sends one summary email per scraper run via Gmail SMTP (App Password auth).

    Args:
        sender:     Gmail address used as From: header and SMTP login.
        password:   Gmail App Password (16-char, spaces OK — they are stripped).
        recipients: List of To: addresses.
        smtp_host:  SMTP server (default ``smtp.gmail.com``).
        smtp_port:  SMTP port for STARTTLS (default ``587``).
        subject_prefix: Prefix prepended to the subject line.
    """

    channel_name = "email"

    def __init__(
        self,
        sender: str,
        password: str,
        recipients: list[str],
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        subject_prefix: str = "[Hackathon Hunter]",
        db_path: str | None = None,
    ) -> None:
        self._sender = sender.strip()
        self._password = password.replace(" ", "")  # App Passwords may have spaces
        self._recipients = [r.strip() for r in recipients if r.strip()]
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._subject_prefix = subject_prefix
        self._db_path = db_path

    # ------------------------------------------------------------------
    # BaseNotifier interface
    # ------------------------------------------------------------------

    def send_batch(self, hackathons: list[Hackathon]) -> bool:
        """
        Send a single summary email for all hackathons in the batch.

        Args:
            hackathons: List of new, unnotified Hackathon objects.

        Returns:
            True if the email was sent successfully, False on any error.
        """
        if not hackathons:
            logger.debug("[email] send_batch called with empty list — skipping.")
            return True

        if not self._recipients:
            logger.warning("[email] No recipients configured — skipping send.")
            return False

        try:
            msg = self._build_message(hackathons)
            self._send(msg)
            logger.info(
                "[email] Summary email sent: %d hackathon(s) → %s",
                len(hackathons),
                ", ".join(self._recipients),
            )
            return True

        except smtplib.SMTPAuthenticationError as exc:
            logger.error(
                "[email] Authentication failed. Verify HH_EMAIL_SENDER and "
                "HH_EMAIL_PASSWORD (must be a Gmail App Password). Detail: %s",
                exc,
            )
        except smtplib.SMTPConnectError as exc:
            logger.error("[email] Could not connect to %s:%s — %s", self._smtp_host, self._smtp_port, exc)
        except smtplib.SMTPRecipientsRefused as exc:
            logger.error("[email] Recipient(s) refused by server: %s", exc)
        except smtplib.SMTPException as exc:
            logger.error("[email] SMTP error: %s", exc)
        except OSError as exc:
            logger.error("[email] Network error: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("[email] Unexpected error during send: %s", exc, exc_info=True)

        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_message(self, hackathons: list[Hackathon]) -> MIMEMultipart:
        """Construct a MIMEMultipart('alternative') message with HTML + plain text."""
        analyses = {}
        if self._db_path:
            try:
                from hackathon_hunter.repositories.registration_analysis_repository import RegistrationAnalysisRepository
                repo = RegistrationAnalysisRepository(db_path=self._db_path)
                for h in hackathons:
                    analysis = repo.get_analysis(h.url)
                    if analysis:
                        analyses[h.url] = analysis
            except Exception as exc:
                logger.warning("Failed to fetch analyses from database: %s", exc)

        subject = build_subject(hackathons, self._subject_prefix)
        html_body = render_html(hackathons, analyses)
        plain_body = render_plain(hackathons, analyses)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Hackathon Hunter <{self._sender}>"
        msg["To"] = ", ".join(self._recipients)

        # Plain text first (RFC 2046: last part preferred by clients)
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        return msg

    def _send(self, msg: MIMEMultipart) -> None:
        """Open SMTP connection and send the message."""
        logger.debug(
            "[email] Connecting to %s:%d as %s",
            self._smtp_host,
            self._smtp_port,
            self._sender,
        )
        with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            logger.debug("[email] STARTTLS established — logging in.")
            server.login(self._sender, self._password)
            server.sendmail(
                self._sender,
                self._recipients,
                msg.as_string(),
            )
            logger.debug("[email] sendmail() completed.")
