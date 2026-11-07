import os
import sqlite3
import uuid


def _count_aircraft(conn):
    return conn.execute("SELECT COUNT(*) FROM aircraft").fetchone()[0]


def _count_aircraft_status(conn, status):
    return conn.execute("SELECT COUNT(*) FROM aircraft WHERE status = ?", (status,)).fetchone()[0]


def _count_opspec_authorized(conn):
    return conn.execute("SELECT COUNT(*) FROM aircraft WHERE opspec_authorized = 1").fetchone()[0]


def test_organization_overview_returns_org_wide_summary_for_accountable_manager(client):
    headers = {"X-Role": "accountable_manager", "X-Actor": "u-accountable"}

    response = client.get("/api/p1/organization/overview", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"trends", "deadlines", "operations", "fleet"}
    assert set(payload["operations"]) >= {"total", "released", "in_progress", "completed"}
    assert set(payload["fleet"]) >= {"total", "status_counts", "opspec_authorized", "not_opspec_authorized"}
    assert "occurrences_last_30_days" in payload["trends"]
    assert "overdue_count" in payload["deadlines"]


def test_organization_overview_is_restricted_to_accountable_manager_and_admin(client, admin_headers, librarian_headers):
    manager = {"X-Role": "accountable_manager", "X-Actor": "u-accountable"}
    assert client.get("/api/p1/organization/overview", headers=manager).status_code == 200
    assert client.get("/api/p1/organization/overview", headers=admin_headers).status_code == 200
    assert client.get("/api/p1/organization/overview", headers=librarian_headers).status_code == 403
    quality_headers = {"X-Role": "head_quality", "X-Actor": "u-quality"}
    assert client.get("/api/p1/organization/overview", headers=quality_headers).status_code == 403


def test_aircraft_summary_counts_the_full_fleet_not_a_paginated_slice(client):
    headers = {"X-Role": "accountable_manager", "X-Actor": "u-accountable"}
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    aircraft_ids = [f"AC-QA-{uuid.uuid4().hex[:10]}" for _ in range(2)]
    registrations = [f"QA{uuid.uuid4().hex[:6].upper()}" for _ in range(2)]
    now = "2026-11-07T00:00:00"
    try:
        before_total = _count_aircraft(conn)
        before_active = _count_aircraft_status(conn, "active")
        before_grounded = _count_aircraft_status(conn, "grounded")
        before_authorized = _count_opspec_authorized(conn)
        conn.executemany(
            """INSERT INTO aircraft
               (aircraft_id, registration, model, status, opspec_authorized,
                created_at, updated_at, created_by, updated_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (aircraft_ids[0], registrations[0], "QA model", "active", 1, now, now, "u-admin", "u-admin"),
                (aircraft_ids[1], registrations[1], "QA model", "grounded", 0, now, now, "u-admin", "u-admin"),
            ],
        )
        conn.commit()
        response = client.get("/api/p1/aircraft/summary", headers=headers)
        assert response.status_code == 200, response.text
        summary = response.json()
        assert summary["total"] == before_total + 2
        assert summary["status_counts"]["active"] == before_active + 1
        assert summary["status_counts"]["grounded"] == before_grounded + 1
        assert summary["opspec_authorized"] == before_authorized + 1
        assert summary["not_opspec_authorized"] == before_total - before_authorized + 1
    finally:
        conn.execute("DELETE FROM aircraft WHERE aircraft_id IN (?, ?)", aircraft_ids)
        conn.commit()
        conn.close()
