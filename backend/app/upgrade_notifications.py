"""SMTP-based upgrade notification service.

Sends plain-English upgrade notification emails to all active users when a
new application version is released. Uses the existing SMTP infrastructure
(configured via notifications.send_invitation_email) to deliver messages.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_upgrade_email_body(
    recipient_name: str,
    version_number: str,
    improvements: list[dict[str, str]],
) -> str:
    """Build a plain-English upgrade notification email body.

    Args:
        recipient_name: The user's full name.
        version_number: The new version number (e.g. "2.1.0").
        improvements: List of dicts with "title" and "description" keys,
            written in plain non-technical language.
    """
    items = "\n".join(
        f"• {item['title']} — {item['description']}" for item in improvements
    )

    return f"""Hello {recipient_name},

We've updated the KFL Aviation DMS to version {version_number}. Here's what's new and what it means for you:

{items}

You don't need to do anything — the system is ready to use. If you notice anything unusual or have questions, contact your system administrator.

Thank you,
KFL Aviation DMS team"""


DEFAULT_IMPROVEMENTS: list[dict[str, str]] = [
    {
        "title": "Clearer aircraft status tags",
        "description": "Aircraft now show easy-to-read status tags (Serviceable, Grounded, Standby, Deployed) so you can see at a glance which planes are ready to fly.",
    },
    {
        "title": "Department-specific audit dashboards",
        "description": "Quality, Safety, and Security leads now have their own dashboard views showing only the audit findings for their department.",
    },
    {
        "title": "Invite multiple people to the same role",
        "description": "You can now invite several people to the same role at once (for example, multiple flight operations officers) instead of one at a time.",
    },
    {
        "title": "Download PDF risk assessments and mission sheets",
        "description": "You can now download formatted PDF versions of your risk assessments and mission sheets that match KFL templates.",
    },
    {
        "title": "Search everything from one place",
        "description": "A new search bar at the top of every page lets you search across documents, audits, licenses, aircraft, and missions.",
    },
    {
        "title": "Faster issue tracking",
        "description": "Feedback and issue reports are now tracked in Zoho BugTracker so they get resolved faster.",
    },
]


def get_default_improvements() -> list[dict[str, str]]:
    """Return the default set of plain-English improvement descriptions."""
    return list(DEFAULT_IMPROVEMENTS)


def format_improvements_for_api(improvements: list[dict[str, str]]) -> list[dict[str, str]]:
    """Validate and format improvement items for API storage.

    Each item must have "title" and "description" keys.
    """
    formatted: list[dict[str, str]] = []
    for item in improvements:
        title = item.get("title", "").strip()
        description = item.get("description", "").strip()
        if title and description:
            formatted.append({"title": title, "description": description})
    return formatted
