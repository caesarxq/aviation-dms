import asyncio
import uuid
from fastapi.testclient import TestClient
from app import bugtracker_sync
from app.database import get_db, init_db
from app.main import app


def test_refresh_credentials_are_sufficient_to_configure_bugtracker(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "ZOHO_ACCESS_TOKEN", "")
    monkeypatch.setattr(bugtracker_sync, "ZOHO_REFRESH_TOKEN", "refresh-token")
    monkeypatch.setattr(bugtracker_sync, "ZOHO_CLIENT_ID", "client-id")
    monkeypatch.setattr(bugtracker_sync, "ZOHO_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(bugtracker_sync, "ZOHO_BUGTRACKER_PROJECT_ID", "project-id")

    assert bugtracker_sync._is_configured() is True


client = TestClient(app)


def _admin_headers():
    return {"X-Role": "system_admin", "X-Actor": "admin"}


def test_bugtracker_configuration_reads_secret_files(monkeypatch, tmp_path):
    secret_file = tmp_path / "zoho_refresh_token"
    secret_file.write_text("file-refresh-token\n", encoding="utf-8")
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "environment-token")
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN_FILE", str(secret_file))

    assert bugtracker_sync._read_config_value("ZOHO_REFRESH_TOKEN") == "file-refresh-token"


def test_legacy_sync_state_migrates_to_bugtracker_sync_state():
    response = client.post("/api/p0/feedback", json={
        "issue_type": "bug",
        "app_area": "migration-test",
        "goal": f"legacy-sync-state-{uuid.uuid4().hex}",
        "impact": "workaround",
        "observation_time": "2026-01-15T10:00:00Z",
        "contact": "pilot1",
    }, headers=_admin_headers())
    assert response.status_code == 201, response.text
    feedback_id = response.json()["feedback_id"]

    async def mark_legacy_state():
        db = await get_db()
        try:
            await db.execute(
                "UPDATE feedback SET zoho_form_sync_state = 'synced' WHERE feedback_id = ?",
                (feedback_id,),
            )
            await db.execute("ALTER TABLE feedback DROP COLUMN bugtracker_sync_state")
            await db.commit()
        finally:
            await db.close()

    asyncio.run(mark_legacy_state())
    asyncio.run(init_db())

    async def read_migrated_state():
        db = await get_db()
        try:
            row = await (await db.execute(
                "SELECT bugtracker_sync_state FROM feedback WHERE feedback_id = ?", (feedback_id,)
            )).fetchone()
            return row["bugtracker_sync_state"]
        finally:
            await db.close()

    assert asyncio.run(read_migrated_state()) == "synced"


def test_create_feedback():
    """Test creating a feedback ticket."""
    payload = {
        "issue_type": "bug",
        "app_area": "Document Viewer",
        "goal": "Open a document",
        "reproduction_steps": "1. Click open 2. Select file",
        "expected_result": "File opens",
        "actual_result": "Error dialog",
        "impact": "block",
        "observation_time": "2026-01-15T10:00:00Z",
        "contact": "pilot1",
        "screenshot_info": None,
    }
    response = client.post("/api/p0/feedback", json=payload, headers=_admin_headers())
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["ticket_number"].startswith("FBK-")
    assert data["status"] == "new"
    assert data["priority"] == "P3"
    assert data["issue_type"] == "bug"
    assert data["feedback_id"]


def test_create_feedback_queues_bugtracker_without_forms_or_sheets_fields(monkeypatch):
    queued_feedback_ids = []

    async def capture_bugtracker_enqueue(feedback_id):
        queued_feedback_ids.append(feedback_id)

    monkeypatch.setattr(bugtracker_sync, "enqueue_feedback_create", capture_bugtracker_enqueue)
    payload = {
        "issue_type": "bug",
        "app_area": "Document Viewer",
        "goal": "BugTracker retention check",
        "impact": "workaround",
        "observation_time": "2026-01-15T10:00:00Z",
        "contact": "pilot1",
    }

    response = client.post("/api/p0/feedback", json=payload, headers=_admin_headers())

    assert response.status_code == 201, response.text
    body = response.json()
    assert queued_feedback_ids == [body["feedback_id"]]
    assert body["bugtracker_sync_state"] == "pending"
    assert {"zoho_form_record_id", "zoho_form_sync_state", "zoho_sheet_row_id"}.isdisjoint(body)


def test_bugtracker_webhook_uses_bugtracker_status_mapping(client, admin_headers, monkeypatch):
    async def skip_remote_create(_feedback_id):
        return None

    monkeypatch.setattr(bugtracker_sync, "enqueue_feedback_create", skip_remote_create)
    monkeypatch.setattr(bugtracker_sync, "_map_bugtracker_to_status", lambda _status: "closed")
    created = client.post("/api/p0/feedback", json={
        "issue_type": "bug",
        "app_area": "webhook-test",
        "goal": f"bugtracker-webhook-{uuid.uuid4().hex}",
        "impact": "workaround",
        "observation_time": "2026-01-15T10:00:00Z",
        "contact": "pilot1",
    }, headers=admin_headers)
    assert created.status_code == 201, created.text
    feedback_id = created.json()["feedback_id"]

    async def attach_bugtracker_id():
        db = await get_db()
        try:
            await db.execute(
                "UPDATE feedback SET bugtracker_id = ? WHERE feedback_id = ?",
                ("BT-TEST-1", feedback_id),
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(attach_bugtracker_id())
    response = client.post(
        "/api/p0/webhook/zoho-bugtracker",
        json={"bug_id": "BT-TEST-1", "status": "Custom Tracker Status"},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    assert body["status"] == "closed", body
    assert body["feedback_id"] == feedback_id

    async def read_status():
        db = await get_db()
        try:
            row = await (await db.execute(
                "SELECT status FROM feedback WHERE feedback_id = ?", (feedback_id,)
            )).fetchone()
            assert row is not None
            return row["status"]
        finally:
            await db.close()

    assert asyncio.run(read_status()) == "closed"


def test_create_feedback_duplicate():
    """Test that creating duplicate open feedback is rejected."""
    payload = {
        "issue_type": "bug",
        "app_area": "Test Area",
        "goal": "Test goal",
        "impact": "workaround",
        "observation_time": "2026-01-15T10:00:00Z",
        "contact": "pilot1",
    }
    # First creation
    r1 = client.post("/api/p0/feedback", json=payload, headers=_admin_headers())
    assert r1.status_code == 201, r1.text

    # Duplicate with same goal/app_area while open should be rejected
    r2 = client.post("/api/p0/feedback", json=payload, headers=_admin_headers())
    assert r2.status_code == 400, r2.text


def test_list_feedback():
    """Test listing feedback tickets."""
    response = client.get("/api/p0/feedback", headers=_admin_headers())
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)


def test_list_feedback_with_status_filter():
    """Test listing feedback with status filter."""
    response = client.get("/api/p0/feedback?status=new", headers=_admin_headers())
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)


def test_list_feedback_with_issue_type_filter():
    """Test listing feedback with issue_type filter."""
    response = client.get("/api/p0/feedback?issue_type=bug", headers=_admin_headers())
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
