import asyncio
import uuid
import pytest
from app.database import get_db
from app import database, p1_routes


def _new_release_pilot():
    person_id = f"release-pilot-{uuid.uuid4().hex[:8]}"
    async def insert_user():
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO users (user_id, username, email, full_name, role, is_active, created_at, updated_at) VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))",
                (person_id, person_id, f"{person_id}@example.test", "Release Test Pilot", "chief_pilot", 1),
            )
            await db.commit()
        finally:
            await db.close()
    asyncio.run(insert_user())
    return person_id


def _release_mission(client, mission, plan, headers):
    return client.post("/api/p1/flight-releases", json={
        "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
        "pre_flight_checklist": "Checklist itemized and completed", "weather_confirmed": True,
        "crew_confirmed": True, "aircraft_confirmed": True,
        "weather_evidence": "Forecast reviewed", "crew_evidence": "Crew credentials verified",
        "aircraft_evidence": "Aircraft and insurance verified",
    }, headers=headers)


def _risk_reviewer_headers():
    return {"X-Role": "head_safety", "X-Actor": "u-safety"}


def _flight_plan_reviewer_headers():
    return {"X-Role": "head_operations", "X-Actor": "u-ops"}


def _set_aircraft_authorization_fields(aircraft_id, registration, roc_id, opspec_authorized):
    async def update():
        db = await get_db()
        try:
            await db.execute(
                "UPDATE aircraft SET registration = ?, roc_id = ?, opspec_authorized = ? WHERE aircraft_id = ?",
                (registration, roc_id, opspec_authorized, aircraft_id),
            )
            await db.commit()
        finally:
            await db.close()
    asyncio.run(update())


@pytest.fixture
def preserve_roc_opspec_state():
    async def snapshot():
        db = await get_db()
        try:
            async with db.execute("SELECT * FROM roc_register") as cur:
                rocs = [dict(row) for row in await cur.fetchall()]
            async with db.execute("SELECT * FROM aircraft") as cur:
                aircraft = [dict(row) for row in await cur.fetchall()]
            async with db.execute("SELECT event_id FROM audit_events") as cur:
                audit_event_ids = {row["event_id"] for row in await cur.fetchall()}
            if not any(row["roc_id"] == "ROC-001" for row in rocs):
                raise AssertionError("Seeded ROC-001 is required for this test")
            return rocs, aircraft, audit_event_ids
        finally:
            await db.close()

    roc_snapshot, aircraft_snapshot, audit_event_ids = asyncio.run(snapshot())
    yield

    async def restore():
        db = await get_db()
        try:
            await db.execute("BEGIN IMMEDIATE")
            original_aircraft_ids = {row["aircraft_id"] for row in aircraft_snapshot}
            async with db.execute("SELECT aircraft_id FROM aircraft") as cur:
                current_aircraft_ids = {row["aircraft_id"] for row in await cur.fetchall()}
            for added_id in current_aircraft_ids - original_aircraft_ids:
                await db.execute("DELETE FROM aircraft WHERE aircraft_id = ?", (added_id,))

            original_roc_ids = {row["roc_id"] for row in roc_snapshot}
            async with db.execute("SELECT roc_id FROM roc_register") as cur:
                current_roc_ids = {row["roc_id"] for row in await cur.fetchall()}
            for added_id in current_roc_ids - original_roc_ids:
                await db.execute("DELETE FROM roc_register WHERE roc_id = ?", (added_id,))

            await db.executemany(
                """UPDATE roc_register SET roc_number = ?, serial_number = ?, kcaa_reference = ?, issue_date = ?,
                   expiry_date = ?, status = ?, categories = ?, bvlos_authorized = ?, night_authorized = ?,
                   max_altitude_agl = ?, evlos_authorized = ?, dg_category = ?, authorized_registrations = ?, notes = ?,
                   created_at = ?, updated_at = ?, created_by = ?, updated_by = ? WHERE roc_id = ?""",
                [
                    (
                        row["roc_number"], row["serial_number"], row["kcaa_reference"], row["issue_date"],
                        row["expiry_date"], row["status"], row["categories"], row["bvlos_authorized"],
                        row["night_authorized"], row["max_altitude_agl"], row["evlos_authorized"],
                        row["dg_category"], row["authorized_registrations"], row["notes"], row["created_at"],
                        row["updated_at"], row["created_by"], row["updated_by"], row["roc_id"],
                    )
                    for row in roc_snapshot
                ],
            )
            await db.executemany(
                """UPDATE aircraft SET registration = ?, model = ?, manufacturer = ?, serial_number = ?, roc_id = ?,
                   status = ?, category = ?, weight_class = ?, max_takeoff_weight_kg = ?, acquired_date = ?,
                   opspec_authorized = ?, notes = ?, created_at = ?, updated_at = ?, created_by = ?, updated_by = ?
                   WHERE aircraft_id = ?""",
                [
                    (
                        row["registration"], row["model"], row["manufacturer"], row["serial_number"], row["roc_id"],
                        row["status"], row["category"], row["weight_class"], row["max_takeoff_weight_kg"],
                        row["acquired_date"], row["opspec_authorized"], row["notes"], row["created_at"],
                        row["updated_at"], row["created_by"], row["updated_by"], row["aircraft_id"],
                    )
                    for row in aircraft_snapshot
                ],
            )
            async with db.execute("SELECT event_id FROM audit_events") as cur:
                current_event_ids = {row["event_id"] for row in await cur.fetchall()}
            for added_id in current_event_ids - audit_event_ids:
                await db.execute("DELETE FROM audit_events WHERE event_id = ?", (added_id,))
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    asyncio.run(restore())


def _prepare_releasable_mission(client, headers, title="Eligible flight", with_risk_assessment=True):
    person_id = _new_release_pilot()
    insurance = client.post("/api/p2/aircraft/AC-001/insurance", json={
        "insurance_type": "liability", "policy_number": f"POL-{title}", "insurer": "Test Insurer", "expiry_date": "2027-12-31"
    }, headers=headers)
    assert insurance.status_code == 200
    license_record = client.post("/api/p2/personnel/licenses", json={
        "person_id": person_id, "license_type": "RPAS pilot", "expiry_date": "2027-12-31",
        "status": "valid", "verified_by": "admin",
    }, headers=headers)
    assert license_record.status_code == 200
    mission = client.post("/api/p1/missions", json={
        "title": title, "mission_type": "survey", "roc_id": "ROC-001", "aircraft_id": "AC-001",
        "rpas_pilot_id": person_id, "max_altitude_agl": 300,
    }, headers=headers)
    assert mission.status_code == 201, mission.text
    if with_risk_assessment:
        assessment = client.post("/api/p1/risk-assessments", json={
            "title": f"{title} risk", "mission_id": mission.json()["mission_id"],
            "risk_model": "om_flight_26", "likelihood": "rare", "severity": "negligible",
            "exposure": "rare", "risk_level": "low",
        }, headers=headers)
        assert assessment.status_code == 201, assessment.text
        approved_assessment = client.post(
            f"/api/p1/risk-assessments/{assessment.json()['assessment_id']}/approve", headers=_risk_reviewer_headers(),
        )
        assert approved_assessment.status_code == 200, approved_assessment.text
        linked_mission = client.patch(
            f"/api/p1/missions/{mission.json()['mission_id']}",
            json={"risk_assessment_id": assessment.json()["assessment_id"]}, headers=headers,
        )
        assert linked_mission.status_code == 200, linked_mission.text
        mission = linked_mission
    plan = client.post("/api/p1/flight-plans", json={
        "mission_id": mission.json()["mission_id"], "route_description": "Approved test route", "max_altitude_agl": 300,
    }, headers=headers)
    assert plan.status_code == 201
    approved = client.patch(
        f"/api/p1/flight-plans/{plan.json()['plan_id']}/approve", headers=_flight_plan_reviewer_headers(),
    )
    assert approved.status_code == 200
    return mission.json(), plan.json(), insurance.json()["insurance_id"], license_record.json()["license_id"]


def test_mission_summary_counts_every_status_across_the_full_table(client, admin_headers, safety_headers):
    async def status_counts():
        db = await get_db()
        try:
            cursor = await db.execute("SELECT status, COUNT(*) AS count FROM missions GROUP BY status")
            return {row["status"]: row["count"] for row in await cursor.fetchall()}
        finally:
            await db.close()

    baseline = asyncio.run(status_counts())
    new_ids = []
    for index in range(55):
        response = client.post("/api/p1/missions", json={
            "title": f"Summary mission {index}", "mission_type": "survey",
        }, headers=admin_headers)
        assert response.status_code == 201, response.text
        new_ids.append(response.json()["mission_id"])

    status_by_index = {50: "released", 51: "in_progress", 52: "completed", 53: "cancelled", 54: "aborted"}

    async def assign_summary_statuses():
        db = await get_db()
        try:
            for index, status in status_by_index.items():
                await db.execute("UPDATE missions SET status = ? WHERE mission_id = ?", (status, new_ids[index]))
            await db.commit()
        finally:
            await db.close()
    asyncio.run(assign_summary_statuses())

    response = client.get("/api/p1/missions/summary", headers=safety_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "total": sum(baseline.values()) + 55,
        "planned": baseline.get("planned", 0) + 50,
        "released": baseline.get("released", 0) + 1,
        "in_progress": baseline.get("in_progress", 0) + 1,
        "completed": baseline.get("completed", 0) + 1,
        "cancelled": baseline.get("cancelled", 0) + 1,
        "aborted": baseline.get("aborted", 0) + 1,
    }


def test_mission_list_search_status_and_pagination_cover_entire_register(client, admin_headers):
    created = []
    for index in range(55):
        response = client.post("/api/p1/missions", json={
            "title": f"Register match {index:02d}", "mission_type": "survey",
            "location": "Northern field" if index == 54 else "South field",
        }, headers=admin_headers)
        assert response.status_code == 201, response.text
        created.append(response.json()["mission_id"])

    filtered = client.get("/api/p1/missions", params={"search": "Northern", "status": "planned", "limit": 10, "offset": 0}, headers=admin_headers)
    assert filtered.status_code == 200
    assert [item["mission_id"] for item in filtered.json()] == [created[54]]

    page_one = client.get("/api/p1/missions", params={"search": "Register match", "limit": 10, "offset": 0}, headers=admin_headers)
    page_two = client.get("/api/p1/missions", params={"search": "Register match", "limit": 10, "offset": 10}, headers=admin_headers)
    assert page_one.status_code == page_two.status_code == 200
    assert len(page_one.json()) == len(page_two.json()) == 10
    assert set(item["mission_id"] for item in page_one.json()).isdisjoint(item["mission_id"] for item in page_two.json())
    assert [item["mission_id"] for item in page_one.json()] == sorted(created)[:10]


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 1000001},
    {"search": "x" * 201}, {"status": "unknown"},
])
def test_mission_list_rejects_unbounded_or_invalid_filters(client, admin_headers, params):
    response = client.get("/api/p1/missions", params=params, headers=admin_headers)
    assert response.status_code == 422


def test_mission_creation_rejects_non_iso_planned_date(client, admin_headers):
    response = client.post("/api/p1/missions", json={
        "title": "Invalid date mission", "planned_date": "61120-02-20",
    }, headers=admin_headers)
    assert response.status_code == 422


def test_mission_update_rejects_non_iso_planned_date(client, admin_headers):
    created = client.post("/api/p1/missions", json={"title": "Date update mission"}, headers=admin_headers)
    assert created.status_code == 201, created.text
    response = client.patch(
        f"/api/p1/missions/{created.json()['mission_id']}",
        json={"planned_date": "61120-02-20"}, headers=admin_headers,
    )
    assert response.status_code == 422


@pytest.mark.parametrize("planned_date", ["20261120", "2026-W47-5"])
def test_mission_creation_rejects_noncanonical_iso_date(client, admin_headers, planned_date):
    response = client.post("/api/p1/missions", json={
        "title": "Noncanonical date mission", "planned_date": planned_date,
    }, headers=admin_headers)
    assert response.status_code == 422


@pytest.mark.parametrize("planned_date", ["20261120", "2026-W47-5"])
def test_mission_update_rejects_noncanonical_iso_date(client, admin_headers, planned_date):
    created = client.post("/api/p1/missions", json={"title": "Noncanonical date update"}, headers=admin_headers)
    assert created.status_code == 201, created.text
    response = client.patch(
        f"/api/p1/missions/{created.json()['mission_id']}",
        json={"planned_date": planned_date}, headers=admin_headers,
    )
    assert response.status_code == 422


def test_roc_create_rejects_noncanonical_validity_dates(client, admin_headers):
    response = client.post("/api/p1/roc", json={
        "roc_number": "TEST-INVALID-DATE", "issue_date": "2026-W47-5", "expiry_date": "2027-01-01",
    }, headers=admin_headers)
    assert response.status_code == 422


def test_roc_update_rejects_noncanonical_validity_dates(client, admin_headers):
    response = client.patch("/api/p1/roc/ROC-001", json={"expiry_date": "20261120"}, headers=admin_headers)
    assert response.status_code == 422
    current = client.get("/api/p1/roc/ROC-001", headers=admin_headers)
    assert current.status_code == 200
    assert current.json()["expiry_date"] == "2027-10-11"


def test_roc_create_persists_authorized_registrations(client, admin_headers, preserve_roc_opspec_state):
    created = client.post("/api/p1/roc", json={
        "roc_number": "TEST-SCOPE", "issue_date": "2026-01-01", "expiry_date": "2027-01-01",
        "authorized_registrations": "5Y-1000A, 5Y-1001A",
    }, headers=admin_headers)
    assert created.status_code == 201, created.text
    assert created.json()["authorized_registrations"] == "5Y-1000A, 5Y-1001A"
    reread = client.get(f"/api/p1/roc/{created.json()['roc_id']}", headers=admin_headers)
    assert reread.status_code == 200
    assert reread.json()["authorized_registrations"] == "5Y-1000A, 5Y-1001A"

    async def read_create_audit_details():
        db = await get_db()
        try:
            row = await (await db.execute(
                "SELECT details FROM audit_events WHERE entity_type='roc' AND entity_id=? AND action='created'",
                (created.json()["roc_id"],),
            )).fetchone()
            return row["details"] if row else None
        finally:
            await db.close()

    import json
    create_details_raw = asyncio.run(read_create_audit_details())
    assert create_details_raw is not None
    assert json.loads(create_details_raw)["authorized_registrations"] == "5Y-1000A, 5Y-1001A"


def test_roc_update_persists_authorized_registrations(client, admin_headers, preserve_roc_opspec_state):
    response = client.patch(
        "/api/p1/roc/ROC-001", json={"authorized_registrations": "5Y-TEST-REVIEW"}, headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["authorized_registrations"] == "5Y-TEST-REVIEW"
    reread = client.get("/api/p1/roc/ROC-001", headers=admin_headers)
    assert reread.json()["authorized_registrations"] == "5Y-TEST-REVIEW"

    async def latest_scope_audit_details():
        db = await get_db()
        try:
            row = await (await db.execute(
                """SELECT details FROM audit_events WHERE entity_type='roc' AND entity_id='ROC-001'
                   AND action='updated' ORDER BY rowid DESC LIMIT 1"""
            )).fetchone()
            return row["details"] if row else None
        finally:
            await db.close()

    import json
    update_details_raw = asyncio.run(latest_scope_audit_details())
    assert update_details_raw is not None
    details = json.loads(update_details_raw)
    assert details["changed"]["authorized_registrations"] == {
        "from": "5Y-0029A,5Y-0030A,5Y-0042A,5Y-0164A,5Y-0600A,5Y-0601A,5Y-0602A",
        "to": "5Y-TEST-REVIEW",
    }
    cleared = client.patch(
        "/api/p1/roc/ROC-001", json={"authorized_registrations": ""}, headers=admin_headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["authorized_registrations"] == ""
    clear_details_raw = asyncio.run(latest_scope_audit_details())
    assert clear_details_raw is not None
    assert json.loads(clear_details_raw)["changed"]["authorized_registrations"] == {
        "from": "5Y-TEST-REVIEW", "to": "",
    }
def test_roc_boolean_authorization_change_is_audited_with_before_and_after(client, admin_headers):
    original = client.get("/api/p1/roc/ROC-001", headers=admin_headers).json()["bvlos_authorized"]
    requested = not original
    updated = client.patch(
        "/api/p1/roc/ROC-001", json={"bvlos_authorized": requested}, headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text

    async def latest_roc_update_details():
        db = await get_db()
        try:
            row = await (await db.execute(
                """SELECT details FROM audit_events WHERE entity_type='roc' AND entity_id='ROC-001'
                   AND action='updated' ORDER BY rowid DESC LIMIT 1"""
            )).fetchone()
            return row["details"] if row else None
        finally:
            await db.close()

    import json
    details_raw = asyncio.run(latest_roc_update_details())
    assert details_raw is not None
    assert json.loads(details_raw)["changed"]["bvlos_authorized"] == {
        "from": original, "to": requested,
    }
    restored = client.patch(
        "/api/p1/roc/ROC-001", json={"bvlos_authorized": original}, headers=admin_headers,
    )
    assert restored.status_code == 200, restored.text


def test_roc_scope_removal_revokes_and_readdition_does_not_restore_aircraft_authorization(
    client, admin_headers, preserve_roc_opspec_state,
):
    registration = "5Y-0029A"
    original_scope = "5Y-0029A,5Y-0030A,5Y-0042A,5Y-0164A,5Y-0600A,5Y-0601A,5Y-0602A"
    aircraft = next(
        row for row in client.get("/api/p1/aircraft", headers=admin_headers).json()
        if row["registration"] == registration
    )
    assert aircraft["opspec_authorized"] is True

    reduced_scope = ",".join(value for value in original_scope.split(",") if value != registration)
    removed = client.patch(
        "/api/p1/roc/ROC-001", json={"authorized_registrations": reduced_scope}, headers=admin_headers,
    )
    assert removed.status_code == 200, removed.text
    after_removal = next(
        row for row in client.get("/api/p1/aircraft", headers=admin_headers).json()
        if row["aircraft_id"] == aircraft["aircraft_id"]
    )
    assert after_removal["opspec_authorized"] is False

    async def read_revocation_event():
        db = await get_db()
        try:
            row = await (await db.execute(
                """SELECT details FROM audit_events WHERE entity_type='aircraft' AND entity_id=?
                   AND action='opspec_authorization_revoked' ORDER BY rowid DESC LIMIT 1""",
                (aircraft["aircraft_id"],),
            )).fetchone()
            return row["details"] if row else None
        finally:
            await db.close()

    import json
    revocation_details = asyncio.run(read_revocation_event())
    assert revocation_details is not None
    assert json.loads(revocation_details)["registration"] == registration

    restored = client.patch(
        "/api/p1/roc/ROC-001", json={"authorized_registrations": original_scope}, headers=admin_headers,
    )
    assert restored.status_code == 200, restored.text
    after_readdition = next(
        row for row in client.get("/api/p1/aircraft", headers=admin_headers).json()
        if row["aircraft_id"] == aircraft["aircraft_id"]
    )
    assert after_readdition["opspec_authorized"] is False


def test_roc_scope_removal_revokes_padded_aircraft_registration(client, admin_headers, preserve_roc_opspec_state):
    aircraft_id = f"AC-PADDED-{uuid.uuid4().hex[:8]}"
    original_scope = "5Y-0029A,5Y-0030A,5Y-0042A,5Y-0164A,5Y-0600A,5Y-0601A,5Y-0602A"
    reduced_scope = ",".join(value for value in original_scope.split(",") if value != "5Y-0029A")

    async def create_padded_aircraft():
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO aircraft
                   (aircraft_id, registration, model, roc_id, status, opspec_authorized,
                    created_at, updated_at, created_by, updated_by)
                   VALUES (?, ' 5Y-0029A ', 'Test UAS', 'ROC-001', 'active', 1,
                           'now', 'now', 'admin', 'admin')""",
                (aircraft_id,),
            )
            await db.commit()
        finally:
            await db.close()
    try:
        asyncio.run(create_padded_aircraft())
        response = client.patch(
            "/api/p1/roc/ROC-001", json={"authorized_registrations": reduced_scope}, headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        aircraft = client.get(f"/api/p1/aircraft/{aircraft_id}", headers=admin_headers)
        assert aircraft.status_code == 200
        assert aircraft.json()["opspec_authorized"] is False
    finally:
        async def delete_padded_aircraft():
            db = await get_db()
            try:
                await db.execute("DELETE FROM aircraft WHERE aircraft_id=?", (aircraft_id,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(delete_padded_aircraft())


def test_roc_scope_addition_invalidates_legacy_stale_aircraft_flag(client, admin_headers, preserve_roc_opspec_state):
    registration = "5Y-0029A"
    original_scope = "5Y-0029A,5Y-0030A,5Y-0042A,5Y-0164A,5Y-0600A,5Y-0601A,5Y-0602A"
    reduced_scope = ",".join(value for value in original_scope.split(",") if value != registration)
    aircraft = next(
        row for row in client.get("/api/p1/aircraft", headers=admin_headers).json()
        if row["registration"] == registration
    )

    async def simulate_legacy_scope_change_without_revocation():
        db = await get_db()
        try:
            await db.execute(
                "UPDATE roc_register SET authorized_registrations=? WHERE roc_id='ROC-001'", (reduced_scope,)
            )
            await db.commit()
        finally:
            await db.close()

    asyncio.run(simulate_legacy_scope_change_without_revocation())
    restored = client.patch(
        "/api/p1/roc/ROC-001", json={"authorized_registrations": original_scope}, headers=admin_headers,
    )
    assert restored.status_code == 200, restored.text
    after_addition = next(
        row for row in client.get("/api/p1/aircraft", headers=admin_headers).json()
        if row["aircraft_id"] == aircraft["aircraft_id"]
    )
    assert after_addition["opspec_authorized"] is False



def test_roc_scope_change_rolls_back_when_audit_write_fails(client, admin_headers, monkeypatch):
    original_scope = "5Y-0029A,5Y-0030A,5Y-0042A,5Y-0164A,5Y-0600A,5Y-0601A,5Y-0602A"
    aircraft = next(
        row for row in client.get("/api/p1/aircraft", headers=admin_headers).json()
        if row["registration"] == "5Y-0029A"
    )
    reduced_scope = ",".join(value for value in original_scope.split(",") if value != "5Y-0029A")

    async def fail_audit(*args, **kwargs):
        raise RuntimeError("simulated audit store failure")

    monkeypatch.setattr(p1_routes, "log_audit_event", fail_audit)
    with pytest.raises(RuntimeError, match="simulated audit store failure"):
        client.patch(
            "/api/p1/roc/ROC-001", json={"authorized_registrations": reduced_scope}, headers=admin_headers,
        )

    current_roc = client.get("/api/p1/roc/ROC-001", headers=admin_headers)
    assert current_roc.json()["authorized_registrations"] == original_scope
    current_aircraft = next(
        row for row in client.get("/api/p1/aircraft", headers=admin_headers).json()
        if row["aircraft_id"] == aircraft["aircraft_id"]
    )
    assert current_aircraft["opspec_authorized"] is True


def test_flight_release_is_disabled_when_policy_flag_is_off(client, admin_headers, monkeypatch):
    monkeypatch.setattr(p1_routes, "FLIGHT_RELEASE_ENABLED", False, raising=False)
    response = client.post("/api/p1/flight-releases", json={
        "mission_id": "MSN-NOT-ACTIVE", "plan_id": "FP-NOT-ACTIVE",
        "pre_flight_checklist": "Checklist completed",
        "weather_confirmed": True, "crew_confirmed": True, "aircraft_confirmed": True,
        "weather_evidence": "Weather checked", "crew_evidence": "Crew checked",
        "aircraft_evidence": "Aircraft checked",
    }, headers=admin_headers)
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()


def test_mission_creation_rejects_negative_altitude(client, admin_headers):
    response = client.post("/api/p1/missions", json={
        "title": "Negative altitude mission", "max_altitude_agl": -1,
    }, headers=admin_headers)
    assert response.status_code == 422


def test_mission_update_rejects_negative_altitude(client, admin_headers):
    created = client.post("/api/p1/missions", json={"title": "Altitude update mission"}, headers=admin_headers)
    assert created.status_code == 201, created.text
    response = client.patch(
        f"/api/p1/missions/{created.json()['mission_id']}",
        json={"max_altitude_agl": -1}, headers=admin_headers,
    )
    assert response.status_code == 422


def test_mission_update_rejects_direct_status_mutation(client, admin_headers):
    created = client.post("/api/p1/missions", json={"title": "Status command only"}, headers=admin_headers)
    assert created.status_code == 201, created.text
    response = client.patch(
        f"/api/p1/missions/{created.json()['mission_id']}", json={"status": "cancelled"}, headers=admin_headers,
    )
    assert response.status_code == 422
    current = client.get(f"/api/p1/missions/{created.json()['mission_id']}", headers=admin_headers)
    assert current.json()["status"] == "planned"


def test_flight_plan_creation_rejects_negative_altitude(client, admin_headers):
    mission = client.post("/api/p1/missions", json={"title": "Negative plan altitude"}, headers=admin_headers)
    assert mission.status_code == 201, mission.text
    response = client.post("/api/p1/flight-plans", json={
        "mission_id": mission.json()["mission_id"], "max_altitude_agl": -1,
    }, headers=admin_headers)
    assert response.status_code == 422


class TestMissionStateTransitions:
    def _create_mission(self, client, headers):
        resp = client.post("/api/p1/missions", json={
            "title": "Test mission", "mission_type": "survey",
            "planned_date": "2026-11-01", "location": "Nairobi"
        }, headers=headers)
        assert resp.status_code == 201
        return resp.json()["mission_id"]

    def test_planned_cannot_transition_to_in_progress_without_release(self, client, admin_headers):
        mid = self._create_mission(client, admin_headers)
        resp = client.patch(f"/api/p1/missions/{mid}/state?state=in_progress", headers=admin_headers)
        assert resp.status_code == 400
        assert "invalid transition" in resp.json()["detail"].lower()

    def test_in_progress_requires_a_linked_release_record(self, client, admin_headers):
        mid = self._create_mission(client, admin_headers)

        async def mark_inconsistent_legacy_release():
            db = await get_db()
            try:
                await db.execute("UPDATE missions SET status = 'released', release_id = NULL WHERE mission_id = ?", (mid,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(mark_inconsistent_legacy_release())

        resp = client.patch(f"/api/p1/missions/{mid}/state?state=in_progress", headers=admin_headers)
        assert resp.status_code == 400
        assert "release record" in resp.json()["detail"].lower()

    def test_planned_mission_cannot_be_completed_directly(self, client, admin_headers, safety_headers):
        mid = self._create_mission(client, admin_headers)
        resp = client.patch(f"/api/p1/missions/{mid}/state?state=completed", headers=safety_headers)
        assert resp.status_code == 400
        assert "invalid transition" in resp.json()["detail"].lower()

    def test_post_flight_report_requires_mission_in_progress(self, client, admin_headers):
        mission = client.post("/api/p1/missions", json={"title": "No release", "mission_type": "survey"}, headers=admin_headers).json()
        report = client.post("/api/p1/post-flight-reports", json={"mission_id": mission["mission_id"]}, headers=admin_headers)
        assert report.status_code == 400
        assert "in-progress" in report.json()["detail"].lower()

    def test_invalid_transition_blocked(self, client, admin_headers):
        mid = self._create_mission(client, admin_headers)
        # planned -> completed is invalid (must go through in_progress)
        resp = client.patch(f"/api/p1/missions/{mid}/state?state=completed", headers=admin_headers)
        assert resp.status_code == 400

    def test_terminal_state_no_transition(self, client, admin_headers, safety_headers):
        mid = self._create_mission(client, admin_headers)
        client.patch(f"/api/p1/missions/{mid}/state?state=in_progress", headers=admin_headers)
        client.patch(f"/api/p1/missions/{mid}/state?state=completed", headers=safety_headers)
        # completed -> anything should fail
        resp = client.patch(f"/api/p1/missions/{mid}/state?state=in_progress", headers=admin_headers)
        assert resp.status_code == 400

    def test_cancel_planned_mission(self, client, admin_headers):
        mid = self._create_mission(client, admin_headers)
        resp = client.patch(f"/api/p1/missions/{mid}/state?state=cancelled", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_nonexistent_mission_returns_404(self, client, admin_headers):
        resp = client.patch("/api/p1/missions/NONEXISTENT/state?state=in_progress", headers=admin_headers)
        assert resp.status_code == 404

    def test_master_fleet_preserves_20_aircraft_and_7_opspec_authorized(self, client, admin_headers):
        resp = client.get("/api/p1/aircraft", headers=admin_headers)
        assert resp.status_code == 200
        fleet = resp.json()
        assert len(fleet) == 20
        authorized = [a["registration"] for a in fleet if a.get("opspec_authorized")]
        assert sorted(authorized) == [
            "5Y-0029A", "5Y-0030A", "5Y-0042A", "5Y-0164A", "5Y-0600A", "5Y-0601A", "5Y-0602A"
        ]
        roc = client.get("/api/p1/roc/ROC-001", headers=admin_headers)
        assert roc.status_code == 200
        assert sorted(roc.json()["authorized_registrations"].split(",")) == sorted(authorized)

    def test_released_mission_rejects_changes_to_flight_release_attributes(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Frozen release attributes")
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 201, release.text

        changes = {
            "aircraft_id": "AC-002",
            "roc_id": "ROC-OTHER",
            "rpas_pilot_id": "different-pilot",
            "visual_observer_id": "different-observer",
            "max_altitude_agl": 350,
            "risk_assessment_id": "different-assessment",
            "bvlos_required": True,
            "night_required": True,
        }
        for field, value in changes.items():
            response = client.patch(f"/api/p1/missions/{mission['mission_id']}", json={field: value}, headers=admin_headers)
            assert response.status_code == 409, (field, response.text)
            assert field in response.json()["detail"]

    def test_existing_in_progress_mission_without_release_cannot_change_release_validated_fields(self, client, admin_headers):
        mid = self._create_mission(client, admin_headers)

        async def mark_legacy_in_progress():
            db = await get_db()
            try:
                await db.execute("UPDATE missions SET status = 'in_progress' WHERE mission_id = ?", (mid,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(mark_legacy_in_progress())

        response = client.patch(f"/api/p1/missions/{mid}", json={"max_altitude_agl": 250}, headers=admin_headers)
        assert response.status_code == 409
        assert "locked because its lifecycle has advanced" in response.json()["detail"].lower()

    def test_mission_update_cannot_race_a_flight_release(self, client, admin_headers, monkeypatch):
        mission_id = self._create_mission(client, admin_headers)

        async def release_during_eligibility_check(db, aircraft_id, pilot_id, observer_id):
            await db.execute("UPDATE missions SET status = 'released' WHERE mission_id = ?", (mission_id,))
            await db.commit()

        monkeypatch.setattr(p1_routes, "_check_mission_eligibility", release_during_eligibility_check)
        response = client.patch(
            f"/api/p1/missions/{mission_id}",
            json={"aircraft_id": "AC-002"},
            headers=admin_headers,
        )
        assert response.status_code == 409
        mission_after = client.get(f"/api/p1/missions/{mission_id}", headers=admin_headers).json()
        assert mission_after["aircraft_id"] is None
        assert mission_after["status"] == "released"

    def test_released_mission_rejects_untracked_metadata_edits(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Metadata is locked")
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 201, release.text

        response = client.patch(f"/api/p1/missions/{mission['mission_id']}", json={
            "title": "Changed after release", "description": "Untracked note", "location": "Nairobi",
        }, headers=admin_headers)
        assert response.status_code == 409, response.text
        assert "locked because its lifecycle has advanced" in response.json()["detail"].lower()
        unchanged = client.get(f"/api/p1/missions/{mission['mission_id']}", headers=admin_headers)
        assert unchanged.json()["title"] == mission["title"]
        assert unchanged.json()["description"] == mission["description"]

    def test_released_mission_can_start_and_completion_requires_post_flight_report(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Released lifecycle")
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 201, release.text

        started = client.patch(f"/api/p1/missions/{mission['mission_id']}/state?state=in_progress", headers=admin_headers)
        assert started.status_code == 200
        assert started.json()["status"] == "in_progress"
        completed = client.patch(f"/api/p1/missions/{mission['mission_id']}/state?state=completed", headers=admin_headers)
        assert completed.status_code == 400

    def test_transition_does_not_overwrite_a_concurrent_lifecycle_change(self, client, admin_headers, monkeypatch):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Concurrent transition")
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 201, release.text
        original_get_db = p1_routes.get_db

        async def get_db_with_concurrent_abort():
            db = await original_get_db()
            original_execute = db.execute

            async def execute(sql, parameters=None):
                if sql.startswith("UPDATE missions SET status = ?, updated_at = ?, updated_by = ? WHERE mission_id = ?"):
                    await original_execute("UPDATE missions SET status = 'aborted' WHERE mission_id = ?", (mission["mission_id"],))
                    await db.commit()
                return await original_execute(sql, parameters)

            setattr(db, "execute", execute)
            return db

        monkeypatch.setattr(p1_routes, "get_db", get_db_with_concurrent_abort)
        response = client.patch(f"/api/p1/missions/{mission['mission_id']}/state?state=in_progress", headers=admin_headers)
        assert response.status_code == 409
        final = client.get(f"/api/p1/missions/{mission['mission_id']}", headers=admin_headers)
        assert final.json()["status"] == "aborted"

    def test_in_progress_mission_accepts_post_flight_report_and_completes(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Positive release and PFR")
        release = client.post("/api/p1/flight-releases", json={
            "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
            "pre_flight_checklist": "Checklist itemized and completed", "weather_confirmed": True,
            "crew_confirmed": True, "aircraft_confirmed": True,
            "weather_evidence": "Forecast reviewed at dispatch", "crew_evidence": "Verified RPAS pilot authorization and availability",
            "aircraft_evidence": "Active aircraft, OpSpec listing, and insurance verified",
        }, headers=admin_headers)
        assert release.status_code == 201, release.text
        assert release.json()["weather_evidence"] == "Forecast reviewed at dispatch"
        listed = client.get("/api/p1/flight-releases", params={"mission_id": mission["mission_id"]}, headers=admin_headers)
        assert listed.status_code == 200
        assert listed.json()[0]["crew_evidence"] == "Verified RPAS pilot authorization and availability"
        premature = client.post("/api/p1/post-flight-reports", json={
            "mission_id": mission["mission_id"], "actual_duration_min": 20,
        }, headers=admin_headers)
        assert premature.status_code == 400
        assert "in-progress" in premature.json()["detail"].lower()
        started = client.patch(f"/api/p1/missions/{mission['mission_id']}/state?state=in_progress", headers=admin_headers)
        assert started.status_code == 200, started.text
        report = client.post("/api/p1/post-flight-reports", json={
            "mission_id": mission["mission_id"], "actual_duration_min": 20, "incidents": "None reported"
        }, headers=admin_headers)
        assert report.status_code == 201, report.text
        assert client.get(f"/api/p1/missions/{mission['mission_id']}", headers=admin_headers).json()["status"] == "completed"
        duplicate = client.post("/api/p1/post-flight-reports", json={
            "mission_id": mission["mission_id"], "actual_duration_min": 20, "incidents": "None reported"
        }, headers=admin_headers)
        assert duplicate.status_code == 409

    def test_post_flight_report_rejects_empty_substantive_details(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Empty PFR details")
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 201, release.text
        started = client.patch(f"/api/p1/missions/{mission['mission_id']}/state?state=in_progress", headers=admin_headers)
        assert started.status_code == 200, started.text

        response = client.post("/api/p1/post-flight-reports", json={"mission_id": mission["mission_id"]}, headers=admin_headers)
        assert response.status_code == 422
        assert "at least one" in response.json()["detail"].lower()
        unchanged = client.get(f"/api/p1/missions/{mission['mission_id']}", headers=admin_headers)
        assert unchanged.json()["status"] == "in_progress"
        assert unchanged.json()["post_flight_report_id"] is None

    @pytest.mark.parametrize("field,value", [
        ("actual_duration_min", -1), ("actual_max_altitude", -1),
        ("battery_cycles", -1), ("flight_hours", -0.1),
    ])
    def test_post_flight_report_rejects_negative_measurements(self, client, admin_headers, field, value):
        response = client.post(
            "/api/p1/post-flight-reports",
            json={"mission_id": "MSN-NOT-CREATED", field: value},
            headers=admin_headers,
        )
        assert response.status_code == 422

    def test_flight_release_requires_a_linked_risk_assessment(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(
            client, admin_headers, "Missing risk assessment", with_risk_assessment=False,
        )
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 400
        assert "risk assessment" in release.json()["detail"].lower()

    def test_flight_release_requires_the_om_flight_risk_model(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "SMS model is not flight risk")
        async def switch_to_sms_model():
            db = await get_db()
            try:
                await db.execute(
                    "UPDATE risk_assessments SET risk_model = 'sms_5x5' WHERE assessment_id = ?",
                    (mission["risk_assessment_id"],),
                )
                await db.commit()
            finally:
                await db.close()
        asyncio.run(switch_to_sms_model())
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 400
        assert "om" in release.json()["detail"].lower()

    def test_flight_plan_cannot_be_created_after_mission_release(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "No plan after release")
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 201, release.text

        created = client.post("/api/p1/flight-plans", json={
            "mission_id": mission["mission_id"], "route_description": "Post-release replacement",
            "max_altitude_agl": 300,
        }, headers=admin_headers)
        assert created.status_code == 409

    def test_flight_plan_approval_cannot_be_repeated_after_release(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "No approval after release")
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 201, release.text

        approval = client.patch(
            f"/api/p1/flight-plans/{plan['plan_id']}/approve", headers=_flight_plan_reviewer_headers(),
        )
        assert approval.status_code == 409

    def test_flight_plan_creator_cannot_approve_their_own_plan(self, client, admin_headers):
        mission = client.post("/api/p1/missions", json={
            "title": "Flight plan SoD", "max_altitude_agl": 300,
        }, headers=admin_headers)
        assert mission.status_code == 201, mission.text
        plan = client.post("/api/p1/flight-plans", json={
            "mission_id": mission.json()["mission_id"], "route_description": "Test route",
            "max_altitude_agl": 300,
        }, headers=admin_headers)
        assert plan.status_code == 201, plan.text

        approval = client.patch(
            f"/api/p1/flight-plans/{plan.json()['plan_id']}/approve", headers=admin_headers,
        )
        assert approval.status_code == 403

    def test_release_requires_the_current_approved_flight_plan(self, client, admin_headers):
        mission, old_plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Current plan pointer")
        replacement = client.post("/api/p1/flight-plans", json={
            "mission_id": mission["mission_id"], "route_description": "Replacement approved route",
            "max_altitude_agl": 300,
        }, headers=admin_headers)
        assert replacement.status_code == 201, replacement.text
        approved = client.patch(
            f"/api/p1/flight-plans/{replacement.json()['plan_id']}/approve", headers=_flight_plan_reviewer_headers(),
        )
        assert approved.status_code == 200, approved.text

        release = _release_mission(client, mission, old_plan, admin_headers)
        assert release.status_code == 400
        assert "current" in release.json()["detail"].lower()

    def test_flight_release_rejects_plan_altitude_above_roc_even_when_mission_altitude_is_lower(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Mismatched plan altitude")

        async def raise_approved_plan_altitude():
            db = await get_db()
            try:
                await db.execute(
                    "UPDATE flight_plans SET max_altitude_agl = 500 WHERE plan_id = ?",
                    (plan["plan_id"],),
                )
                await db.commit()
            finally:
                await db.close()
        asyncio.run(raise_approved_plan_altitude())

        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 400
        assert "altitude" in release.json()["detail"].lower()

    def test_flight_release_requires_an_altitude_for_roc_validation(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Missing planned altitude")

        async def remove_both_altitudes():
            db = await get_db()
            try:
                await db.execute("UPDATE missions SET max_altitude_agl = NULL WHERE mission_id = ?", (mission["mission_id"],))
                await db.execute("UPDATE flight_plans SET max_altitude_agl = NULL WHERE plan_id = ?", (plan["plan_id"],))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(remove_both_altitudes())

        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 400
        assert "altitude" in release.json()["detail"].lower()

    @pytest.mark.parametrize("missing", ["mission", "plan"])
    def test_flight_release_requires_altitude_on_both_mission_and_plan(self, client, admin_headers, missing):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, f"One-sided altitude missing: {missing}")

        async def clear_one_altitude():
            db = await get_db()
            try:
                if missing == "mission":
                    await db.execute("UPDATE missions SET max_altitude_agl = NULL WHERE mission_id = ?", (mission["mission_id"],))
                else:
                    await db.execute("UPDATE flight_plans SET max_altitude_agl = NULL WHERE plan_id = ?", (plan["plan_id"],))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(clear_one_altitude())

        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 400
        assert "both" in release.json()["detail"].lower()

    def test_mission_cannot_link_assessment_owned_by_a_different_mission(self, client, admin_headers):
        first = client.post("/api/p1/missions", json={"title": "First mission"}, headers=admin_headers).json()
        second = client.post("/api/p1/missions", json={"title": "Second mission"}, headers=admin_headers).json()
        assessment = client.post("/api/p1/risk-assessments", json={
            "title": "First mission risk", "mission_id": first["mission_id"],
            "risk_model": "sms_5x5", "likelihood": "rare", "severity": "negligible", "risk_level": "low",
        }, headers=admin_headers)
        assert assessment.status_code == 201, assessment.text

        linked = client.patch(f"/api/p1/missions/{second['mission_id']}", json={
            "risk_assessment_id": assessment.json()["assessment_id"],
        }, headers=admin_headers)
        assert linked.status_code == 422
        assert "different mission" in linked.json()["detail"].lower()

    def test_flight_release_rejects_legacy_plan_self_approval_via_alias(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Legacy self-approved plan")
        legacy_creator_alias = f"legacy-creator-{uuid.uuid4().hex}"

        async def rewrite_plan_approval_as_creator_alias():
            db = await get_db()
            try:
                row = await (await db.execute(
                    "SELECT created_by FROM flight_plans WHERE plan_id = ?", (plan["plan_id"],)
                )).fetchone()
                assert row and row["created_by"]
                await db.execute(
                    "INSERT INTO user_id_aliases (legacy_user_id, canonical_user_id, merged_at) VALUES (?, ?, datetime('now'))",
                    (legacy_creator_alias, row["created_by"]),
                )
                await db.execute(
                    "UPDATE flight_plans SET approved_by = ? WHERE plan_id = ?",
                    (legacy_creator_alias, plan["plan_id"]),
                )
                await db.commit()
            finally:
                await db.close()
        asyncio.run(rewrite_plan_approval_as_creator_alias())

        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 400
        assert "independent" in release.json()["detail"].lower()

    def test_flight_release_rejects_legacy_risk_self_review_via_alias(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Legacy self-reviewed risk")
        assessment_id = mission["risk_assessment_id"]
        legacy_assessor_alias = f"legacy-assessor-{uuid.uuid4().hex}"

        async def rewrite_risk_review_as_assessor_alias():
            db = await get_db()
            try:
                row = await (await db.execute(
                    "SELECT assessor_id FROM risk_assessments WHERE assessment_id = ?", (assessment_id,)
                )).fetchone()
                assert row and row["assessor_id"]
                await db.execute(
                    "INSERT INTO user_id_aliases (legacy_user_id, canonical_user_id, merged_at) VALUES (?, ?, datetime('now'))",
                    (legacy_assessor_alias, row["assessor_id"]),
                )
                await db.execute(
                    "UPDATE risk_assessments SET reviewed_by = ? WHERE assessment_id = ?",
                    (legacy_assessor_alias, assessment_id),
                )
                await db.commit()
            finally:
                await db.close()
        asyncio.run(rewrite_risk_review_as_assessor_alias())

        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 400
        assert "independent" in release.json()["detail"].lower()

    def test_flight_release_requires_risk_assessment_approval_even_for_low_risk(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Unapproved low risk")
        assessment = client.post("/api/p1/risk-assessments", json={
            "title": "Low risk", "mission_id": mission["mission_id"],
            "risk_model": "om_flight_26", "likelihood": "rare", "severity": "negligible",
            "exposure": "rare", "risk_level": "low",
        }, headers=admin_headers)
        assert assessment.status_code == 201, assessment.text
        linked = client.patch(f"/api/p1/missions/{mission['mission_id']}", json={
            "risk_assessment_id": assessment.json()["assessment_id"],
        }, headers=admin_headers)
        assert linked.status_code == 200, linked.text
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 400
        assert "approved" in release.json()["detail"].lower()

    def test_release_fails_closed_for_unsupported_stored_risk_model(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Unsupported risk model")
        assessment = client.post("/api/p1/risk-assessments", json={
            "title": "Low flight risk", "mission_id": mission["mission_id"],
            "risk_model": "om_flight_26", "likelihood": "unlikely", "severity": "negligible",
            "exposure": "rare", "risk_level": "low",
        }, headers=admin_headers)
        assert assessment.status_code == 201, assessment.text
        approved = client.post(
            f"/api/p1/risk-assessments/{assessment.json()['assessment_id']}/approve",
            headers=_risk_reviewer_headers(),
        )
        assert approved.status_code == 200, approved.text
        assessment_id = assessment.json()["assessment_id"]
        linked = client.patch(f"/api/p1/missions/{mission['mission_id']}", json={"risk_assessment_id": assessment_id}, headers=admin_headers)
        assert linked.status_code == 200

        async def tamper_assessment_model():
            db = await get_db()
            try:
                await db.execute("UPDATE risk_assessments SET risk_model = 'unknown' WHERE assessment_id = ?", (assessment_id,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(tamper_assessment_model())

        release = client.post("/api/p1/flight-releases", json={
            "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
            "pre_flight_checklist": "Checklist complete", "weather_confirmed": True,
            "crew_confirmed": True, "aircraft_confirmed": True,
            "weather_evidence": "Weather reviewed", "crew_evidence": "Credentials reviewed",
            "aircraft_evidence": "Aircraft and insurance verified",
        }, headers=admin_headers)
        assert release.status_code == 400
        assert "risk model" in release.json()["detail"].lower()

    def test_release_and_semantic_audit_event_commit_together(self, client, admin_headers, monkeypatch):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Atomic release audit")

        async def fail_audit(*args, **kwargs):
            raise RuntimeError("simulated audit store failure")

        monkeypatch.setattr(p1_routes, "log_audit_event", fail_audit)
        with pytest.raises(RuntimeError, match="simulated audit store failure"):
            client.post("/api/p1/flight-releases", json={
                "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
                "pre_flight_checklist": "Checklist completed", "weather_confirmed": True,
                "crew_confirmed": True, "aircraft_confirmed": True,
                "weather_evidence": "Forecast reviewed", "crew_evidence": "Crew records verified",
                "aircraft_evidence": "Aircraft/insurance verified",
            }, headers=admin_headers)

        releases = client.get("/api/p1/flight-releases", params={"mission_id": mission["mission_id"]}, headers=admin_headers)
        assert releases.status_code == 200
        assert releases.json() == []

    def test_release_recomputes_stored_risk_score_before_gate(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Tampered risk score")
        assessment = client.post("/api/p1/risk-assessments", json={
            "title": "Low flight risk", "mission_id": mission["mission_id"],
            "risk_model": "om_flight_26", "likelihood": "unlikely", "severity": "negligible",
            "exposure": "rare", "risk_level": "low",
        }, headers=admin_headers)
        assessment_id = assessment.json()["assessment_id"]
        approved = client.post(
            f"/api/p1/risk-assessments/{assessment_id}/approve",
            headers=_risk_reviewer_headers(),
        )
        assert approved.status_code == 200, approved.text
        assert client.patch(f"/api/p1/missions/{mission['mission_id']}", json={"risk_assessment_id": assessment_id}, headers=admin_headers).status_code == 200

        async def tamper_score():
            db = await get_db()
            try:
                await db.execute("UPDATE risk_assessments SET risk_score = 0 WHERE assessment_id = ?", (assessment_id,))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(tamper_score())

        release = client.post("/api/p1/flight-releases", json={
            "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
            "pre_flight_checklist": "Checklist complete", "weather_confirmed": True,
            "crew_confirmed": True, "aircraft_confirmed": True,
            "weather_evidence": "Weather reviewed", "crew_evidence": "Credentials reviewed",
            "aircraft_evidence": "Aircraft and insurance verified",
        }, headers=admin_headers)
        assert release.status_code == 400
        assert "inconsistent" in release.json()["detail"].lower()

    def test_release_rechecks_crew_qualification_expiry(self, client, admin_headers):
        mission, plan, _, license_id = _prepare_releasable_mission(client, admin_headers, "Expired crew release")
        expired = client.patch(f"/api/p2/personnel/licenses/{license_id}", json={"expiry_date": "2020-01-01"}, headers=admin_headers)
        assert expired.status_code == 200
        release = client.post("/api/p1/flight-releases", json={
            "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
            "pre_flight_checklist": "Checklist complete", "weather_confirmed": True,
            "crew_confirmed": True, "aircraft_confirmed": True,
            "weather_evidence": "Weather reviewed", "crew_evidence": "Pilot credential reviewed",
            "aircraft_evidence": "Aircraft/insurance verified",
        }, headers=admin_headers)
        assert release.status_code == 422
        assert "crew" in str(release.json()["detail"]).lower()

    def test_release_rechecks_aircraft_insurance_expiry(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Expired insurance release")
        policies = client.get("/api/p2/aircraft/AC-001/insurance", headers=admin_headers).json()
        for policy in policies:
            response = client.patch(f"/api/p2/insurance/{policy['insurance_id']}", json={"expiry_date": "2020-01-01", "status": "expired"}, headers=admin_headers)
            assert response.status_code == 200
        try:
            release = client.post("/api/p1/flight-releases", json={
                "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
                "pre_flight_checklist": "Checklist complete", "weather_confirmed": True,
                "crew_confirmed": True, "aircraft_confirmed": True,
                "weather_evidence": "Weather reviewed", "crew_evidence": "Pilot credential reviewed",
                "aircraft_evidence": "Aircraft/insurance verified",
            }, headers=admin_headers)
            assert release.status_code == 422
            assert "aircraft" in str(release.json()["detail"]).lower()
        finally:
            for policy in policies:
                client.patch(f"/api/p2/insurance/{policy['insurance_id']}", json={"expiry_date": policy["expiry_date"], "status": policy["status"]}, headers=admin_headers)

    def test_release_fails_closed_for_expired_roc(self, client, admin_headers):
        mission = client.post("/api/p1/missions", json={"title": "Expired ROC", "mission_type": "survey", "roc_id": "ROC-001"}, headers=admin_headers).json()
        plan = client.post("/api/p1/flight-plans", json={"mission_id": mission["mission_id"], "route_description": "Test route"}, headers=admin_headers).json()
        client.patch(f"/api/p1/flight-plans/{plan['plan_id']}/approve", headers=_flight_plan_reviewer_headers())
        expired = client.patch("/api/p1/roc/ROC-001", json={"expiry_date": "2020-01-01"}, headers=admin_headers)
        assert expired.status_code == 200
        try:
            release = client.post("/api/p1/flight-releases", json={
                "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
                "pre_flight_checklist": "Checklist complete", "weather_confirmed": True,
                "crew_confirmed": True, "aircraft_confirmed": True,
                "weather_evidence": "Weather reviewed", "crew_evidence": "Crew reviewed",
                "aircraft_evidence": "Aircraft reviewed",
            }, headers=admin_headers)
            assert release.status_code == 400
            assert "roc" in release.json()["detail"].lower()
        finally:
            client.patch("/api/p1/roc/ROC-001", json={"expiry_date": "2027-10-11"}, headers=admin_headers)

    def test_release_requires_explicit_weather_crew_and_aircraft_evidence(self, client, admin_headers):
        ops_headers = {"X-Role": "head_operations", "X-Actor": "u-ops"}
        mission = client.post("/api/p1/missions", json={"title": "Evidence gate", "mission_type": "survey", "max_altitude_agl": 300}, headers=ops_headers).json()
        plan = client.post("/api/p1/flight-plans", json={"mission_id": mission["mission_id"], "route_description": "Test route", "max_altitude_agl": 300}, headers=ops_headers).json()
        client.patch(f"/api/p1/flight-plans/{plan['plan_id']}/approve", headers=admin_headers)
        release = client.post("/api/p1/flight-releases", json={
            "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
            "pre_flight_checklist": "Checklist completed", "weather_confirmed": True,
            "crew_confirmed": True, "aircraft_confirmed": True,
        }, headers=ops_headers)
        assert release.status_code == 400
        assert "evidence" in release.json()["detail"].lower()

    def test_release_fails_closed_when_mission_has_no_assigned_aircraft(self, client, admin_headers):
        ops_headers = {"X-Role": "head_operations", "X-Actor": "u-ops"}
        mission = client.post("/api/p1/missions", json={"title": "No aircraft", "mission_type": "survey", "roc_id": "ROC-001", "max_altitude_agl": 300}, headers=ops_headers).json()
        plan = client.post("/api/p1/flight-plans", json={"mission_id": mission["mission_id"], "route_description": "Test route", "max_altitude_agl": 300}, headers=ops_headers).json()
        client.patch(f"/api/p1/flight-plans/{plan['plan_id']}/approve", headers=admin_headers)
        release = client.post("/api/p1/flight-releases", json={
            "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
            "pre_flight_checklist": "Checklist completed", "weather_confirmed": True,
            "crew_confirmed": True, "aircraft_confirmed": True,
            "weather_evidence": "METAR checked", "crew_evidence": "Crew records reviewed",
            "aircraft_evidence": "Airworthiness and insurance checked",
        }, headers=ops_headers)
        assert release.status_code == 400
        assert "aircraft" in release.json()["detail"].lower()

    def test_flight_release_enforces_delegated_role_opspec_and_om_gates(self, client, admin_headers, safety_headers):
        ops_headers = {"X-Role": "head_operations", "X-Actor": "u-ops"}
        for ac_id in ("AC-001", "AC-004"):
            client.post(f"/api/p2/aircraft/{ac_id}/insurance", json={
                "insurance_type": "liability",
                "policy_number": f"POL-{ac_id}",
                "insurer": "KFL Insurer",
                "expiry_date": "2027-12-31",
            }, headers=admin_headers)
        # AC-004 (5Y-0043A) is in the 20-aircraft fleet but NOT on the 7-aircraft OpSpec page
        m_unauth = client.post("/api/p1/missions", json={
            "title": "Non-OpSpec aircraft mission",
            "mission_type": "survey",
            "roc_id": "ROC-001",
            "aircraft_id": "AC-004",
            "max_altitude_agl": 300,
        }, headers=admin_headers)
        assert m_unauth.status_code == 201
        mid_unauth = m_unauth.json()["mission_id"]

        fp_unauth = client.post("/api/p1/flight-plans", json={
            "mission_id": mid_unauth, "route_description": "Test route", "max_altitude_agl": 300
        }, headers=admin_headers).json()

        # Head of Safety cannot approve flight plan (OM §2.3.1: HOO / Chief Pilot)
        bad_role = client.patch(f"/api/p1/flight-plans/{fp_unauth['plan_id']}/approve", headers=safety_headers)
        assert bad_role.status_code == 403

        # Head of Operations can approve flight plan
        ok_approve = client.patch(f"/api/p1/flight-plans/{fp_unauth['plan_id']}/approve", headers=ops_headers)
        assert ok_approve.status_code == 200

        # Release blocked because AC-004 is not in the 7 OpSpec-authorized registrations
        rel_unauth = client.post("/api/p1/flight-releases", json={
            "mission_id": mid_unauth,
            "plan_id": fp_unauth["plan_id"],
            "pre_flight_checklist": "OM Part B Enclosure 7 completed",
            "weather_confirmed": True,
            "crew_confirmed": True,
            "aircraft_confirmed": True,
            "weather_evidence": "Weather checked against forecast",
            "crew_evidence": "Crew license and availability checked",
            "aircraft_evidence": "Aircraft and insurance checked",
        }, headers=ops_headers)
        assert rel_unauth.status_code == 400
        assert "opspec" in rel_unauth.json()["detail"].lower()

        # Mission exceeding 400ft AGL or BVLOS is blocked on release under ROC-001
        m_alt = client.post("/api/p1/missions", json={
            "title": "High altitude mission",
            "mission_type": "survey",
            "roc_id": "ROC-001",
            "aircraft_id": "AC-001",
            "max_altitude_agl": 500,
        }, headers=admin_headers).json()
        fp_alt = client.post("/api/p1/flight-plans", json={
            "mission_id": m_alt["mission_id"], "route_description": "High route", "max_altitude_agl": 500
        }, headers=admin_headers).json()
        client.patch(f"/api/p1/flight-plans/{fp_alt['plan_id']}/approve", headers=ops_headers)
        rel_alt = client.post("/api/p1/flight-releases", json={
            "mission_id": m_alt["mission_id"],
            "plan_id": fp_alt["plan_id"],
            "pre_flight_checklist": "OM Part B Enclosure 7 completed",
            "weather_confirmed": True,
            "crew_confirmed": True,
            "aircraft_confirmed": True,
            "weather_evidence": "Weather checked against forecast",
            "crew_evidence": "Crew license and availability checked",
            "aircraft_evidence": "Aircraft and insurance checked",
        }, headers=ops_headers)
        assert rel_alt.status_code == 400
        assert "400" in rel_alt.json()["detail"]

    def test_aircraft_identity_update_invalidates_opspec_authorization(self, client, admin_headers):
        aircraft_id = f"AC-IDENTITY-{uuid.uuid4().hex[:8]}"
        async def create_aircraft():
            db = await get_db()
            try:
                await db.execute(
                    """INSERT INTO aircraft
                       (aircraft_id, registration, model, roc_id, status, opspec_authorized,
                        created_at, updated_at, created_by, updated_by)
                       VALUES (?, '5Y-TEST-001', 'Test UAS', 'ROC-001', 'active', 1,
                               'now', 'now', 'admin', 'admin')""",
                    (aircraft_id,),
                )
                await db.commit()
            finally:
                await db.close()
        asyncio.run(create_aircraft())

        try:
            updated = client.patch(
                f"/api/p1/aircraft/{aircraft_id}", json={"registration": "5Y-TEST-002"}, headers=admin_headers,
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["opspec_authorized"] is False

            async def read_revocation_event():
                db = await get_db()
                try:
                    row = await (await db.execute(
                        """SELECT details FROM audit_events WHERE entity_type='aircraft' AND entity_id=?
                           AND action='opspec_authorization_revoked' ORDER BY rowid DESC LIMIT 1""",
                        (aircraft_id,),
                    )).fetchone()
                    return row["details"] if row else None
                finally:
                    await db.close()

            import json
            event_details = asyncio.run(read_revocation_event())
            assert event_details is not None
            details = json.loads(event_details)
            assert details["reason"] == "aircraft identity/configuration changed"
            assert details["changed_fields"]["registration"] == {
                "from": "5Y-TEST-001", "to": "5Y-TEST-002",
            }
        finally:
            async def delete_aircraft():
                db = await get_db()
                try:
                    await db.execute("DELETE FROM aircraft WHERE aircraft_id = ?", (aircraft_id,))
                    await db.commit()
                finally:
                    await db.close()
            asyncio.run(delete_aircraft())

    def test_aircraft_identity_change_rolls_back_when_revocation_audit_fails(self, client, admin_headers, monkeypatch):
        aircraft_id = f"AC-IDENTITY-ROLLBACK-{uuid.uuid4().hex[:8]}"

        async def create_aircraft():
            db = await get_db()
            try:
                await db.execute(
                    """INSERT INTO aircraft
                       (aircraft_id, registration, model, roc_id, status, opspec_authorized,
                        created_at, updated_at, created_by, updated_by)
                       VALUES (?, '5Y-ROLLBACK-001', 'Test UAS', 'ROC-001', 'active', 1,
                               'now', 'now', 'admin', 'admin')""",
                    (aircraft_id,),
                )
                await db.commit()
            finally:
                await db.close()
        asyncio.run(create_aircraft())

        async def fail_audit(*args, **kwargs):
            raise RuntimeError("simulated aircraft audit failure")

        monkeypatch.setattr(p1_routes, "log_audit_event", fail_audit)
        try:
            with pytest.raises(RuntimeError, match="simulated aircraft audit failure"):
                client.patch(
                    f"/api/p1/aircraft/{aircraft_id}", json={"registration": "5Y-ROLLBACK-002"}, headers=admin_headers,
                )
            current = client.get(f"/api/p1/aircraft/{aircraft_id}", headers=admin_headers)
            assert current.status_code == 200
            assert current.json()["registration"] == "5Y-ROLLBACK-001"
            assert current.json()["opspec_authorized"] is True
        finally:
            async def delete_aircraft():
                db = await get_db()
                try:
                    await db.execute("DELETE FROM aircraft WHERE aircraft_id = ?", (aircraft_id,))
                    await db.commit()
                finally:
                    await db.close()
            asyncio.run(delete_aircraft())

    def test_release_rejects_stale_opspec_flag_for_unlisted_registration(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Changed aircraft registration")
        original = client.get("/api/p1/aircraft/AC-001", headers=admin_headers).json()
        try:
            _set_aircraft_authorization_fields("AC-001", "5Y-9999A", original["roc_id"], 1)
            release = _release_mission(client, mission, plan, admin_headers)
            assert release.status_code == 400
            assert "authorized registration" in release.json()["detail"].lower()
        finally:
            _set_aircraft_authorization_fields(
                "AC-001", original["registration"], original["roc_id"], int(original["opspec_authorized"]),
            )

    def test_release_rejects_aircraft_without_explicit_roc_assignment(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Missing aircraft ROC")
        original = client.get("/api/p1/aircraft/AC-001", headers=admin_headers).json()
        try:
            _set_aircraft_authorization_fields("AC-001", original["registration"], None, 1)
            release = _release_mission(client, mission, plan, admin_headers)
            assert release.status_code == 400
            assert "not assigned to roc" in release.json()["detail"].lower()
        finally:
            _set_aircraft_authorization_fields(
                "AC-001", original["registration"], original["roc_id"], int(original["opspec_authorized"]),
            )

    def test_release_requires_explicit_mission_roc_assignment(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Missing mission ROC")
        async def clear_mission_roc():
            db = await get_db()
            try:
                await db.execute("UPDATE missions SET roc_id = NULL WHERE mission_id = ?", (mission["mission_id"],))
                await db.commit()
            finally:
                await db.close()
        asyncio.run(clear_mission_roc())
        release = _release_mission(client, mission, plan, admin_headers)
        assert release.status_code == 400
        assert "roc assignment" in release.json()["detail"].lower()

    def test_startup_catalogue_correction_preserves_explicit_opspec_revocation(self):
        async def read_state():
            db = await get_db()
            try:
                cursor = await db.execute("SELECT authorized_registrations FROM roc_register WHERE roc_id = 'ROC-001'")
                roc = await cursor.fetchone()
                cursor = await db.execute("SELECT opspec_authorized FROM aircraft WHERE aircraft_id = 'AC-001'")
                aircraft = await cursor.fetchone()
                return aircraft["opspec_authorized"], roc["authorized_registrations"]
            finally:
                await db.close()

        async def set_authorized_registrations(value):
            db = await get_db()
            try:
                await db.execute("UPDATE roc_register SET authorized_registrations = ? WHERE roc_id = 'ROC-001'", (value,))
                await db.commit()
            finally:
                await db.close()

        _, original_scope = asyncio.run(read_state())
        try:
            _set_aircraft_authorization_fields("AC-001", "5Y-0029A", "ROC-001", 0)
            asyncio.run(set_authorized_registrations("5Y-TEST-REVIEW"))
            asyncio.run(database.apply_catalogue_corrections())
            authorized, registrations = asyncio.run(read_state())
            assert authorized == 0
            assert registrations == "5Y-TEST-REVIEW"
        finally:
            _set_aircraft_authorization_fields("AC-001", "5Y-0029A", "ROC-001", 1)
            asyncio.run(set_authorized_registrations(original_scope))

    def test_catalogue_correction_does_not_infer_fresh_seed_from_empty_scope(self):
        async def snapshot():
            db = await get_db()
            try:
                roc = await (await db.execute(
                    "SELECT authorized_registrations FROM roc_register WHERE roc_id = 'ROC-001'"
                )).fetchone()
                assert roc is not None
                aircraft = await (await db.execute(
                    "SELECT aircraft_id, opspec_authorized FROM aircraft ORDER BY aircraft_id"
                )).fetchall()
                marker = await (await db.execute(
                    "SELECT value, updated_at FROM app_settings WHERE key = 'opspec_authorization_baseline_initialized'"
                )).fetchone()
                return roc["authorized_registrations"], [dict(row) for row in aircraft], dict(marker) if marker else None
            finally:
                await db.close()

        async def clear_scope_and_marker():
            db = await get_db()
            try:
                await db.execute("UPDATE roc_register SET authorized_registrations = NULL WHERE roc_id = 'ROC-001'")
                await db.execute("UPDATE aircraft SET opspec_authorized = 0")
                await db.execute("DELETE FROM app_settings WHERE key = 'opspec_authorization_baseline_initialized'")
                await db.commit()
            finally:
                await db.close()

        original_scope, original_aircraft, original_marker = asyncio.run(snapshot())
        try:
            asyncio.run(clear_scope_and_marker())
            asyncio.run(database.apply_catalogue_corrections())
            scope, aircraft, marker = asyncio.run(snapshot())
            assert scope is None
            assert all(row["opspec_authorized"] == 0 for row in aircraft)
            assert marker is None
        finally:
            async def restore():
                db = await get_db()
                try:
                    await db.execute(
                        "UPDATE roc_register SET authorized_registrations = ? WHERE roc_id = 'ROC-001'",
                        (original_scope,),
                    )
                    for row in original_aircraft:
                        await db.execute(
                            "UPDATE aircraft SET opspec_authorized = ? WHERE aircraft_id = ?",
                            (row["opspec_authorized"], row["aircraft_id"]),
                        )
                    if original_marker:
                        await db.execute(
                            "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                            ("opspec_authorization_baseline_initialized", original_marker["value"], original_marker["updated_at"]),
                        )
                    else:
                        await db.execute("DELETE FROM app_settings WHERE key = 'opspec_authorization_baseline_initialized'")
                    await db.commit()
                finally:
                    await db.close()
            asyncio.run(restore())