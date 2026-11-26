"""Tests for BugTracker sync robustness: token caching, paging, route consolidation."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app import bugtracker_sync
from app.database import get_db
from app.main import app

client = TestClient(app)


def _admin_headers():
    return {"X-Role": "system_admin", "X-Actor": "admin"}


@pytest.fixture(autouse=True)
def _fresh_token_cache():
    bugtracker_sync._reset_token_cache()
    yield
    bugtracker_sync._reset_token_cache()


# --- token caching -----------------------------------------------------------

def _counting_client(calls, payload=None):
    class _Response:
        status_code = 200

        def json(self):
            return payload or {"access_token": "tok-1", "expires_in": 3600}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, **kwargs):
            calls.append(kwargs.get("data"))
            return _Response()

    return _Client


@pytest.fixture
def _refresh_config(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "ZOHO_ACCESS_TOKEN", "")
    monkeypatch.setattr(bugtracker_sync, "ZOHO_REFRESH_TOKEN", "refresh")
    monkeypatch.setattr(bugtracker_sync, "ZOHO_CLIENT_ID", "id")
    monkeypatch.setattr(bugtracker_sync, "ZOHO_CLIENT_SECRET", "secret")


def test_token_is_reused_across_calls(monkeypatch, _refresh_config):
    calls = []
    monkeypatch.setattr(bugtracker_sync.httpx, "AsyncClient", _counting_client(calls))

    first = asyncio.run(bugtracker_sync._get_access_token())
    second = asyncio.run(bugtracker_sync._get_access_token())

    assert first == second == "tok-1"
    assert len(calls) == 1, "a cached token must not trigger another refresh"


def test_token_refreshes_once_expired(monkeypatch, _refresh_config):
    calls = []
    monkeypatch.setattr(bugtracker_sync.httpx, "AsyncClient", _counting_client(calls))

    asyncio.run(bugtracker_sync._get_access_token())
    bugtracker_sync._TOKEN_CACHE["expires_at"] = 0.0
    asyncio.run(bugtracker_sync._get_access_token())

    assert len(calls) == 2


def test_static_access_token_short_circuits_refresh(monkeypatch, _refresh_config):
    calls = []
    monkeypatch.setattr(bugtracker_sync, "ZOHO_ACCESS_TOKEN", "static-token")
    monkeypatch.setattr(bugtracker_sync.httpx, "AsyncClient", _counting_client(calls))

    assert asyncio.run(bugtracker_sync._get_access_token()) == "static-token"
    assert calls == []


def test_ttl_keeps_a_safety_margin():
    assert bugtracker_sync._token_ttl_seconds(3600) == 3540
    assert bugtracker_sync._token_ttl_seconds(30) == bugtracker_sync._TOKEN_MIN_TTL_SECONDS
    assert bugtracker_sync._token_ttl_seconds("garbage") == bugtracker_sync._TOKEN_DEFAULT_TTL_SECONDS
    assert bugtracker_sync._token_ttl_seconds(None) == bugtracker_sync._TOKEN_DEFAULT_TTL_SECONDS


# --- keyset paging -----------------------------------------------------------

def test_drain_keyset_reads_every_page():
    pages = {
        "": [{"feedback_id": "a"}, {"feedback_id": "b"}],
        "b": [{"feedback_id": "c"}],
        "c": [],
    }
    seen = []

    async def fetch_page(after):
        seen.append(after)
        return pages[after]

    rows = asyncio.run(bugtracker_sync._drain_keyset(fetch_page))

    assert [r["feedback_id"] for r in rows] == ["a", "b", "c"]
    assert seen == ["", "b", "c"]


def test_drain_keyset_stops_on_empty_first_page():
    async def fetch_page(after):
        return []

    assert asyncio.run(bugtracker_sync._drain_keyset(fetch_page)) == []


def test_sync_pages_past_the_old_single_limit(monkeypatch):
    """A backlog larger than one batch must all be offered to the sync."""
    monkeypatch.setattr(bugtracker_sync, "SYNC_BATCH_SIZE", 2)
    created = []

    async def fake_create(feedback):
        created.append(feedback["feedback_id"])
        return "bug-" + feedback["feedback_id"]

    monkeypatch.setattr(bugtracker_sync, "_create_bug_in_bugtracker", fake_create)

    ids = ["FBK-1", "FBK-2", "FBK-3", "FBK-4", "FBK-5"]

    async def seed():
        db = await get_db()
        try:
            for index, feedback_id in enumerate(ids):
                await db.execute(
                    """INSERT INTO feedback
                       (feedback_id, ticket_number, actor_user_id, actor_role, source_route,
                        issue_type, app_area, goal, impact, contact, status, priority,
                        bugtracker_sync_state, created_at, updated_at, created_by, updated_by)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (feedback_id, f"T-{index}", "u", "system_admin", "test",
                     "bug", "paging", f"paging test {feedback_id}", "workaround", "c@example.test",
                     "new", "P3", "pending", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z",
                     "u", "u"),
                )
            await db.commit()
        finally:
            await db.close()

    async def cleanup():
        db = await get_db()
        try:
            await db.execute(
                "DELETE FROM feedback WHERE feedback_id IN (%s)" % ",".join("?" * len(ids)),
                ids,
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(seed())
    try:
        assert bugtracker_sync._is_configured() is False  # no creds in tests
        result = asyncio.run(_run_pending_without_config_guard(monkeypatch))
    finally:
        asyncio.run(cleanup())

    assert sorted(created) == sorted(ids)
    assert result == len(ids)


async def _run_pending_without_config_guard(monkeypatch_ignored=None):
    """Drive sync_all_pending with the configuration guard bypassed."""
    original = bugtracker_sync._is_configured
    bugtracker_sync._is_configured = lambda: True
    try:
        return await bugtracker_sync.sync_all_pending()
    finally:
        bugtracker_sync._is_configured = original


# --- sync health -------------------------------------------------------------

def test_sync_status_defaults_before_any_run(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "_is_configured", lambda: True)

    async def clear():
        db = await get_db()
        try:
            await db.execute("DELETE FROM integration_sync_status")
            await db.commit()
        finally:
            await db.close()

    asyncio.run(clear())
    status = asyncio.run(bugtracker_sync.get_sync_status())

    assert status["last_status"] == "never_run"
    assert status["consecutive_failures"] == 0
    assert status["healthy"] is False


def test_successful_run_is_recorded(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "_is_configured", lambda: True)

    async def fake_push():
        return 2

    async def fake_pull():
        return 1

    monkeypatch.setattr(bugtracker_sync, "sync_all_pending", fake_push)
    monkeypatch.setattr(bugtracker_sync, "sync_bugtracker_updates", fake_pull)

    result = asyncio.run(bugtracker_sync.run_full_sync())
    status = asyncio.run(bugtracker_sync.get_sync_status())

    assert result["status"] == "success"
    assert result["created"] == 2 and result["updated"] == 1
    assert status["last_status"] == "success"
    assert status["last_created"] == 2
    assert status["last_updated"] == 1
    assert status["last_success_at"]
    assert status["consecutive_failures"] == 0
    assert status["healthy"] is True


def test_failing_run_records_error_and_increments_failures(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "_is_configured", lambda: True)

    async def boom():
        raise RuntimeError("zoho exploded")

    monkeypatch.setattr(bugtracker_sync, "sync_all_pending", boom)

    first = asyncio.run(bugtracker_sync.run_full_sync())
    second = asyncio.run(bugtracker_sync.run_full_sync())
    status = asyncio.run(bugtracker_sync.get_sync_status())

    assert first["status"] == "failed"
    assert "zoho exploded" in first["error"]
    assert second["status"] == "failed"
    assert status["consecutive_failures"] == 2
    assert status["last_failure_at"]
    assert "zoho exploded" in status["last_error"]
    assert status["healthy"] is False


def test_success_clears_the_failure_counter(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "_is_configured", lambda: True)

    async def boom():
        raise RuntimeError("nope")

    async def ok():
        return 0

    monkeypatch.setattr(bugtracker_sync, "sync_all_pending", boom)
    asyncio.run(bugtracker_sync.run_full_sync())

    monkeypatch.setattr(bugtracker_sync, "sync_all_pending", ok)
    monkeypatch.setattr(bugtracker_sync, "sync_bugtracker_updates", ok)
    asyncio.run(bugtracker_sync.run_full_sync())

    status = asyncio.run(bugtracker_sync.get_sync_status())
    assert status["consecutive_failures"] == 0
    assert status["last_status"] == "success"
    assert status["last_error"] is None
    assert status["healthy"] is True


def test_unconfigured_run_is_skipped_not_failed(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "_is_configured", lambda: False)

    result = asyncio.run(bugtracker_sync.run_full_sync())
    status = asyncio.run(bugtracker_sync.get_sync_status())

    assert result["status"] == "skipped"
    assert status["last_status"] == "skipped"
    assert status["consecutive_failures"] == 0


def test_observability_exposes_bugtracker_sync(monkeypatch):
    monkeypatch.setattr(bugtracker_sync, "_is_configured", lambda: True)

    response = client.get("/api/p0/admin/observability", headers=_admin_headers())

    assert response.status_code == 200, response.text
    block = response.json()["health"]["bugtracker_sync"]
    assert block["integration"] == "bugtracker"
    assert "last_status" in block and "consecutive_failures" in block


# --- routes ------------------------------------------------------------------

def test_cron_sync_endpoint_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("ZOHO_CRON_SECRET", raising=False)

    response = client.post("/api/p0/zoho/cron/sync", headers=_admin_headers())

    assert response.status_code == 503, response.text


def test_cron_sync_endpoint_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("ZOHO_CRON_SECRET", "expected")

    response = client.post(
        "/api/p0/zoho/cron/sync",
        headers={**_admin_headers(), "Authorization": "Bearer wrong"},
    )

    assert response.status_code == 403, response.text


def test_webhook_route_delegates_to_shared_handler(monkeypatch):
    """Both webhook routes must produce the shared handler's response shape."""
    seen = {}

    async def fake_handler(payload):
        seen.update(payload)
        return {"success": True, "feedback_id": "FBK-9", "status": "closed"}

    import app.p0_routes as p0_routes

    monkeypatch.setattr(p0_routes, "handle_bugtracker_webhook", fake_handler)

    response = client.post(
        "/api/p0/webhook/zoho-bugtracker",
        json={"bug_id": "BT-1", "status": "Closed"},
        headers=_admin_headers(),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "closed"
    assert seen["bug_id"] == "BT-1"


def test_webhook_route_still_requires_bug_id_and_status():
    response = client.post(
        "/api/p0/webhook/zoho-bugtracker",
        json={"bug_id": "BT-1"},
        headers=_admin_headers(),
    )

    assert response.status_code == 422
