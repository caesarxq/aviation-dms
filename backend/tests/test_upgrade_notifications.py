import asyncio
import uuid

from fastapi.testclient import TestClient

from app import notifications
from app.database import get_db
from app.main import app
from app.upgrade_notifications import build_upgrade_email_body

client = TestClient(app)


def test_upgrade_email_uses_release_notes_instead_of_unrelated_defaults():
    body = build_upgrade_email_body("Aviation User", "3.2.0", "Simpler aircraft status labels\nClearer maintenance reminders")

    assert "Simpler aircraft status labels" in body
    assert "Clearer maintenance reminders" in body
    assert "Clearer aircraft status tags" not in body


def test_upgrade_notification_fails_closed_when_smtp_is_not_ready(monkeypatch):
    version_id = f"VER-{uuid.uuid4().hex[:8]}"

    async def insert_version():
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO app_versions (version_id, version_number, released_at, released_by, changelog_non_technical, changelog_technical, notification_sent, created_at) VALUES (?,?,?,?,?,?,0,?)",
                (version_id, "3.2.0", "2026-11-27T00:00:00Z", "u-admin", "Simpler aircraft status labels", "technical", "2026-11-27T00:00:00Z"),
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(insert_version())
    monkeypatch.setattr(notifications, "NOTIFICATION_ENABLED", False)
    monkeypatch.setattr(notifications, "SMTP_HOST", "")

    response = client.post(f"/api/p0/app-versions/{version_id}/notify", headers={"X-Role": "system_admin", "X-Actor": "admin"})
    assert response.status_code == 503

    async def get_notification_sent():
        db = await get_db()
        try:
            row = await (await db.execute("SELECT notification_sent FROM app_versions WHERE version_id = ?", (version_id,))).fetchone()
            return row["notification_sent"] if row else None
        finally:
            await db.close()

    assert asyncio.run(get_notification_sent()) == 0


def test_partial_upgrade_delivery_reports_each_recipient_and_stays_retryable(monkeypatch):
    version_id = f"VER-{uuid.uuid4().hex[:8]}"

    async def seed_version_and_get_recipients():
        db = await get_db()
        try:
            recipients = await (await db.execute(
                "SELECT email FROM users WHERE is_active = 1 AND email IS NOT NULL AND email != '' ORDER BY email"
            )).fetchall()
            await db.execute(
                "INSERT INTO app_versions (version_id, version_number, released_at, released_by, changelog_non_technical, changelog_technical, notification_sent, created_at) VALUES (?,?,?,?,?,?,0,?)",
                (version_id, "3.2.1", "2026-11-27T00:00:00Z", "u-admin", "Improved release notes", "technical", "2026-11-27T00:00:00Z"),
            )
            await db.commit()
            return [row["email"] for row in recipients]
        finally:
            await db.close()

    recipients = asyncio.run(seed_version_and_get_recipients())
    assert recipients
    monkeypatch.setattr(notifications, "NOTIFICATION_ENABLED", True)
    monkeypatch.setattr(notifications, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(notifications, "SMTP_USER", "test-user")
    monkeypatch.setattr(notifications, "SMTP_PASS", "test-password")
    monkeypatch.setattr(notifications, "SMTP_FROM_CONFIGURED", True)

    def send_email(email, *_args, **_kwargs):
        return email != recipients[-1]

    monkeypatch.setattr(notifications, "send_email", send_email)
    response = client.post(
        f"/api/p0/app-versions/{version_id}/notify",
        headers={"X-Role": "system_admin", "X-Actor": "admin"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["notification_status"] == "partial"
    assert payload["notifications_failed"] == 1
    statuses = {entry["email"]: entry["status"] for entry in payload["recipient_results"]}
    assert statuses[recipients[-1]] == "failed"
    assert all(status == "sent" for email, status in statuses.items() if email != recipients[-1])

    async def read_notification_sent():
        db = await get_db()
        try:
            row = await (await db.execute(
                "SELECT notification_sent FROM app_versions WHERE version_id = ?", (version_id,)
            )).fetchone()
            return row["notification_sent"] if row else None
        finally:
            await db.close()

    assert asyncio.run(read_notification_sent()) == 0
