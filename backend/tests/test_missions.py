import asyncio
import uuid
import pytest
from app.database import get_db
from app import p1_routes


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


def _prepare_releasable_mission(client, headers, title="Eligible flight"):
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
    plan = client.post("/api/p1/flight-plans", json={
        "mission_id": mission.json()["mission_id"], "route_description": "Approved test route", "max_altitude_agl": 300,
    }, headers=headers)
    assert plan.status_code == 201
    approved = client.patch(f"/api/p1/flight-plans/{plan.json()['plan_id']}/approve", headers=headers)
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

    def test_post_flight_report_requires_released_mission(self, client, admin_headers):
        mission = client.post("/api/p1/missions", json={"title": "No release", "mission_type": "survey"}, headers=admin_headers).json()
        report = client.post("/api/p1/post-flight-reports", json={"mission_id": mission["mission_id"]}, headers=admin_headers)
        assert report.status_code == 400
        assert "released" in report.json()["detail"].lower()

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

    def test_released_mission_accepts_post_flight_report_and_completes(self, client, admin_headers):
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
        report = client.post("/api/p1/post-flight-reports", json={
            "mission_id": mission["mission_id"], "actual_duration_min": 20, "incidents": "None reported"
        }, headers=admin_headers)
        assert report.status_code == 201, report.text
        assert client.get(f"/api/p1/missions/{mission['mission_id']}", headers=admin_headers).json()["status"] == "completed"
        duplicate = client.post("/api/p1/post-flight-reports", json={
            "mission_id": mission["mission_id"], "actual_duration_min": 20, "incidents": "None reported"
        }, headers=admin_headers)
        assert duplicate.status_code == 409

    def test_release_fails_closed_for_unsupported_stored_risk_model(self, client, admin_headers):
        mission, plan, _, _ = _prepare_releasable_mission(client, admin_headers, "Unsupported risk model")
        assessment = client.post("/api/p1/risk-assessments", json={
            "title": "Low flight risk", "mission_id": mission["mission_id"],
            "risk_model": "sms_5x5", "likelihood": "unlikely", "severity": "negligible", "risk_level": "low",
        }, headers=admin_headers)
        assert assessment.status_code == 201, assessment.text
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
            "risk_model": "sms_5x5", "likelihood": "unlikely", "severity": "negligible", "risk_level": "low",
        }, headers=admin_headers)
        assessment_id = assessment.json()["assessment_id"]
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
        client.patch(f"/api/p1/flight-plans/{plan['plan_id']}/approve", headers=admin_headers)
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

    def test_release_requires_explicit_weather_crew_and_aircraft_evidence(self, client):
        ops_headers = {"X-Role": "head_operations", "X-Actor": "u-ops"}
        mission = client.post("/api/p1/missions", json={"title": "Evidence gate", "mission_type": "survey"}, headers=ops_headers).json()
        plan = client.post("/api/p1/flight-plans", json={"mission_id": mission["mission_id"], "route_description": "Test route"}, headers=ops_headers).json()
        client.patch(f"/api/p1/flight-plans/{plan['plan_id']}/approve", headers=ops_headers)
        release = client.post("/api/p1/flight-releases", json={
            "mission_id": mission["mission_id"], "plan_id": plan["plan_id"],
            "pre_flight_checklist": "Checklist completed", "weather_confirmed": True,
            "crew_confirmed": True, "aircraft_confirmed": True,
        }, headers=ops_headers)
        assert release.status_code == 400
        assert "evidence" in release.json()["detail"].lower()

    def test_release_fails_closed_when_mission_has_no_assigned_aircraft(self, client):
        ops_headers = {"X-Role": "head_operations", "X-Actor": "u-ops"}
        mission = client.post("/api/p1/missions", json={"title": "No aircraft", "mission_type": "survey"}, headers=ops_headers).json()
        plan = client.post("/api/p1/flight-plans", json={"mission_id": mission["mission_id"], "route_description": "Test route"}, headers=ops_headers).json()
        client.patch(f"/api/p1/flight-plans/{plan['plan_id']}/approve", headers=ops_headers)
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
        }, headers=ops_headers)
        assert m_unauth.status_code == 201
        mid_unauth = m_unauth.json()["mission_id"]

        fp_unauth = client.post("/api/p1/flight-plans", json={
            "mission_id": mid_unauth, "route_description": "Test route", "max_altitude_agl": 300
        }, headers=ops_headers).json()

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
        }, headers=ops_headers).json()
        fp_alt = client.post("/api/p1/flight-plans", json={
            "mission_id": m_alt["mission_id"], "route_description": "High route", "max_altitude_agl": 500
        }, headers=ops_headers).json()
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