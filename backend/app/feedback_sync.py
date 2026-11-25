"""Zoho integration for feedback sync.

Handles syncing feedback records to Zoho Forms and Zoho Sheets.
All operations are best-effort: failures are logged but never block
the primary feedback submission flow.
"""

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from app.database import get_db

logger = logging.getLogger(__name__)

# Configuration from environment
ZOHO_ACCESS_TOKEN = os.getenv("ZOHO_ACCESS_TOKEN", "")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN", "")
ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID", "")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "")
ZOHO_FORM_ID = os.getenv("ZOHO_FORM_ID", "")
ZOHO_SHEET_ID = os.getenv("ZOHO_SHEET_ID", "")
ZOHO_API_BASE = "https://www.zohoapis.com"


def _is_configured() -> bool:
    """Check if Zoho integration is minimally configured."""
    return bool(ZOHO_ACCESS_TOKEN and ZOHO_FORM_ID and ZOHO_SHEET_ID)


async def _get_access_token() -> str:
    """Get a valid Zoho access token, refreshing if needed."""
    if ZOHO_ACCESS_TOKEN:
        return ZOHO_ACCESS_TOKEN

    # If we have refresh token credentials, attempt to refresh
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


async def enqueue_feedback_create(feedback_id: str) -> None:
    """Queue a feedback record for Zoho sync.

    This is called immediately after a feedback record is created in the
    local database. It attempts to sync to Zoho Forms and Zoho Sheets.
    Failures are logged but never raised - the sync is best-effort.
    """
    if not _is_configured():
        logger.debug("Zoho integration not configured, skipping sync for %s", feedback_id)
        return

    try:
        from app.db import get_db

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM feedback WHERE feedback_id = ?",
                (feedback_id,),
            )
            row = await cursor.fetchone()
            if not row:
                logger.warning("Feedback %s not found for Zoho sync", feedback_id)
                return

            feedback = dict(row)
            await _sync_feedback_to_zoho(feedback)
        finally:
            await db.close()
    except Exception as exc:
        logger.exception("Failed to enqueue feedback sync for %s: %s", feedback_id, exc)


async def _sync_feedback_to_zoho(feedback: dict) -> None:
    """Sync a feedback record to Zoho Forms and Zoho Sheets.

    Attempts both destinations independently - a failure in one does not
    prevent the other from being attempted.
    """
    access_token = await _get_access_token()
    if not access_token:
        logger.warning("No Zoho access token available, skipping sync for %s", feedback["feedback_id"])
        return

    # Sync to Zoho Forms (create form record)
    form_result = await _submit_to_zoho_form(access_token, feedback)
    if form_result and form_result.get("form_id"):
        await _update_zoho_form_record(feedback["feedback_id"], form_result["form_id"], "synced")
    else:
        logger.warning("Failed to sync feedback %s to Zoho Forms", feedback["feedback_id"])

    # Sync to Zoho Sheets (append row)
    sheet_result = await _append_to_zoho_sheet(access_token, feedback)
    if sheet_result and sheet_result.get("row_id"):
        await _update_zoho_sheet_row(feedback["feedback_id"], sheet_result["row_id"], "synced")
    else:
        logger.warning("Failed to sync feedback %s to Zoho Sheets", feedback["feedback_id"])


async def _submit_to_zoho_form(access_token: str, feedback: dict) -> Optional[dict]:
    """Submit feedback as a Zoho Form submission.

    Returns the form submission record on success, None on failure.
    """
    url = f"{ZOHO_API_BASE}/forms/v2/forms/{ZOHO_FORM_ID}/submissions"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "form_data": {
            "Feedback_ID": feedback.get("feedback_id", ""),
            "Ticket_Number": feedback.get("ticket_number", ""),
            "Issue_Type": feedback.get("issue_type", ""),
            "App_Area": feedback.get("app_area", ""),
            "Goal": feedback.get("goal", ""),
            "Impact": feedback.get("impact", ""),
            "Priority": feedback.get("priority", "P3"),
            "Contact Email": feedback.get("contact", ""),
            "Status": feedback.get("status", "new"),
            "Created_At": feedback.get("created_at", ""),
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code in (200, 201):
                data = resp.json()
                form_data = data.get("form_data", {})
                return {
                    "form_id": form_data.get("form_id", ""),
                    "submission_id": form_data.get("submission_id", ""),
                }
            else:
                logger.warning(
                    "Zoho Forms submission failed: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
    except Exception as exc:
        logger.exception("Error submitting to Zoho Forms: %s", exc)
    return None


async def _append_to_zoho_sheet(access_token: str, feedback: dict) -> Optional[dict]:
    """Append feedback as a row to Zoho Sheet.

    Returns the row info on success, None on failure.
    """
    url = f"{ZOHO_API_BASE}/sheet/v2/spreadsheets/{ZOHO_SHEET_ID}/rows"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "data": [
            {
                "row_data": [
                    feedback.get("feedback_id", ""),
                    feedback.get("ticket_number", ""),
                    feedback.get("issue_type", ""),
                    feedback.get("app_area", ""),
                    feedback.get("goal", ""),
                    feedback.get("impact", ""),
                    feedback.get("priority", "P3"),
                    feedback.get("contact", ""),
                    feedback.get("status", "new"),
                    feedback.get("created_at", ""),
                ]
            }
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code in (200, 201):
                data = resp.json()
                result_data = data.get("data", {})
                return {
                    "row_id": result_data.get("row_id", ""),
                    "sheet_id": ZOHO_SHEET_ID,
                }
            else:
                logger.warning(
                    "Zoho Sheets append failed: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
    except Exception as exc:
        logger.exception("Error appending to Zoho Sheet: %s", exc)
    return None


async def _update_zoho_form_record(feedback_id: str, form_id: str, status: str) -> None:
    """Update the feedback record with the Zoho form record ID."""
    from app.database import get_db

    db = await get_db()
    try:
        await db.execute(
            "UPDATE feedback SET zoho_form_id = ?, zoho_form_sync_state = ? WHERE feedback_id = ?",
            (form_id, status, feedback_id),
        )
        await db.commit()
    except Exception as exc:
        logger.exception("Failed to update Zoho form record for %s: %s", feedback_id, exc)
    finally:
        await db.close()


async def _update_zoho_sheet_row(feedback_id: str, row_id: str, status: str) -> None:
    """Update the feedback record with the Zoho sheet row ID."""
    from app.database import get_db

    db = await get_db()
    try:
        await db.execute(
            "UPDATE feedback SET zoho_sheet_row_id = ?, zoho_form_sync_state = ? WHERE feedback_id = ?",
            (row_id, status, feedback_id),
        )
        await db.commit()
    except Exception as exc:
        logger.exception("Failed to update Zoho sheet row for %s: %s", feedback_id, exc)
    finally:
        await db.close()


async def sync_all_pending() -> int:
    """Sync all pending feedback records to Zoho.

    Returns the number of records successfully synced.
    """
    from app.database import get_db

    if not _is_configured():
        logger.warning("Zoho integration not configured, skipping sync_all")
        return 0

    access_token = await _get_access_token()
    if not access_token:
        logger.warning("No Zoho access token available for sync_all")
        return 0

    c = sqlite3.connect("data/dms.db")
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT * FROM feedback WHERE zoho_form_sync_state = 'pending' LIMIT 50"
    ).fetchall()
    c.close()

    synced = 0
    for row in rows:
        feedback = dict(row)
        try:
            await _sync_feedback_to_zoho(feedback)
            synced += 1
        except Exception as exc:
            logger.exception("Failed to sync %s: %s", feedback["feedback_id"], exc)

    return synced


async def handle_zoho_webhook(webhook_data: dict) -> dict:
    """
    Handle incoming webhook from Zoho Forms/Sheets.
    
    Expected webhook payload from Zoho:
    - For Forms: { "form_id": "...", "submission_id": "...", "form_data": {...} }
    - For Sheets: { "sheet_id": "...", "row_id": "...", "row_data": [...] }
    """
    logger.info("Received Zoho webhook: %s", webhook_data)
    
    # Extract feedback_id from webhook data
    feedback_id = None
    zoho_status = None
    
    # Try to find feedback_id in form_data
    form_data = webhook_data.get("form_data", {})
    if form_data:
        feedback_id = form_data.get("Feedback_ID")
        zoho_status = form_data.get("Status")
    
    # Try sheet row data
    if not feedback_id:
        row_data = webhook_data.get("row_data", [])
        if row_data and len(row_data) > 0:
            feedback_id = row_data[0]  # First column is feedback_id
            zoho_status = row_data[8] if len(row_data) > 8 else None  # Status column
    
    if not feedback_id:
        return {"success": False, "error": "No feedback_id found in webhook data"}
    
    # Update local feedback record with Zoho status
    if zoho_status:
        local_status = _map_zoho_to_local_status(zoho_status)
        db = await get_db()
        try:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                """UPDATE feedback SET 
                    status = ?, 
                    zoho_form_sync_state = 'synced',
                    updated_at = ?,
                    updated_by = 'zoho_webhook'
                WHERE feedback_id = ?""",
                (local_status, now, feedback_id),
            )
            await db.commit()
            logger.info("Updated feedback %s status to %s from Zoho webhook", feedback_id, local_status)
            return {"success": True, "feedback_id": feedback_id, "status": local_status}
        except Exception as exc:
            logger.exception("Failed to update feedback %s from webhook: %s", feedback_id, exc)
            return {"success": False, "error": str(exc)}
        finally:
            await db.close()
    
    return {"success": True, "feedback_id": feedback_id, "status": "no_status_update"}


async def sync_feedback_from_zoho(limit: int = 50) -> int:
    """
    Cron job: Pull updated feedback from Zoho Sheets.
    Call this periodically (e.g., every 5 minutes) to sync Zoho -> local.
    """
    if not _is_configured():
        logger.debug("Zoho integration not configured, skipping sync_from_zoho")
        return 0

    access_token = await _get_access_token()
    if not access_token:
        logger.warning("No Zoho access token available for sync_from_zoho")
        return 0

    # Read all rows from Zoho Sheet
    url = f"{ZOHO_API_BASE}/sheet/v2/spreadsheets/{ZOHO_SHEET_ID}/rows"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                logger.warning("Failed to fetch Zoho Sheet rows: %s %s", resp.status_code, resp.text[:200])
                return 0
            data = resp.json()
    except Exception as exc:
        logger.exception("Error fetching Zoho Sheet rows: %s", exc)
        return 0

    rows = data.get("data", [])
    synced = 0
    
    for row in rows:
        row_data = row.get("row_data", [])
        if not row_data or len(row_data) < 9:
            continue
        
        feedback_id = row_data[0]
        zoho_status = row_data[8]  # Status column
        
        if zoho_status:
            local_status = _map_zoho_to_local_status(zoho_status)
            db = await get_db()
            try:
                # Check current status
                cursor = await db.execute(
                    "SELECT status FROM feedback WHERE feedback_id = ?", (feedback_id,)
                )
                current = await cursor.fetchone()
                if current and current["status"] != local_status:
                    now = datetime.now(timezone.utc).isoformat()
                    await db.execute(
                        """UPDATE feedback SET 
                            status = ?, 
                            updated_at = ?,
                            updated_by = 'zoho_cron'
                        WHERE feedback_id = ?""",
                        (local_status, now, feedback_id),
                    )
                    await db.commit()
                    logger.info("Cron synced feedback %s status to %s from Zoho", feedback_id, local_status)
                    synced += 1
            except Exception as exc:
                logger.exception("Failed to cron-sync feedback %s: %s", feedback_id, exc)
            finally:
                await db.close()
    
    return synced


def _map_zoho_to_local_status(zoho_status: str) -> str:
    """Map Zoho Form/Sheet status back to local feedback status."""
    mapping = {
        "Open": "new",
        "New": "new",
        "In Progress": "in_progress",
        "Fixed": "resolved",
        "Resolved": "resolved",
        "Closed": "closed",
        "Rejected": "rejected",
        "Duplicate": "duplicate",
    }
    return mapping.get(zoho_status, "new")