"""Tests for pilot feedback / ticketing API."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _admin_headers():
    return {"X-Role": "system_admin", "X-Actor": "admin"}


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
