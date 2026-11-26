"""Tests for the Zoho BugTracker client.

Zoho's BugTracker REST API mounts bugs under
/restapi/portal/{portal}/projects/{project}/bugs/. The client previously used
/api/v1/projects/{project}/bugs, which returns Zoho's HTML "Page Not Found"
(observed as HTTP 404 on staging), so these tests pin the documented path.
"""
import pytest

from app import bugtracker_sync


@pytest.fixture(autouse=True)
def _portal_config(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "ZOHO_BUGTRACKER_PORTAL", "kfldotke")
    monkeypatch.setattr(bugtracker_sync, "ZOHO_BUGTRACKER_PORTAL_ID", "")
    monkeypatch.setattr(bugtracker_sync, "ZOHO_BUGTRACKER_PROJECT_ID", "2730932000000114802")


def test_bug_collection_url_uses_restapi_portal_path():
    assert bugtracker_sync._bug_collection_url() == (
        "https://bugtracker.zoho.com/restapi/portal/kfldotke"
        "/projects/2730932000000114802/bugs/"
    )


def test_bug_item_url_uses_restapi_portal_path():
    assert bugtracker_sync._bug_item_url("2730932000000116017") == (
        "https://bugtracker.zoho.com/restapi/portal/kfldotke"
        "/projects/2730932000000114802/bugs/2730932000000116017/"
    )


def test_numeric_portal_id_overrides_link_name(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "ZOHO_BUGTRACKER_PORTAL_ID", "2063927")

    assert "/restapi/portal/2063927/" in bugtracker_sync._bug_collection_url()


def test_urls_never_use_the_undocumented_api_v1_prefix():
    for url in (
        bugtracker_sync._bug_collection_url(),
        bugtracker_sync._bug_item_url("1"),
    ):
        assert "/api/v1/" not in url


def test_portal_name_is_escaped(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "ZOHO_BUGTRACKER_PORTAL", "kfl dot ke")

    assert "/restapi/portal/kfl%20dot%20ke/" in bugtracker_sync._bug_collection_url()


def test_create_payload_sends_only_documented_fields():
    payload = bugtracker_sync._map_feedback_to_bugtracker(
        {
            "feedback_id": "FBK-1",
            "ticket_number": "FBK-20260101-0001",
            "issue_type": "bug",
            "app_area": "Document Viewer",
            "goal": "Open a document",
            "reproduction_steps": "1. Click open",
            "expected_result": "File opens",
            "actual_result": "Error dialog",
            "impact": "block",
            "priority": "P1",
            "status": "new",
            "contact": "pilot1",
            "created_at": "2026-01-15T10:00:00Z",
        }
    )

    assert set(payload) <= {"title", "description", "priority"}
    assert "custom_fields" not in payload
    assert "project_id" not in payload
    assert "status" not in payload
    assert payload["priority"] == "High"
    assert "FBK-20260101-0001" in payload["title"]
    assert "Error dialog" in payload["description"]


def test_extract_bug_status_accepts_string():
    assert bugtracker_sync._extract_bug_status({"status": "Fixed"}) == "Fixed"


def test_extract_bug_status_accepts_zoho_status_object():
    payload = {"bugs": [{"id": "1", "status": {"name": "In Progress", "type": "In Progress"}}]}

    assert bugtracker_sync._extract_bug_status(payload) == "In Progress"


def test_extract_bug_status_accepts_wrapped_bug_and_legacy_key():
    assert bugtracker_sync._extract_bug_status({"bug": {"bug_status": "Closed"}}) == "Closed"


def test_extract_bug_status_returns_none_when_absent():
    assert bugtracker_sync._extract_bug_status({"bugs": []}) is None
    assert bugtracker_sync._extract_bug_status({"unexpected": True}) is None


@pytest.mark.parametrize(
    ("remote", "local"),
    [
        ("Open", "new"),
        ("In Progress", "in_progress"),
        ("Fixed", "resolved"),
        ("Closed", "closed"),
        ("Reopened", "new"),
    ],
)
def test_status_mapping_round_trips(remote, local):
    assert bugtracker_sync._map_bugtracker_to_status(remote) == local
