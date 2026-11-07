import asyncio
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import database, p1_routes
from app.audit import log_audit_event as write_audit_event
from app.p1_models import AuditFindingCreate, FlightReleaseCreate, MissionUpdate, PostFlightReportCreate


class TrackedConnection:
    def __init__(self, connection):
        self.connection = connection
        self.close_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0
        self.in_transaction_when_closed = None

    @property
    def in_transaction(self):
        return self.connection.in_transaction

    async def execute(self, *args, **kwargs):
        return await self.connection.execute(*args, **kwargs)

    async def commit(self):
        self.commit_calls += 1
        return await self.connection.commit()

    async def rollback(self):
        self.rollback_calls += 1
        return await self.connection.rollback()

    async def close(self):
        self.close_calls += 1
        self.in_transaction_when_closed = self.connection.in_transaction
        return await self.connection.close()


@pytest.fixture

def isolated_p1_db(tmp_path, monkeypatch):
    db_path = tmp_path / "p1-transaction-audit.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    asyncio.run(database.init_db())
    connections = []

    async def tracked_get_db():
        connection = TrackedConnection(await database.get_db())
        connections.append(connection)
        return connection

    monkeypatch.setattr(p1_routes, "get_db", tracked_get_db)
    monkeypatch.setattr(p1_routes, "_check", lambda request, permission: None)
    monkeypatch.setattr(p1_routes, "_check_mission_eligibility", _eligibility_ok)
    return db_path, connections


async def _eligibility_ok(*args, **kwargs):
    return None


def _request():
    request = Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    })
    request.state.actor = "p1-tx-test"
    request.state.role = "system_admin"
    return request


def _run(coro):
    return asyncio.run(coro)


async def _seed_releasable_mission():
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO roc_register
               (roc_id, roc_number, issue_date, expiry_date, status, bvlos_authorized,
                night_authorized, evlos_authorized, authorized_registrations, created_at, updated_at, created_by, updated_by)
               VALUES ('ROC-TX', 'ROC-TX', '2020-01-01', '2035-12-31', 'active', 1,
                       1, 1, '5Y-TX', 'now', 'now', 'seed', 'seed')"""
        )
        await db.execute(
            """INSERT INTO aircraft
               (aircraft_id, registration, model, roc_id, status, opspec_authorized,
                created_at, updated_at, created_by, updated_by)
               VALUES ('AC-TX', '5Y-TX', 'Test aircraft', 'ROC-TX', 'active', 1,
                       'now', 'now', 'seed', 'seed')"""
        )
        await db.execute(
            """INSERT INTO missions
               (mission_id, title, mission_type, status, priority, aircraft_id, roc_id, max_altitude_agl,
                created_at, updated_at, created_by, updated_by)
               VALUES ('MISSION-TX', 'Transaction test', 'survey', 'planned', 'normal',
                       'AC-TX', 'ROC-TX', 300, 'now', 'now', 'seed', 'seed')"""
        )
        await db.execute(
            """INSERT INTO risk_assessments
               (assessment_id, mission_id, title, likelihood, severity, risk_level, risk_model, exposure,
                risk_score, scrutiny_required, flight_cancelled, assessor_id, assessed_at,
                reviewed_by, reviewed_at, status, created_at, updated_at)
               VALUES ('RA-TX', 'MISSION-TX', 'Transaction risk', 'rare', 'negligible', 'low', 'om_flight_26', 'rare',
                       2, 0, 0, 'seed-assessor', 'now', 'seed-reviewer', 'now', 'approved', 'now', 'now')"""
        )
        await db.execute("UPDATE missions SET risk_assessment_id = 'RA-TX' WHERE mission_id = 'MISSION-TX'")
        await db.execute(
            """INSERT INTO flight_plans
               (plan_id, mission_id, max_altitude_agl, status, approved_by, approved_at,
                created_at, updated_at, created_by, updated_by)
               VALUES ('PLAN-TX', 'MISSION-TX', 300, 'approved', 'seed-reviewer', 'now', 'now', 'now', 'seed', 'seed')"""
        )
        await db.execute("UPDATE missions SET flight_plan_id = 'PLAN-TX' WHERE mission_id = 'MISSION-TX'")
        await db.commit()
    finally:
        await db.close()


async def _seed_released_mission():
    await _seed_releasable_mission()
    db = await database.get_db()
    try:
        await db.execute(
            "UPDATE missions SET status = 'released', release_id = 'RELEASE-TX' WHERE mission_id = 'MISSION-TX'"
        )
        await db.execute(
            """INSERT INTO flight_releases
               (release_id, mission_id, plan_id, released_by, released_at, status, created_at)
               VALUES ('RELEASE-TX', 'MISSION-TX', 'PLAN-TX', 'seed', 'now', 'released', 'now')"""
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_quality_audit():
    db = await database.get_db()
    try:
        await db.execute(
            """INSERT INTO quality_audits
               (audit_id, title, auditor_id, status, created_at, updated_at, created_by, updated_by)
               VALUES ('AUDIT-TX', 'Transaction test', 'auditor', 'planned', 'now', 'now', 'seed', 'seed')"""
        )
        await db.commit()
    finally:
        await db.close()


async def _install_semantic_audit_failure(entity_type):
    db = await database.get_db()
    try:
        await db.execute(
            f"""CREATE TRIGGER fail_p1_semantic_audit BEFORE INSERT ON audit_events
                WHEN NEW.entity_type = '{entity_type}'
                BEGIN SELECT RAISE(ABORT, 'forced P1 audit write failure'); END"""
        )
        await db.commit()
    finally:
        await db.close()


async def _audit_event_count():
    db = await database.get_db()
    try:
        row = await (await db.execute("SELECT COUNT(*) AS n FROM audit_events")).fetchone()
        return row["n"]
    finally:
        await db.close()


async def _mission_snapshot():
    db = await database.get_db()
    try:
        row = await (await db.execute(
            "SELECT status, release_id, post_flight_report_id FROM missions WHERE mission_id = 'MISSION-TX'"
        )).fetchone()
        return dict(row)
    finally:
        await db.close()


async def _install_same_connection_audit_spy(monkeypatch, connections):
    async def verified_writer(*args, **kwargs):
        assert kwargs.get("db") is connections[-1]
        return await write_audit_event(*args, **kwargs)

    monkeypatch.setattr(p1_routes, "log_audit_event", verified_writer)


def test_flight_release_audit_failure_rolls_back_release_and_mission(isolated_p1_db, monkeypatch):
    _, connections = isolated_p1_db
    _run(_seed_releasable_mission())
    _run(_install_semantic_audit_failure("flight_release"))
    before_events = _run(_audit_event_count())
    _run(_install_same_connection_audit_spy(monkeypatch, connections))
    payload = FlightReleaseCreate(
        mission_id="MISSION-TX", plan_id="PLAN-TX", pre_flight_checklist="Checklist complete",
        weather_confirmed=True, crew_confirmed=True, aircraft_confirmed=True,
        weather_evidence="Forecast reviewed", crew_evidence="Crew checked", aircraft_evidence="Aircraft checked",
    )

    with pytest.raises(Exception, match="forced P1 audit write failure"):
        _run(p1_routes.create_flight_release(payload, _request()))

    assert _run(_mission_snapshot()) == {
        "status": "planned", "release_id": None, "post_flight_report_id": None,
    }
    assert _run(_audit_event_count()) == before_events
    db = _run(database.get_db())
    try:
        count = _run(db.execute("SELECT COUNT(*) AS n FROM flight_releases"))
        assert _run(count.fetchone())["n"] == 0
    finally:
        _run(db.close())
    assert connections[-1].commit_calls == 0
    assert connections[-1].rollback_calls == 1
    assert connections[-1].close_calls == 1


def test_post_flight_audit_failure_rolls_back_report_and_mission(isolated_p1_db, monkeypatch):
    _, connections = isolated_p1_db
    _run(_seed_released_mission())
    async def mark_mission_in_progress():
        db = await database.get_db()
        try:
            await db.execute("UPDATE missions SET status = 'in_progress' WHERE mission_id = 'MISSION-TX'")
            await db.commit()
        finally:
            await db.close()
    _run(mark_mission_in_progress())
    _run(_install_semantic_audit_failure("post_flight_report"))
    before_events = _run(_audit_event_count())
    _run(_install_same_connection_audit_spy(monkeypatch, connections))
    payload = PostFlightReportCreate(mission_id="MISSION-TX", actual_duration_min=12)

    with pytest.raises(Exception, match="forced P1 audit write failure"):
        _run(p1_routes.create_post_flight_report(payload, _request()))

    assert _run(_mission_snapshot()) == {
        "status": "in_progress", "release_id": "RELEASE-TX", "post_flight_report_id": None,
    }
    assert _run(_audit_event_count()) == before_events
    db = _run(database.get_db())
    try:
        row = _run(db.execute("SELECT COUNT(*) AS n FROM post_flight_reports"))
        assert _run(row.fetchone())["n"] == 0
    finally:
        _run(db.close())
    assert connections[-1].commit_calls == 0
    assert connections[-1].rollback_calls == 1
    assert connections[-1].close_calls == 1


def test_audit_finding_audit_failure_rolls_back_finding_and_counter(isolated_p1_db, monkeypatch):
    _, connections = isolated_p1_db
    _run(_seed_quality_audit())
    _run(_install_semantic_audit_failure("quality_audit_finding"))
    before_events = _run(_audit_event_count())
    _run(_install_same_connection_audit_spy(monkeypatch, connections))
    payload = AuditFindingCreate(audit_id="AUDIT-TX", description="Finding for rollback")

    with pytest.raises(Exception, match="forced P1 audit write failure"):
        _run(p1_routes.create_audit_finding(payload, _request()))

    db = _run(database.get_db())
    try:
        finding = _run(db.execute("SELECT COUNT(*) AS n FROM quality_audit_findings"))
        audit = _run(db.execute("SELECT findings_count FROM quality_audits WHERE audit_id = 'AUDIT-TX'"))
        assert _run(finding.fetchone())["n"] == 0
        assert _run(audit.fetchone())["findings_count"] == 0
    finally:
        _run(db.close())
    assert _run(_audit_event_count()) == before_events
    assert connections[-1].commit_calls == 0
    assert connections[-1].rollback_calls == 1
    assert connections[-1].close_calls == 1


@pytest.mark.parametrize("route_name", ["update_mission", "transition_mission_state"])
def test_mission_transaction_closes_connection_when_begin_immediate_fails(
    isolated_p1_db, monkeypatch, route_name
):
    class BeginFailureConnection:
        in_transaction = False

        def __init__(self):
            self.close_calls = 0
            self.rollback_calls = 0

        async def execute(self, sql, *args):
            assert sql == "BEGIN IMMEDIATE"
            raise RuntimeError("forced BEGIN IMMEDIATE failure")

        async def rollback(self):
            self.rollback_calls += 1

        async def close(self):
            self.close_calls += 1

    db = BeginFailureConnection()
    monkeypatch.setattr(p1_routes, "get_db", lambda: _return_db(db))
    if route_name == "update_mission":
        call = p1_routes.update_mission("MISSION-TX", MissionUpdate(title="Changed"), _request())
    else:
        call = p1_routes.transition_mission_state("MISSION-TX", "cancelled", _request())

    with pytest.raises(RuntimeError, match="forced BEGIN IMMEDIATE failure"):
        _run(call)

    assert db.close_calls == 1
    assert db.rollback_calls == 0


async def _return_db(db):
    return db


def test_post_flight_http_exception_rolls_back_and_closes_connection(isolated_p1_db):
    _, connections = isolated_p1_db
    with pytest.raises(HTTPException) as error:
        _run(p1_routes.create_post_flight_report(
            PostFlightReportCreate(mission_id="MISSING-MISSION"), _request()
        ))

    assert error.value.status_code == 404
    assert connections[-1].in_transaction_when_closed is False
    assert connections[-1].rollback_calls == 1
    assert connections[-1].close_calls == 1


def test_mission_lifecycle_gates_remain_enforced(isolated_p1_db):
    _run(_seed_released_mission())
    with pytest.raises(HTTPException) as error:
        _run(p1_routes.update_mission(
            "MISSION-TX", MissionUpdate(title="Locked change"), _request()
        ))
    assert error.value.status_code == 409

    with pytest.raises(HTTPException) as error:
        _run(p1_routes.transition_mission_state("MISSION-TX", "completed", _request()))
    assert error.value.status_code == 400
    assert _run(_mission_snapshot())["status"] == "released"
