import sqlite3
import uuid
from datetime import date, timedelta
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import database, p1_routes
from app.main import app


ADMIN = {"X-Role": "system_admin", "X-Actor": "admin"}


def _id(prefix):
    return f"{prefix}-{uuid.uuid4().hex}"


def _insert_mission(mission_id, *, status="planned", aircraft_id=None, roc_id=None):
    now = "2026-11-03T00:00:00"
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO missions
               (mission_id, title, status, created_at, updated_at, created_by, updated_by,
                aircraft_id, roc_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mission_id, "P1 transaction integrity test", status, now, now, ADMIN["X-Actor"], ADMIN["X-Actor"], aircraft_id, roc_id),
        )


def _audit_failure(monkeypatch):
    async def fail_audit(*args, db=None, **kwargs):
        assert db is not None, "mutation audit must use its transaction connection"
        raise RuntimeError("injected audit write failure")

    monkeypatch.setattr(p1_routes, "log_audit_event", fail_audit)


@contextmanager
def _client():
    yield TestClient(app, raise_server_exceptions=False)


def _scalar(sql, params=()):
    with sqlite3.connect(database.DB_PATH) as conn:
        return conn.execute(sql, params).fetchone()[0]


def _row(sql, params=()):
    with sqlite3.connect(database.DB_PATH) as conn:
        return conn.execute(sql, params).fetchone()


def test_mission_transition_audit_failure_rolls_back_state(monkeypatch):
    mission_id = _id("MSN")
    _insert_mission(mission_id)
    _audit_failure(monkeypatch)

    with _client() as client:
        response = client.patch(f"/api/p1/missions/{mission_id}/state?state=cancelled", headers=ADMIN)

    assert response.status_code == 500
    assert _scalar("SELECT status FROM missions WHERE mission_id = ?", (mission_id,)) == "planned"


def test_flight_plan_approval_audit_failure_rolls_back_approval(monkeypatch):
    mission_id, plan_id = _id("MSN"), _id("FP")
    _insert_mission(mission_id)
    now = "2026-11-03T00:00:00"
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO flight_plans
               (plan_id, mission_id, status, created_at, updated_at, created_by, updated_by)
               VALUES (?, ?, 'draft', ?, ?, ?, ?)""",
            (plan_id, mission_id, now, now, ADMIN["X-Actor"], ADMIN["X-Actor"]),
        )
    _audit_failure(monkeypatch)

    with _client() as client:
        response = client.patch(f"/api/p1/flight-plans/{plan_id}/approve", headers=ADMIN)

    assert response.status_code == 500
    assert _scalar("SELECT status FROM flight_plans WHERE plan_id = ?", (plan_id,)) == "draft"


def test_flight_release_audit_failure_rolls_back_release_and_mission(monkeypatch):
    mission_id, plan_id, aircraft_id, roc_id = (_id("MSN"), _id("FP"), _id("AC"), _id("ROC"))
    now = "2026-11-03T00:00:00"
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO roc_register
               (roc_id, roc_number, issue_date, expiry_date, status, max_altitude_agl,
                created_at, updated_at, created_by, updated_by)
               VALUES (?, 'TEST-ROC', ?, ?, 'active', 400, ?, ?, ?, ?)""",
            (roc_id, (date.today() - timedelta(days=1)).isoformat(), (date.today() + timedelta(days=30)).isoformat(), now, now, ADMIN["X-Actor"], ADMIN["X-Actor"]),
        )
        conn.execute(
            """INSERT INTO aircraft
               (aircraft_id, registration, model, roc_id, status, opspec_authorized,
                created_at, updated_at, created_by, updated_by)
               VALUES (?, ?, 'Test UAS', ?, 'active', 1, ?, ?, ?, ?)""",
            (aircraft_id, _id("REG"), roc_id, now, now, ADMIN["X-Actor"], ADMIN["X-Actor"]),
        )
        conn.execute(
            """INSERT INTO missions
               (mission_id, title, status, aircraft_id, roc_id, created_at, updated_at, created_by, updated_by)
               VALUES (?, 'Release rollback test', 'planned', ?, ?, ?, ?, ?, ?)""",
            (mission_id, aircraft_id, roc_id, now, now, ADMIN["X-Actor"], ADMIN["X-Actor"]),
        )
        conn.execute(
            """INSERT INTO flight_plans
               (plan_id, mission_id, status, max_altitude_agl, created_at, updated_at, created_by, updated_by)
               VALUES (?, ?, 'approved', 300, ?, ?, ?, ?)""",
            (plan_id, mission_id, now, now, ADMIN["X-Actor"], ADMIN["X-Actor"]),
        )

    assert _scalar("SELECT opspec_authorized FROM aircraft WHERE aircraft_id = ?", (aircraft_id,)) == 1
    async def skip_crew_eligibility(*args, **kwargs):
        return None

    monkeypatch.setattr(p1_routes, "_check_mission_eligibility", skip_crew_eligibility)
    _audit_failure(monkeypatch)
    payload = {
        "mission_id": mission_id,
        "plan_id": plan_id,
        "pre_flight_checklist": "Checklist completed",
        "weather_confirmed": True,
        "crew_confirmed": True,
        "aircraft_confirmed": True,
        "weather_evidence": "Weather checked",
        "crew_evidence": "Crew confirmed",
        "aircraft_evidence": "Aircraft serviceable",
    }

    with _client() as client:
        response = client.post("/api/p1/flight-releases", json=payload, headers=ADMIN)

    assert response.status_code == 500, response.text
    assert _scalar("SELECT status FROM missions WHERE mission_id = ?", (mission_id,)) == "planned"
    assert _scalar("SELECT COUNT(*) FROM flight_releases WHERE mission_id = ?", (mission_id,)) == 0


def test_audit_finding_audit_failure_rolls_back_finding_and_counter(monkeypatch):
    audit_id = _id("QA")
    now = "2026-11-03T00:00:00"
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO quality_audits
               (audit_id, title, auditor_id, created_at, updated_at, created_by, updated_by)
               VALUES (?, 'P1 finding rollback test', ?, ?, ?, ?, ?)""",
            (audit_id, ADMIN["X-Actor"], now, now, ADMIN["X-Actor"], ADMIN["X-Actor"]),
        )
    _audit_failure(monkeypatch)

    with _client() as client:
        response = client.post(
            "/api/p1/audit-findings",
            json={"audit_id": audit_id, "description": "Injected audit failure", "finding_type": "observation"},
            headers=ADMIN,
        )

    assert response.status_code == 500
    assert _scalar("SELECT COUNT(*) FROM quality_audit_findings WHERE audit_id = ?", (audit_id,)) == 0
    assert _scalar("SELECT findings_count FROM quality_audits WHERE audit_id = ?", (audit_id,)) == 0


@pytest.mark.parametrize("workflow", ["flight_release", "post_flight_report"])
def test_rejected_mission_workflows_leave_no_partial_rows(workflow):
    mission_id = _id("MSN")
    _insert_mission(mission_id)

    with _client() as client:
        if workflow == "flight_release":
            response = client.post(
                "/api/p1/flight-releases",
                json={
                    "mission_id": mission_id,
                    "plan_id": _id("FP"),
                    "pre_flight_checklist": "Checklist completed",
                    "weather_confirmed": True,
                    "crew_confirmed": True,
                    "aircraft_confirmed": True,
                    "weather_evidence": "Weather checked",
                    "crew_evidence": "Crew confirmed",
                    "aircraft_evidence": "Aircraft serviceable",
                },
                headers=ADMIN,
            )
            assert response.status_code == 400
            assert _scalar("SELECT COUNT(*) FROM flight_releases WHERE mission_id = ?", (mission_id,)) == 0
            assert _scalar("SELECT status FROM missions WHERE mission_id = ?", (mission_id,)) == "planned"
        else:
            response = client.post("/api/p1/post-flight-reports", json={"mission_id": mission_id}, headers=ADMIN)
            assert response.status_code == 400
            assert _scalar("SELECT COUNT(*) FROM post_flight_reports WHERE mission_id = ?", (mission_id,)) == 0
            row = _row("SELECT status, post_flight_report_id FROM missions WHERE mission_id = ?", (mission_id,))
            assert row == ("planned", None)


@pytest.mark.parametrize("route", ["update", "transition"])
def test_mission_begin_failure_rolls_back_and_closes_connection(monkeypatch, route):
    class BeginFailureConnection:
        in_transaction = False

        def __init__(self):
            self.rollback_calls = 0
            self.close_calls = 0

        async def execute(self, sql, *args):
            if sql == "BEGIN IMMEDIATE":
                raise RuntimeError("injected begin failure")
            raise AssertionError(f"unexpected query: {sql}")

        async def rollback(self):
            self.rollback_calls += 1

        async def close(self):
            self.close_calls += 1

    db = BeginFailureConnection()

    async def fake_get_db():
        return db

    monkeypatch.setattr(p1_routes, "get_db", fake_get_db)
    mission_id = _id("MSN")
    with _client() as client:
        if route == "update":
            response = client.patch(f"/api/p1/missions/{mission_id}", json={"title": "New title"}, headers=ADMIN)
        else:
            response = client.patch(f"/api/p1/missions/{mission_id}/state?state=cancelled", headers=ADMIN)

    assert response.status_code == 500
    assert db.rollback_calls == 0
    assert db.close_calls == 1


@pytest.mark.parametrize("route", ["update", "transition"])
def test_mission_failure_after_begin_explicitly_rolls_back_and_closes(monkeypatch, route):
    class QueryFailureConnection:
        def __init__(self):
            self.in_transaction = False
            self.rollback_calls = 0
            self.close_calls = 0

        async def execute(self, sql, *args):
            if sql == "BEGIN IMMEDIATE":
                self.in_transaction = True
                return None
            raise RuntimeError("injected failure after BEGIN IMMEDIATE")

        async def rollback(self):
            self.rollback_calls += 1
            self.in_transaction = False

        async def close(self):
            self.close_calls += 1

    db = QueryFailureConnection()

    async def fake_get_db():
        return db

    monkeypatch.setattr(p1_routes, "get_db", fake_get_db)
    mission_id = _id("MSN")
    with _client() as client:
        if route == "update":
            response = client.patch(f"/api/p1/missions/{mission_id}", json={"title": "New title"}, headers=ADMIN)
        else:
            response = client.patch(f"/api/p1/missions/{mission_id}/state?state=cancelled", headers=ADMIN)

    assert response.status_code == 500
    assert db.rollback_calls == 1
    assert db.close_calls == 1
    assert db.in_transaction is False


@pytest.mark.parametrize("action", ["verify", "close"])
def test_corrective_action_audit_failure_rolls_back_state(monkeypatch, action):
    car_id = _id("CAR")
    now = "2026-11-03T00:00:00"
    status = "open" if action == "verify" else "verified"
    verification = None if action == "verify" else "Independent verification passed"
    verified_by = None if action == "verify" else "independent-auditor"
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            """INSERT INTO corrective_actions
               (car_id, title, description, root_cause, corrective_action, owner_id, status,
                verification, verified_by, created_at, updated_at, created_by, updated_by)
               VALUES (?, 'CAR rollback test', 'Description', 'Cause', 'Corrective step', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (car_id, "different-owner", status, verification, verified_by, now, now, ADMIN["X-Actor"], ADMIN["X-Actor"]),
        )
    _audit_failure(monkeypatch)

    with _client() as client:
        if action == "verify":
            response = client.post(
                f"/api/p1/corrective-actions/{car_id}/verify?verification=Evidence+checked",
                headers=ADMIN,
            )
        else:
            response = client.post(f"/api/p1/corrective-actions/{car_id}/close", headers=ADMIN)

    assert response.status_code == 500
    assert _scalar("SELECT status FROM corrective_actions WHERE car_id = ?", (car_id,)) == status
