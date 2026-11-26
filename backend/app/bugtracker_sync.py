"""Zoho BugTracker integration for feedback/ticket sync.

Replaces the Zoho Forms + Zoho Sheets dual-write with a proper issue tracker.
All operations are best-effort: failures are logged but never block
the primary feedback submission flow.

BugTracker project: https://bugtracker.zoho.com/portal/kfldotke
Project ID: 2730932000000114802
Dashboard ID: 2730932000000114857
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

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
ZOHO_BUGTRACKER_PORTAL_ID = os.getenv("ZOHO_BUGTRACKER_PORTAL_ID", "")
ZOHO_BUGTRACKER_PROJECT_ID = os.getenv("ZOHO_BUGTRACKER_PROJECT_ID", "2730932000000114802")
# Zoho mounts bugs under /restapi/portal/{portal}/projects/{project}/bugs/.
# The previous /api/v1/projects/... path is not a Zoho route and returns the
# BugTracker HTML "Page Not Found" (HTTP 404).
ZOHO_API_BASE = "https://bugtracker.zoho.com/restapi"


def _api_portal() -> str:
    """Portal segment for API paths.

    Zoho accepts the numeric portal id or the portal link name. The id is
    preferred when configured, because a link name can be renamed.
    """
    return ZOHO_BUGTRACKER_PORTAL_ID or ZOHO_BUGTRACKER_PORTAL


def _bug_collection_url() -> str:
    """URL of the project's bug collection."""
    return (
        f"{ZOHO_API_BASE}/portal/{quote(_api_portal(), safe='')}"
        f"/projects/{quote(ZOHO_BUGTRACKER_PROJECT_ID, safe='')}/bugs/"
    )


def _bug_item_url(bug_id: str) -> str:
    """URL of a single bug."""
    return f"{_bug_collection_url()}{quote(str(bug_id), safe='')}/"


def _is_configured() -> bool:
    """Check whether BugTracker OAuth credentials and project configuration exist."""
    has_access_token = bool(ZOHO_ACCESS_TOKEN)
    has_refresh_credentials = bool(ZOHO_REFRESH_TOKEN and ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET)
    return bool((has_access_token or has_refresh_credentials) and ZOHO_BUGTRACKER_PROJECT_ID)


# Sync reads pages of feedback in bounded batches instead of a single LIMIT, so
# reconciling does not silently stop at the first 50/100 rows.
SYNC_BATCH_SIZE = 50

_TOKEN_CACHE: Dict[str, Any] = {"token": "", "expires_at": 0.0}
_TOKEN_LOCK = asyncio.Lock()
_TOKEN_DEFAULT_TTL_SECONDS = 3300
_TOKEN_MIN_TTL_SECONDS = 60


def _token_ttl_seconds(expires_in: Any) -> int:
    """Cache lifetime for a token, keeping a safety margin before it expires."""
    try:
        ttl = int(expires_in)
    except (TypeError, ValueError):
        return _TOKEN_DEFAULT_TTL_SECONDS
    return max(ttl - 60, _TOKEN_MIN_TTL_SECONDS)


def _reset_token_cache() -> None:
    """Drop the cached token (tests, and after a 401 from BugTracker)."""
    _TOKEN_CACHE["token"] = ""
    _TOKEN_CACHE["expires_at"] = 0.0


async def _drain_keyset(fetch_page) -> list:
    """Read every row from a keyset-paginated query.

    `fetch_page(after)` returns the next batch ordered by `feedback_id`, or an
    empty batch at the end. Keyset paging keeps advancing even when a row
    cannot be synced, so a permanently failing record cannot stall the loop.
    """
    rows: list = []
    after = ""
    while True:
        batch = await fetch_page(after)
        if not batch:
            return rows
        rows.extend(batch)
        after = str(batch[-1]["feedback_id"])



async def _get_access_token() -> str:
    """Return a usable Zoho access token, refreshing at most once per TTL.

    Zoho's token endpoint returns a ~1h token. Refreshing per API call burned
    one request per feedback row and made long syncs slower and rate-limit
    prone, so the token is cached in-process and refreshes are single-flight.
    """
    if ZOHO_ACCESS_TOKEN:
        return ZOHO_ACCESS_TOKEN

    if not (ZOHO_REFRESH_TOKEN and ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET):
        return ""

    async with _TOKEN_LOCK:
        now = time.monotonic()
        if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"]:
            return _TOKEN_CACHE["token"]

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
                    token = data.get("access_token") or ""
                    if token:
                        ttl = _token_ttl_seconds(data.get("expires_in"))
                        _TOKEN_CACHE["token"] = token
                        _TOKEN_CACHE["expires_at"] = now + ttl
                        return token
                else:
                    logger.warning(
                        "Zoho token refresh failed: %s", resp.status_code
                    )
            except Exception as exc:
                logger.exception("Error refreshing Zoho access token: %s", exc)

    return ""


def _map_feedback_to_bugtracker(feedback: dict) -> dict:
    """Map a local feedback record to BugTracker bug create fields.

    Only fields Zoho documents for `POST .../bugs/` are sent. The project is
    part of the URL, and Zoho rejects unknown members such as a nested
    `custom_fields` object, so the remaining detail goes into the description.
    """
    return {
        "title": (
            f"[{feedback.get('ticket_number', '')}] "
            f"{feedback.get('issue_type', 'Feedback')} — {feedback.get('app_area', '')}"
        )[:255],
        "description": (
            f"**Ticket:** {feedback.get('ticket_number', '')}\n"
            f"**Feedback ID:** {feedback.get('feedback_id', '')}\n"
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


def _map_bugtracker_to_status(bt_status: str) -> str:
    """Map BugTracker status back to local feedback status."""
    mapping = {
        "Open": "new",
        "Reopened": "new",
        "In Progress": "in_progress",
        "Fixed": "resolved",
        "Closed": "closed",
        "Rejected": "rejected",
        "Won't Fix": "rejected",
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

    # Zoho BugTracker: POST /restapi/portal/{portal}/projects/{project}/bugs/
    url = _bug_collection_url()
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    try:
        async with httpx.AsyncClient() as client:
            # Zoho Projects/BugTracker REST v1 reads create fields from a
            # form-encoded body. A JSON body is not parsed at all and the API
            # replies 400 {"error":{"code":6831,"message":"Input Parameter Missing"}}.
            resp = await client.post(url, headers=headers, data=payload, timeout=30)
            if resp.status_code in (200, 201):
                bug_id = _extract_bug_id(resp.json())
                if bug_id:
                    await _update_feedback_bugtracker_id(feedback["feedback_id"], bug_id, "synced")
                    logger.info("Created BugTracker bug %s for feedback %s", bug_id, feedback["feedback_id"])
                    return bug_id
                logger.warning(
                    "BugTracker create returned %s without a bug id: %s",
                    resp.status_code,
                    resp.text[:200],
                )
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

    from app.database import get_db

    db = await get_db()
    try:
        async def fetch_page(after: str) -> list:
            cursor = await db.execute(
                "SELECT * FROM feedback "
                "WHERE (bugtracker_sync_state = 'pending' OR bugtracker_id IS NULL) "
                "AND feedback_id > ? ORDER BY feedback_id LIMIT ?",
                (after, SYNC_BATCH_SIZE),
            )
            return [dict(row) for row in await cursor.fetchall()]

        rows = await _drain_keyset(fetch_page)
    finally:
        await db.close()

    synced = 0
    for feedback in rows:
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
        logger.warning("No Zoho access token available for status pull")
        return 0

    from app.database import get_db

    db = await get_db()
    try:
        async def fetch_page(after: str) -> list:
            cursor = await db.execute(
                "SELECT feedback_id, bugtracker_id FROM feedback "
                "WHERE bugtracker_id IS NOT NULL AND feedback_id > ? "
                "ORDER BY feedback_id LIMIT ?",
                (after, SYNC_BATCH_SIZE),
            )
            return [dict(row) for row in await cursor.fetchall()]

        rows = await _drain_keyset(fetch_page)
    finally:
        await db.close()

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
                    cursor = await db2.execute(
                        "UPDATE feedback SET status = ?, bugtracker_sync_state = 'synced' WHERE feedback_id = ? AND status != ?",
                        (local_status, row["feedback_id"], local_status),
                    )
                    await db2.commit()
                    if cursor.rowcount > 0:
                        updated += 1
                finally:
                    await db2.close()
        except Exception as exc:
            logger.exception("Failed to pull BugTracker status for bug %s: %s", bug_id, exc)

    return updated


def _extract_bug_id(payload: Any) -> Optional[str]:
    """Return the new bug's id from a BugTracker create response.

    Zoho answers `POST .../bugs/` with `{"bugs": [{"id_string": "..."}]}`; older
    payloads and wrappers use `id`, `bug_id`, or a single `bug` object.
    """
    candidates = []
    if isinstance(payload, dict):
        bugs = payload.get("bugs")
        if isinstance(bugs, list) and bugs:
            candidates.append(bugs[0])
        elif isinstance(payload.get("bug"), dict):
            candidates.append(payload["bug"])
        candidates.append(payload)

    for node in candidates:
        if not isinstance(node, dict):
            continue
        for key in ("id_string", "bug_id", "id"):
            value = node.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return None


def _extract_bug_status(payload: Any) -> Optional[str]:
    """Return the bug status name from a BugTracker bug response.

    Zoho returns the status as an object (`{"name": "Open"}`) in REST v1, but
    older payloads and the webhook carry a plain string under `status` or
    `bug_status`, so both shapes are accepted.
    """
    bug = payload
    if isinstance(payload, dict):
        if isinstance(payload.get("bugs"), list):
            if not payload["bugs"]:
                return None
            bug = payload["bugs"][0]
        elif isinstance(payload.get("bug"), dict):
            bug = payload["bug"]

    if not isinstance(bug, dict):
        return None

    status = bug.get("status") or bug.get("bug_status")
    if isinstance(status, dict):
        status = status.get("name") or status.get("type")
    if isinstance(status, str) and status.strip():
        return status.strip()
    return None


async def _get_bugtracker_bug_status(access_token: str, bug_id: str) -> Optional[str]:
    """Get the current status of a BugTracker bug."""
    url = _bug_item_url(bug_id)
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                return _extract_bug_status(resp.json())
            logger.warning(
                "BugTracker bug %s lookup failed: %s", bug_id, resp.status_code
            )
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
