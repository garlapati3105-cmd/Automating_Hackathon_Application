"""hackathon_hunter.notifications.templates package."""

from hackathon_hunter.notifications.templates.summary_email import (
    build_subject,
    render_html,
    render_plain,
)

__all__ = ["build_subject", "render_html", "render_plain"]
