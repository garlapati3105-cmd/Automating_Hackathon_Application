"""
Summary email templates for Hackathon Hunter notifications.

All rendering is done with pure Python string formatting — no external
template engine required. CSS is fully inline for maximum email client
compatibility (Gmail, Outlook, Apple Mail).

Public API:
    build_subject(hackathons, prefix)  →  str
    render_html(hackathons)            →  str   (full HTML email)
    render_plain(hackathons)           →  str   (plain-text fallback)

Approval link placeholders:
    Each hackathon card contains [Approve] and [Skip] buttons with
    href="#approve-<url-hash>" / href="#skip-<url-hash>".
    Replace the href values with real webhook URLs when that feature is built.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from hackathon_hunter.notifications.filters import is_hyderabad_hackathon

if TYPE_CHECKING:
    from typing import Any
    from hackathon_hunter.models.hackathon import Hackathon


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------

def build_subject(hackathons: list[Hackathon], prefix: str = "[Hackathon Hunter]") -> str:
    """
    Build the email subject line.

    Format: ``[Hackathon Hunter] 🎉 5 New Hackathons Discovered (devpost, mlh)``
    """
    count = len(hackathons)
    noun = "Hackathon" if count == 1 else "Hackathons"
    platforms = sorted({h.platform for h in hackathons})
    platform_str = ", ".join(platforms)
    return f"{prefix} 🎉 {count} New {noun} Discovered ({platform_str})"


# ---------------------------------------------------------------------------
# Plain-text fallback
# ---------------------------------------------------------------------------

def render_plain(hackathons: list[Hackathon], analyses: dict[str, dict] = None) -> str:
    """Render a plain-text summary suitable as a MIME fallback."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "=" * 60,
        f"  HACKATHON HUNTER  —  {len(hackathons)} New Hackathon(s) Found",
        f"  Generated: {now_str}",
        "=" * 60,
        "",
    ]
    for i, h in enumerate(hackathons, 1):
        online_tag = (
            "Online" if h.is_online
            else "In-Person" if h.is_online is False
            else "Unknown"
        )
        prefix = "[🌟 HYDERABAD PICK] " if is_hyderabad_hackathon(h.location) else ""
        lines.append(f"{i}. {prefix}[{h.platform.upper()}] {h.name}")
        lines.append(f"   URL      : {h.url}")
        lines.append(f"   Mode     : {online_tag}")
        if h.location:
            lines.append(f"   Location : {h.location}")
        if h.deadline:
            lines.append(f"   Deadline : {h.deadline}")
        lines.append(f"   Register : {h.url}")
        
        # Include readiness report if available
        if analyses and h.url in analyses:
            analysis = analyses[h.url]
            status = analysis.get("analysis_status", "NOT_ANALYZED")
            if status == "ANALYZED":
                lines.append(f"   Automation Score: {analysis.get('automation_score', 0)}")
                lines.append(f"   Classification  : {analysis.get('classification', 'LOW')}")
                lines.append(f"   Recommendation  : {analysis.get('automation_recommendation', 'MANUAL_ONLY')}")
                lines.append("   Fields:")
                lines.append(f"     Profile  : {analysis.get('profile_field_count', 0)}")
                lines.append(f"     Questions: {analysis.get('question_field_count', 0)}")
                lines.append(f"     Team     : {analysis.get('team_field_count', 0)}")
                lines.append(f"     Consent  : {analysis.get('consent_field_count', 0)}")
                lines.append(f"     Unknown  : {analysis.get('unknown_field_count', 0)}")
            else:
                lines.append(f"   Analysis Status: {status}")
        else:
            lines.append("   Analysis Status: NOT_ANALYZED")

        lines.append("")

    lines += [
        "-" * 60,
        "Powered by Hackathon Hunter",
        "To manage notifications, edit your .env file.",
        "-" * 60,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML email
# ---------------------------------------------------------------------------

# Colour palette for platform badges
_PLATFORM_COLOURS: dict[str, tuple[str, str]] = {
    "devpost":     ("#003E54", "#00C8F0"),
    "devfolio":    ("#2F14DF", "#C2BDFF"),
    "mlh":         ("#013A6B", "#FF4F8B"),
    "unstop":      ("#6C24DF", "#D8C5FF"),
    "openhackathons": ("#1B4332", "#74C69D"),
}
_DEFAULT_BADGE_BG = "#374151"
_DEFAULT_BADGE_FG = "#D1D5DB"


def _platform_badge_style(platform: str) -> tuple[str, str]:
    """Return (background, text) hex colours for a platform badge."""
    return _PLATFORM_COLOURS.get(platform.lower(), (_DEFAULT_BADGE_BG, _DEFAULT_BADGE_FG))


def _url_hash(url: str) -> str:
    """Short stable hash of a URL for use in approval link anchors."""
    return hashlib.sha1(url.encode()).hexdigest()[:10]


def _render_hackathon_card(h: Hackathon, index: int, analysis: dict[str, Any] | None = None) -> str:
    """Render a single hackathon card as an HTML table row block."""
    badge_bg, badge_fg = _platform_badge_style(h.platform)
    url_hash = _url_hash(h.url)

    online_tag = (
        ("🌐 Online", "#0284C7", "#E0F2FE")
        if h.is_online
        else ("🏛 In-Person", "#15803D", "#DCFCE7") if h.is_online is False
        else ("❓ Unknown", "#6B7280", "#F3F4F6")
    )
    mode_label, mode_fg, mode_bg = online_tag

    location_row = (
        f"""<tr>
          <td style="padding:2px 0;color:#6B7280;font-size:13px;width:90px;">📍 Location</td>
          <td style="padding:2px 0;color:#374151;font-size:13px;">{h.location}</td>
        </tr>"""
        if h.location else ""
    )
    deadline_row = (
        f"""<tr>
          <td style="padding:2px 0;color:#6B7280;font-size:13px;width:90px;">⏰ Deadline</td>
          <td style="padding:2px 0;color:#DC2626;font-size:13px;font-weight:600;">{h.deadline}</td>
        </tr>"""
        if h.deadline else ""
    )

    # Approval link placeholders — replace href="#..." with real webhook URLs later
    approve_href = f"#approve-{url_hash}"
    skip_href = f"#skip-{url_hash}"

    # Style overrides for Hyderabad priority events
    is_hyd = is_hyderabad_hackathon(h.location)
    if is_hyd:
        card_border = "2px solid #F59E0B"
        card_shadow = "0 4px 6px -1px rgba(245, 158, 11, 0.15), 0 2px 4px -1px rgba(245, 158, 11, 0.1)"
        header_bg = "linear-gradient(135deg,#B45309 0%,#D97706 50%,#F59E0B 100%)"
        hyd_badge = """
                <span style="display:inline-block;background:#FEF3C7;color:#D97706;
                             font-size:11px;font-weight:700;letter-spacing:0.8px;
                             padding:3px 10px;border-radius:20px;text-transform:uppercase;margin-left:8px;">
                  🌟 Hyderabad Pick
                </span>"""
    else:
        card_border = "1px solid #E5E7EB"
        card_shadow = "0 1px 3px rgba(0,0,0,0.07)"
        header_bg = "linear-gradient(135deg,#1E293B 0%,#334155 100%)"
        hyd_badge = ""

    return f"""
    <!-- Hackathon Card #{index} -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="margin-bottom:20px;border-radius:12px;overflow:hidden;
                  border:{card_border};box-shadow:{card_shadow};">
      <!-- Card header -->
      <tr>
        <td style="background:{header_bg};
                   padding:16px 20px;border-radius:12px 12px 0 0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td>
                <span style="display:inline-block;background:{badge_bg};color:{badge_fg};
                             font-size:11px;font-weight:700;letter-spacing:0.8px;
                             padding:3px 10px;border-radius:20px;text-transform:uppercase;">
                  {h.platform}
                </span>
                {hyd_badge}
              </td>
              <td align="right">
                <span style="display:inline-block;background:{mode_bg};color:{mode_fg};
                             font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;">
                  {mode_label}
                </span>
              </td>
            </tr>
          </table>
          <p style="margin:10px 0 0;color:#F8FAFC;font-size:18px;font-weight:700;
                    line-height:1.3;letter-spacing:-0.2px;">
            {h.name}
          </p>
        </td>
      </tr>
      <!-- Card body -->
      <tr>
        <td style="background:#FFFFFF;padding:16px 20px;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            {location_row}
            {deadline_row}
            <tr>
              <td style="padding:2px 0;color:#6B7280;font-size:13px;width:90px;">🔗 URL</td>
              <td style="padding:2px 0;">
                <a href="{h.url}" style="color:#2563EB;font-size:13px;
                          text-decoration:none;word-break:break-all;">{h.url}</a>
              </td>
            </tr>
          </table>
          {_get_readiness_html(analysis)}
        </td>
      </tr>
      <!-- Card footer: action buttons -->
      <tr>
        <td style="background:#F9FAFB;padding:12px 20px;
                   border-top:1px solid #E5E7EB;border-radius:0 0 12px 12px;">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <!-- Register button -->
              <td style="padding-right:10px;">
                <a href="{h.url}"
                   style="display:inline-block;background:#2563EB;color:#FFFFFF;
                          font-size:13px;font-weight:600;padding:8px 20px;
                          border-radius:6px;text-decoration:none;letter-spacing:0.2px;">
                  🚀 Register Now
                </a>
              </td>
              <!-- Approve placeholder -->
              <td style="padding-right:8px;">
                <a href="{approve_href}"
                   style="display:inline-block;background:#16A34A;color:#FFFFFF;
                          font-size:12px;font-weight:600;padding:8px 16px;
                          border-radius:6px;text-decoration:none;">
                  ✅ Approve
                </a>
              </td>
              <!-- Skip placeholder -->
              <td>
                <a href="{skip_href}"
                   style="display:inline-block;background:#E5E7EB;color:#6B7280;
                          font-size:12px;font-weight:600;padding:8px 16px;
                          border-radius:6px;text-decoration:none;">
                  ⏭ Skip
                </a>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>"""


def render_html(hackathons: list[Hackathon], analyses: dict[str, dict] = None) -> str:
    """
    Render a full, richly-styled HTML email for a batch of hackathons.

    The email uses inline CSS only (no external stylesheets or images)
    for maximum compatibility across email clients.

    Returns:
        Complete HTML document string ready to send as text/html MIME part.
    """
    now_str = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    count = len(hackathons)
    noun = "Hackathon" if count == 1 else "Hackathons"

    # Platform summary pills for header
    platforms = sorted({h.platform for h in hackathons})
    platform_pills = "".join(
        f'<span style="display:inline-block;background:rgba(255,255,255,0.15);'
        f'color:#F8FAFC;font-size:12px;font-weight:600;padding:3px 12px;'
        f'border-radius:20px;margin:3px 4px 3px 0;">{p.upper()}</span>'
        for p in platforms
    )

    # Render all hackathon cards
    cards_html = "\n".join(
        _render_hackathon_card(h, i, analyses.get(h.url) if analyses else None)
        for i, h in enumerate(hackathons, 1)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hackathon Hunter — {count} New {noun}</title>
</head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,
             'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">

  <!-- Email wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background:#F1F5F9;min-height:100vh;">
    <tr>
      <td align="center" style="padding:32px 16px;">

        <!-- Main container -->
        <table width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px;width:100%;">

          <!-- ── HEADER BANNER ── -->
          <tr>
            <td style="background:linear-gradient(135deg,#0F172A 0%,#1E3A5F 50%,#0F172A 100%);
                       padding:36px 32px;border-radius:16px 16px 0 0;text-align:center;">
              <p style="margin:0 0 4px;color:#94A3B8;font-size:13px;letter-spacing:1px;
                        text-transform:uppercase;font-weight:600;">
                Hackathon Hunter
              </p>
              <h1 style="margin:0 0 8px;color:#F8FAFC;font-size:32px;font-weight:800;
                         letter-spacing:-0.5px;line-height:1.2;">
                🎉 {count} New {noun} Found
              </h1>
              <p style="margin:0 0 16px;color:#94A3B8;font-size:14px;">
                {now_str}
              </p>
              <div style="margin-top:12px;">
                {platform_pills}
              </div>
            </td>
          </tr>

          <!-- ── BODY ── -->
          <tr>
            <td style="background:#F8FAFC;padding:24px 24px 8px;
                       border-left:1px solid #E2E8F0;border-right:1px solid #E2E8F0;">
              <p style="margin:0 0 20px;color:#374151;font-size:15px;line-height:1.6;">
                Your Hackathon Hunter just discovered <strong>{count} new {noun.lower()}</strong>
                across <strong>{len(platforms)} platform(s)</strong>. Review them below and
                register before deadlines pass!
              </p>

              {cards_html}

            </td>
          </tr>

          <!-- ── FOOTER ── -->
          <tr>
            <td style="background:#1E293B;padding:24px 32px;border-radius:0 0 16px 16px;
                       text-align:center;">
              <p style="margin:0 0 8px;color:#94A3B8;font-size:13px;line-height:1.5;">
                Powered by <strong style="color:#F8FAFC;">Hackathon Hunter</strong>
              </p>
              <p style="margin:0;color:#64748B;font-size:12px;">
                To stop notifications, set
                <code style="background:#0F172A;color:#7DD3FC;padding:2px 6px;
                             border-radius:4px;font-size:11px;">HH_EMAIL_ENABLED=false</code>
                in your <code style="background:#0F172A;color:#7DD3FC;padding:2px 6px;
                                     border-radius:4px;font-size:11px;">.env</code> file.
              </p>
            </td>
          </tr>

        </table>
        <!-- /Main container -->

      </td>
    </tr>
  </table>
  <!-- /Email wrapper -->

</body>
</html>"""


def _get_readiness_html(analysis: dict[str, Any] | None) -> str:
    if not analysis:
        return """
        <div style="margin-top: 14px; padding: 8px 12px; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; font-size: 12px; color: #64748B;">
          🤖 Automation Status: <strong>NOT_ANALYZED</strong>
        </div>
        """
    status = analysis.get("analysis_status", "NOT_ANALYZED")
    if status == "ANALYZED":
        score = analysis.get("automation_score", 0)
        cls = analysis.get("classification", "LOW")
        rec = analysis.get("automation_recommendation", "MANUAL_ONLY")
        rec_color = "#16A34A" if rec == "AUTO_FILL_ONLY" else "#D97706" if rec == "AUTO_FILL_AND_REVIEW" else "#DC2626"
        return f"""
        <div style="margin-top: 14px; padding: 12px; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px;">
          <p style="margin: 0 0 8px 0; font-size: 13px; font-weight: 700; color: #1E293B;">🤖 Automation Readiness Report</p>
          <table width="100%" cellpadding="0" cellspacing="0" border="0" style="font-size: 12px; color: #475569;">
            <tr>
              <td style="padding: 2px 0; font-weight: 600;">Automation Score</td>
              <td style="padding: 2px 0; text-align: right; font-weight: 700; color: #2563EB;">{score}% ({cls})</td>
            </tr>
            <tr>
              <td style="padding: 2px 0;">Profile Fields</td>
              <td style="padding: 2px 0; text-align: right;">{analysis.get("profile_field_count", 0)}</td>
            </tr>
            <tr>
              <td style="padding: 2px 0;">Question Fields</td>
              <td style="padding: 2px 0; text-align: right;">{analysis.get("question_field_count", 0)}</td>
            </tr>
            <tr>
              <td style="padding: 2px 0;">Team Fields</td>
              <td style="padding: 2px 0; text-align: right;">{analysis.get("team_field_count", 0)}</td>
            </tr>
            <tr>
              <td style="padding: 2px 0;">Consent Fields</td>
              <td style="padding: 2px 0; text-align: right;">{analysis.get("consent_field_count", 0)}</td>
            </tr>
            <tr>
              <td style="padding: 2px 0;">Unknown Fields</td>
              <td style="padding: 2px 0; text-align: right;">{analysis.get("unknown_field_count", 0)}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0 0 0; font-weight: 600; border-top: 1px dashed #E2E8F0;">Recommended Action</td>
              <td style="padding: 6px 0 0 0; text-align: right; font-weight: 700; color: {rec_color}; border-top: 1px dashed #E2E8F0;">{rec}</td>
            </tr>
          </table>
        </div>
        """
    else:
        return f"""
        <div style="margin-top: 14px; padding: 8px 12px; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; font-size: 12px; color: #64748B;">
          🤖 Automation Status: <strong style="color: #DC2626;">{status}</strong>
        </div>
        """
