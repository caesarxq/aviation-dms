"""Notification and escalation service for aviation DMS."""
import os
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import asyncio

# Notification configuration from environment
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "dms@kfl-aviation.local")
NOTIFICATION_ENABLED = os.getenv("NOTIFICATION_ENABLED", "false").lower() == "true"

# Escalation thresholds (hours before deadline)
ESCALATION_THRESHOLDS = {
    "critical": [24, 4, 1],   # 24h, 4h, 1h before
    "high": [48, 8],          # 48h, 8h before
    "medium": [72, 24],       # 72h, 24h before
    "low": [168],             # 1 week before
}

# In-memory notification log (would be DB in production)
_notification_log: List[Dict] = []


def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email notification. Returns True on success."""
    if not NOTIFICATION_ENABLED or not SMTP_HOST:
        # Log only in dev mode
        _notification_log.append({
            "to": to, "subject": subject, "body": body[:200],
            "sent_at": datetime.now().isoformat(), "status": "logged (no SMTP)",
        })
        return True

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        _notification_log.append({
            "to": to, "subject": subject, "body": body[:200],
            "sent_at": datetime.now().isoformat(), "status": "sent",
        })
        return True
    except Exception as e:
        _notification_log.append({
            "to": to, "subject": subject, "body": body[:200],
            "sent_at": datetime.now().isoformat(), "status": f"failed: {e}",
        })
        return False


def get_notification_log(limit: int = 50) -> List[Dict]:
    """Return recent notification log entries."""
    return _notification_log[-limit:]


def clear_notification_log():
    """Clear the notification log."""
    _notification_log.clear()


async def check_and_notify(db, recipient_email: str = "safety@kfl-aviation.local"):
    """Check deadlines and send notifications for approaching/overdue items."""
    now = datetime.now()
    notifications_sent = 0

    # Check document reviews due within 48h
    cursor = await db.execute(
        "SELECT document_id, title, review_due_date FROM documents WHERE review_due_date IS NOT NULL"
    )
    for row in await cursor.fetchall():
        r = dict(row)
        due = datetime.fromisoformat(r["review_due_date"])
        hours_until = (due - now).total_seconds() / 3600
        if 0 < hours_until <= 48:
            send_email(
                recipient_email,
                f"[KFL DMS] Document review due: {r['title']}",
                f"Document {r['document_id']} ({r['title']}) review is due on {r['review_due_date']}. "
                f"Please complete the review before the deadline.",
            )
            notifications_sent += 1
        elif hours_until <= 0:
            send_email(
                recipient_email,
                f"[KFL DMS] OVERDUE: Document review - {r['title']}",
                f"Document {r['document_id']} ({r['title']}) review was due on {r['review_due_date']} and is now overdue. "
                f"Immediate action required.",
            )
            notifications_sent += 1

    # Check occurrence MOR deadlines
    cursor = await db.execute(
        "SELECT occurrence_id, serial_number, title, mor_deadline FROM occurrences WHERE mor_required = 1 AND mor_deadline IS NOT NULL AND status != 'closed'"
    )
    for row in await cursor.fetchall():
        r = dict(row)
        due = datetime.fromisoformat(r["mor_deadline"])
        hours_until = (due - now).total_seconds() / 3600
        if hours_until <= 4:  # Critical: within 4 hours
            send_email(
                recipient_email,
                f"[KFL DMS] URGENT: MOR submission due - {r['serial_number']}",
                f"Occurrence {r['serial_number']} ({r['title']}) MOR submission is due at {r['mor_deadline']}. "
                f"Only {max(0, int(hours_until))} hours remaining. Submit immediately.",
            )
            notifications_sent += 1
        elif hours_until <= 24:
            send_email(
                recipient_email,
                f"[KFL DMS] MOR submission due soon - {r['serial_number']}",
                f"Occurrence {r['serial_number']} ({r['title']}) MOR submission is due at {r['mor_deadline']}. "
                f"Please submit the MOR report.",
            )
            notifications_sent += 1

    # Check corrective action due dates
    cursor = await db.execute(
        "SELECT car_id, title, due_date FROM corrective_actions WHERE due_date IS NOT NULL AND status NOT IN ('closed', 'verified')"
    )
    for row in await cursor.fetchall():
        r = dict(row)
        due = datetime.fromisoformat(r["due_date"])
        days_until = (due - now).days
        if days_until <= 3:
            send_email(
                recipient_email,
                f"[KFL DMS] CAR due soon: {r['title']}",
                f"Corrective action {r['car_id']} ({r['title']}) is due on {r['due_date']}. "
                f"Please complete the corrective action.",
            )
            notifications_sent += 1

    # Check ROC expiry (90-day notice)
    cursor = await db.execute("SELECT roc_id, roc_number, expiry_date FROM roc_register WHERE expiry_date IS NOT NULL")
    for row in await cursor.fetchall():
        r = dict(row)
        due = datetime.fromisoformat(r["expiry_date"])
        days_until = (due - now).days
        if days_until <= 90:
            send_email(
                recipient_email,
                f"[KFL DMS] ROC renewal notice: {r['roc_number']}",
                f"ROC {r['roc_number']} expires on {r['expiry_date']} ({days_until} days remaining). "
                f"Begin renewal process with KCAA.",
            )
            notifications_sent += 1

    return notifications_sent


class NotificationScheduler:
    """Background scheduler for deadline notifications."""

    def __init__(self, interval_seconds: int = 3600):
        self.interval = interval_seconds
        self._task = None
        self._running = False

    async def start(self):
        self._running = True
        self._task = asyncio.ensure_future(self._run_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self):
        while self._running:
            try:
                from app.database import get_db
                db = await get_db()
                try:
                    count = await check_and_notify(db)
                    if count > 0:
                        print(f"[NotificationScheduler] Sent {count} notifications")
                finally:
                    await db.close()
            except Exception as e:
                print(f"[NotificationScheduler] Error: {e}")
            await asyncio.sleep(self.interval)
