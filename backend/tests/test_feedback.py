"""Tests for pilot feedback / ticketing API."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _auth_headers():
    # Use a session cookie or bypass auth for testing
    return {"Cookie": "session=test-session"}


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
    response = client.post("/feedback", json=payload)
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
    r1 = client.post("/feedback", json=payload)
    assert r1.status_code == 201, r1.text

    # Duplicate with same goal/app_area while open should be rejected
    r2 = client.post("/feedback", json=payload)
    assert r2.status_code == 400, r2.text


def test_list_feedback():
    """Test listing feedback tickets."""
    response = client.get("/feedback")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)


def test_list_feedback_with_status_filter():
    """Test listing feedback with status filter."""
    response = client.get("/feedback?status=new")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)


def test_list_feedback_with_issue_type_filter():
    """Test listing feedback with issue_type filter."""
    response = client.get("/feedback?issue_type=bug")
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
