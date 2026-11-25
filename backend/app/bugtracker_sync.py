"""Zoho BugTracker integration for feedback/ticket sync.

Replaces the Zoho Forms + Zoho Sheets dual-write with a proper issue tracker.
All operations are best-effort: failures are logged but never block
the primary feedback submission flow.

BugTracker project: https://bugtracker.zoho.com/portal/kfldotke
Project ID: 2730932000000114802
Dashboard ID: 2730932000000114857
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Configuration from environment or protected, read-only secret files.
def _read_config_value(name: str, default: str = "") -> str:
    secret_path = os.getenv(f"{name}_FILE")
    if secret_path:
        try:
            return Path(secret_path).read_text(encoding="utf-8").strip()
        except OSError:
            logger.error("Unable to read configured secret file for %s", name)
            return ""
    return os.getenv(name, default)


ZOHO_ACCESS_TOKEN = _read_config_value("ZOHO_ACCESS_TOKEN")
ZOHO_REFRESH_TOKEN = _read_config_value("ZOHO_REFRESH_TOKEN")
ZOHO_CLIENT_ID = _read_config_value("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = _read_config_value("ZOHO_CLIENT_SECRET")
ZOHO_BUGTRACKER_PORTAL = os.getenv("ZOHO_BUGTRACKER_PORTAL", "kfldotke")
ZOHO_BUGTRACKER_PROJECT_ID = os.getenv("ZOHO_BUGTRACKER_PROJECT_ID", "2730932000000114802")
ZOHO_API_BASE = "https://bugtracker.zoho.com/api/v1"

# Field mapping: Feedback field -> BugTracker custom field name
FIELD_MAP = {
    "feedback_id": "Feedback ID",
    "ticket_number": "Ticket Number",
    "issue_type": "Issue Type",
    "app_area": "App Area",
    "goal": "Goal",
    "impact": "Impact",
    "priority": "Priority",
    "contact": "Contact Email",
    "status": "Status",
    "created_at": "Created At",
}


def _is_configured() -> bool:
    """Check whether BugTracker OAuth credentials and project configuration exist."""
    has_access_token = bool(ZOHO_ACCESS_TOKEN)
    has_refresh_credentials = bool(ZOHO_REFRESH_TOKEN and ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET)
    return bool((has_access_token or has_refresh_credentials) and ZOHO_BUGTRACKER_PROJECT_ID)


async def _get_access_token() -> str:
    """Get a valid Zoho access token, refreshing if needed."""
    if ZOHO_ACCESS_TOKEN:
        return ZOHO_ACCESS_TOKEN

    if ZOHO_REFRESH_TOKEN and ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    "https://accounts.zoho.com/oauth/v2/token",
                    data={
                        "refresh_token": ZOHO_REFRESH_TOKEN,
                        "client_id": ZOHO_CLIENT_ID,
                        "client_secret": ZOHO_CLIENT_SECRET,
                        "grant_type": "refresh_token",
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("access_token", ZOHO_ACCESS_TOKEN)
            except Exception:
                pass

    return ZOHO_ACCESS_TOKEN or ""


def _map_feedback_to_bugtracker(feedback: dict) -> dict:
    """Map a local feedback record to BugTracker bug fields."""
    return {
        "project_id": ZOHO_BUGTRACKER_PROJECT_ID,
        "title": f"[{feedback.get('ticket_number', '')}] {feedback.get('issue_type', 'Feedback')} — {feedback.get('app_area', '')}",
        "description": (
            f"**Ticket:** {feedback.get('ticket_number', '')}\n"
            f"**Issue Type:** {feedback.get('issue_type', '')}\n"
            f"**App Area:** {feedback.get('app_area', '')}\n"
            f"**Goal:** {feedback.get('goal', '')}\n"
            f"**Reproduction Steps:** {feedback.get('reproduction_steps', '')}\n"
            f"**Expected Result:** {feedback.get('expected_result', '')}\n"
            f"**Actual Result:** {feedback.get('actual_result', '')}\n"
            f"**Impact:** {feedback.get('impact', '')}\n"
            f"**Contact:** {feedback.get('contact', '')}\n"
            f"**Created:** {feedback.get('created_at', '')}\n"
        ),
        "priority": _map_priority(feedback.get("priority", "P3")),
        "status": _map_status(feedback.get("status", "new")),
        "custom_fields": {
            "Feedback ID": feedback.get("feedback_id", ""),
            "Ticket Number": feedback.get("ticket_number", ""),
            "Issue Type": feedback.get("issue_type", ""),
            "App Area": feedback.get("app_area", ""),
            "Goal": feedback.get("goal", ""),
            "Impact": feedback.get("impact", ""),
            "Contact Email": feedback.get("contact", ""),
            "Created At": feedback.get("created_at", ""),
        },
    }


def _map_priority(priority: str) -> str:
    """Map local priority to BugTracker priority."""
    mapping = {
        "P1": "High",
        "P2": "Medium",
        "P3": "Low",
        "P4": "Low",
    }
    return mapping.get(priority, "Low")


def _map_status(status: str) -> str:
    """Map local status to BugTracker status."""
    mapping = {
        "new": "Open",
        "in_progress": "In Progress",
        "resolved": "Fixed",
        "closed": "Closed",
        "rejected": "Rejected",
    }
    return mapping.get(status, "Open")


def _map_bugtracker_to_status(bt_status: str) -> str:
    """Map BugTracker status back to local feedback status."""
    mapping = {
        "Open": "new",
        "In Progress": "in_progress",
        "Fixed": "resolved",
        "Closed": "closed",
        "Rejected": "rejected",
    }
    return mapping.get(bt_status, "new")


async def enqueue_feedback_create(feedback_id: str) -> None:
    """Queue a feedback record for BugTracker sync.

    Called immediately after a feedback record is created in the local
    database. Attempts to create a corresponding bug in BugTracker.
    Failures are logged but never raised - the sync is best-effort.
    """
    if not _is_configured():
        logger.debug("Zoho BugTracker not configured, skipping sync for %s", feedback_id)
        return

    try:
        from app.database import get_db

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM feedback WHERE feedback_id = ?",
                (feedback_id,),
            )
            row = await cursor.fetchone()
            if not row:
                logger.warning("Feedback %s not found for BugTracker sync", feedback_id)
                return

            feedback = dict(row)
            await _create_bug_in_bugtracker(feedback)
        finally:
            await db.close()
    except Exception as exc:
        logger.exception("Failed to enqueue feedback sync for %s: %s", feedback_id, exc)


async def _create_bug_in_bugtracker(feedback: dict) -> Optional[str]:
    """Create a bug in Zoho BugTracker. Returns the bug ID on success."""
    access_token = await _get_access_token()
    if not access_token:
        logger.warning("No Zoho access token available, skipping BugTracker sync for %s", feedback["feedback_id"])
        return None

    payload = _map_feedback_to_bugtracker(feedback)

    # BugTracker API: create bug
    url = f"{ZOHO_API_BASE}/projects/{ZOHO_BUGTRACKER_PROJECT_ID}/bugs"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code in (200, 201):
                data = resp.json()
                bug_id = data.get("bug_id") or data.get("id") or data.get("bug", {}).get("bug_id")
                if bug_id:
                    await _update_feedback_bugtracker_id(feedback["feedback_id"], str(bug_id), "synced")
                    logger.info("Created BugTracker bug %s for feedback %s", bug_id, feedback["feedback_id"])
                    return str(bug_id)
            else:
                logger.warning(
                    "BugTracker bug creation failed: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
    except Exception as exc:
        logger.exception("Error creating BugTracker bug: %s", exc)
    return None


async def _update_feedback_bugtracker_id(feedback_id: str, bugtracker_id: str, state: str) -> None:
    """Update the feedback record with the BugTracker bug ID and URL."""
    from app.database import get_db

    bugtracker_url = (
        f"https://bugtracker.zoho.com/portal/{ZOHO_BUGTRACKER_PORTAL}"
        f"#zp/projects/{ZOHO_BUGTRACKER_PROJECT_ID}/bugs/{bugtracker_id}"
    )

    db = await get_db()
    try:
        await db.execute(
            """UPDATE feedback
               SET bugtracker_id = ?, bugtracker_url = ?, bugtracker_sync_state = ?
               WHERE feedback_id = ?""",
            (bugtracker_id, bugtracker_url, state, feedback_id),
        )
        await db.commit()
    except Exception as exc:
        logger.exception("Failed to update BugTracker ID for %s: %s", feedback_id, exc)
    finally:
        await db.close()


async def sync_all_pending() -> int:
    """Sync all pending feedback records to BugTracker.

    Returns the number of records successfully synced.
    """
    if not _is_configured():
        logger.warning("Zoho BugTracker not configured, skipping sync_all")
        return 0

    access_token = await _get_access_token()
    if not access_token:
        logger.warning("No Zoho access token available for sync_all")
        return 0

    import sqlite3

    db_path = os.getenv("DMS_DB_PATH", "data/dms.db")
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT * FROM feedback WHERE (bugtracker_sync_state = 'pending' OR bugtracker_id IS NULL) LIMIT 50"
    ).fetchall()
    c.close()

    synced = 0
    for row in rows:
        feedback = dict(row)
        try:
            bug_id = await _create_bug_in_bugtracker(feedback)
            if bug_id:
                synced += 1
        except Exception as exc:
            logger.exception("Failed to sync %s: %s", feedback["feedback_id"], exc)

    return synced


async def sync_bugtracker_updates() -> int:
    """Pull status updates from BugTracker and update local feedback records.

    Called periodically (e.g. via cron) to keep local status in sync
    with BugTracker bug status changes.
    Returns the number of records updated.
    """
    if not _is_configured():
        return 0

    access_token = await _get_access_token()
    if not access_token:
        return 0

    import sqlite3

    db_path = os.getenv("DMS_DB_PATH", "data/dms.db")
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT feedback_id, bugtracker_id FROM feedback WHERE bugtracker_id IS NOT NULL LIMIT 100"
    ).fetchall()
    c.close()

    updated = 0
    for row in rows:
        bug_id = row["bugtracker_id"]
        try:
            bt_status = await _get_bugtracker_bug_status(access_token, bug_id)
            if bt_status:
                local_status = _map_bugtracker_to_status(bt_status)
                from app.database import get_db

                db2 = await get_db()
                try:
                    await db2.execute(
                        "UPDATE feedback SET status = ?, bugtracker_sync_state = 'synced' WHERE feedback_id = ? AND status != ?",
                        (local_status, row["feedback_id"], local_status),
                    )
                    await db2.commit()
                    updated += 1
                finally:
                    await db2.close()
        except Exception as exc:
            logger.exception("Failed to pull BugTracker status for bug %s: %s", bug_id, exc)

    return updated


async def _get_bugtracker_bug_status(access_token: str, bug_id: str) -> Optional[str]:
    """Get the current status of a BugTracker bug."""
    url = f"{ZOHO_API_BASE}/projects/{ZOHO_BUGTRACKER_PROJECT_ID}/bugs/{bug_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                bug = data.get("bug", data)
                return bug.get("status") or bug.get("bug_status")
    except Exception as exc:
        logger.exception("Error fetching BugTracker bug %s status: %s", bug_id, exc)
    return None


async def handle_bugtracker_webhook(webhook_data: dict) -> dict:
    """
    Handle incoming webhook from Zoho BugTracker.

    Expected webhook payload from BugTracker:
    {
        "bug": {
            "bug_id": "2730932000000123456",
            "status": "Fixed",
            "project_id": "2730932000000114802",
            ...
        },
        "event": "bug_updated",
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    logger.info("Received BugTracker webhook: %s", webhook_data)

    # Extract bug info from webhook
    bug = webhook_data.get("bug", {})
    bug_id = bug.get("bug_id") or bug.get("id")
    bt_status = bug.get("status") or bug.get("bug_status")

    if not bug_id:
        # Try alternative field names
        bug_id = webhook_data.get("bug_id") or webhook_data.get("id")

    if not bt_status:
        bt_status = webhook_data.get("status") or webhook_data.get("bug_status")

    if not bug_id:
        return {"success": False, "error": "No bug_id found in webhook data"}

    # Find local feedback by bugtracker_id
    from app.database import get_db

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT feedback_id FROM feedback WHERE bugtracker_id = ?", (str(bug_id),)
        )
        row = await cursor.fetchone()
        if not row:
            logger.warning("BugTracker webhook: no local feedback found for bug_id %s", bug_id)
            return {"success": False, "error": f"No local feedback for bug {bug_id}", "bug_id": str(bug_id)}

        feedback_id = row["feedback_id"]

        if bt_status:
            local_status = _map_bugtracker_to_status(bt_status)
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                """UPDATE feedback
                   SET status = ?, bugtracker_sync_state = 'synced', updated_at = ?, updated_by = 'bugtracker_webhook'
                   WHERE feedback_id = ? AND status != ?""",
                (local_status, now, feedback_id, local_status),
            )
            await db.commit()
            logger.info("Updated feedback %s status to %s from BugTracker webhook", feedback_id, local_status)
            return {"success": True, "feedback_id": feedback_id, "bug_id": str(bug_id), "status": local_status}

    except Exception as exc:
        logger.exception("Failed to process BugTracker webhook for bug %s: %s", bug_id, exc)
        return {"success": False, "error": str(exc), "bug_id": str(bug_id)}
    finally:
        await db.close()

    return {"success": True, "bug_id": str(bug_id), "status": "no_status_update"}
