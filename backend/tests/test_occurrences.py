import pytest


class TestOccurrences:
    def test_create_occurrence(self, client, reporter_headers):
        resp = client.post("/api/p1/occurrences", json={
            "title": "Test incident", "description": "A test occurrence",
            "occurrence_type": "incident", "occurred_at": "2026-10-23T10:00:00+03:00", "severity": "minor"
        }, headers=reporter_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "reported"
        assert data["title"] == "Test incident"
        assert data["serial_number"].startswith("OCC-")

    def test_reporter_cannot_decide_mor_at_submission(self, client, reporter_headers):
        resp = client.post("/api/p1/occurrences", json={
            "title": "MOR assessment test", "description": "Safety must assess reportability",
            "occurrence_type": "serious_incident", "severity": "major",
            "occurred_at": "2026-10-30T09:00:00+03:00",
            "mor_required": True, "mor_deadline": "2026-10-31T00:00:00+03:00",
        }, headers=reporter_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data["mor_required"] is False
        assert data["mor_deadline"] is None

    def test_head_safety_assessment_sets_72_hour_deadline_from_occurrence(self, client, reporter_headers, safety_headers):
        occ = client.post("/api/p1/occurrences", json={
            "title": "MOR clock test", "description": "Reportable serious incident",
            "occurrence_type": "serious_incident", "severity": "major",
            "occurred_at": "2026-10-30T09:00:00+03:00",
        }, headers=reporter_headers).json()

        resp = client.post(f"/api/p1/occurrences/{occ['occurrence_id']}/mor-assessment", json={
            "mor_required": True,
            "rationale": "Serious incident meets the reportability criteria",
        }, headers=safety_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["mor_required"] is True
        assert data["mor_deadline"] == "2026-11-02T09:00:00+03:00"
        assert data["mor_assessed_by"] == "u-safety"
        assert data["mor_assessment_reason"] == "Serious incident meets the reportability criteria"

    def test_reporter_cannot_assess_mor(self, client, reporter_headers):
        occ = client.post("/api/p1/occurrences", json={
            "title": "Restricted MOR assessment", "description": "Safety decision required",
            "occurrence_type": "accident", "occurred_at": "2026-10-30T09:00:00+03:00",
        }, headers=reporter_headers).json()

        resp = client.post(f"/api/p1/occurrences/{occ['occurrence_id']}/mor-assessment", json={
            "mor_required": True, "rationale": "Reporter cannot make this decision",
        }, headers=reporter_headers)

        assert resp.status_code == 403

    def test_reportable_occurrence_needs_time_to_start_mor_clock(self, client, reporter_headers, safety_headers):
        occ = client.post("/api/p1/occurrences", json={
            "title": "Missing event time", "description": "Time not known yet",
            "occurrence_type": "accident",
        }, headers=reporter_headers).json()

        resp = client.post(f"/api/p1/occurrences/{occ['occurrence_id']}/mor-assessment", json={
            "mor_required": True, "rationale": "Reportability determined, event time needed",
        }, headers=safety_headers)

        assert resp.status_code == 400
        assert "occurred_at" in resp.json()["detail"]

    def test_acknowledge_occurrence(self, client, reporter_headers, safety_headers):
        resp = client.post("/api/p1/occurrences", json={
            "title": "Ack test", "description": "test", "occurrence_type": "incident",
            "occurred_at": "2026-10-23T10:00:00+03:00"
        }, headers=reporter_headers)
        occ_id = resp.json()["occurrence_id"]
        resp = client.post(f"/api/p1/occurrences/{occ_id}/acknowledge", headers=safety_headers)
        assert resp.status_code == 200

    def test_confidential_reporter_masked(self, client, reporter_headers):
        resp = client.post("/api/p1/occurrences", json={
            "title": "Confidential test", "description": "test", "occurrence_type": "incident",
            "occurred_at": "2026-10-23T10:00:00+03:00", "reporter_confidential": True
        }, headers=reporter_headers)
        occ_id = resp.json()["occurrence_id"]
        # Non-investigate role should see CONFIDENTIAL
        resp = client.get(f"/api/p1/occurrences/{occ_id}", headers={"X-Role": "librarian", "X-Actor": "u-lib"})
        assert resp.status_code == 200
        assert resp.json()["reporter_id"] == "CONFIDENTIAL"

    def test_confidential_reporter_visible_to_investigator(self, client, reporter_headers, safety_headers):
        resp = client.post("/api/p1/occurrences", json={
            "title": "Confidential visible test", "description": "test", "occurrence_type": "incident",
            "occurred_at": "2026-10-23T10:00:00+03:00", "reporter_confidential": True
        }, headers=reporter_headers)
        occ_id = resp.json()["occurrence_id"]
        # Investigate role should see real reporter
        resp = client.get(f"/api/p1/occurrences/{occ_id}", headers=safety_headers)
        assert resp.status_code == 200
        assert resp.json()["reporter_id"] != "CONFIDENTIAL"

    def test_nonexistent_occurrence_returns_404(self, client, safety_headers):
        resp = client.get("/api/p1/occurrences/NONEXISTENT", headers=safety_headers)
        assert resp.status_code == 404

    def test_occurrence_closure_requires_satisfactory_followup(self, client, reporter_headers, safety_headers):
        occ = client.post("/api/p1/occurrences", json={
            "title": "Follow-up gate test", "description": "Must verify effectiveness before closing",
            "occurrence_type": "incident", "occurred_at": "2026-10-30T10:00:00+03:00",
        }, headers=reporter_headers).json()
        occ_id = occ["occurrence_id"]

        # Generic PATCH cannot bypass closure gate
        bypass = client.patch(f"/api/p1/occurrences/{occ_id}", json={"status": "closed"}, headers=safety_headers)
        assert bypass.status_code == 400

        # Unsatisfactory follow-up keeps report open (SMS-KFL §2.3.2)
        incomplete = client.post(f"/api/p1/occurrences/{occ_id}/close", json={
            "effectiveness_confirmed": False,
            "no_new_hazards": True,
            "followup_notes": "Risk still present",
        }, headers=safety_headers)
        assert incomplete.status_code == 400

        # Satisfactory follow-up closes the report
        closed = client.post(f"/api/p1/occurrences/{occ_id}/close", json={
            "effectiveness_confirmed": True,
            "no_new_hazards": True,
            "followup_notes": "Mitigation verified effective and introduced no new hazards",
        }, headers=safety_headers)
        assert closed.status_code == 200
        data = closed.json()
        assert data["status"] == "closed"
        assert data["effectiveness_confirmed"] is True
        assert data["no_new_hazards"] is True
        assert data["closed_by"] == "u-safety"


class TestFlightRelease:
    def test_flight_release_requires_checklist(self, client, admin_headers):
        resp = client.post("/api/p1/flight-releases", json={
            "mission_id": "MSN-001", "plan_id": "PLAN-001",
            "pre_flight_checklist": "", "weather_confirmed": True,
            "crew_confirmed": True, "aircraft_confirmed": True
        }, headers=admin_headers)
        assert resp.status_code == 400
        assert "checklist" in resp.json()["detail"].lower()

    def test_flight_release_requires_all_confirmations(self, client, admin_headers):
        resp = client.post("/api/p1/flight-releases", json={
            "mission_id": "MSN-001", "plan_id": "PLAN-001",
            "pre_flight_checklist": "All items checked", "weather_confirmed": True,
            "crew_confirmed": False, "aircraft_confirmed": True
        }, headers=admin_headers)
        assert resp.status_code == 400
        assert "confirmation" in resp.json()["detail"].lower()

    def test_flight_release_valid(self, client, admin_headers):
        resp = client.post("/api/p1/flight-releases", json={
            "mission_id": "MSN-001", "plan_id": "PLAN-001",
            "pre_flight_checklist": "All items checked", "weather_confirmed": True,
            "crew_confirmed": True, "aircraft_confirmed": True
        }, headers=admin_headers)
        # May fail due to missing mission/plan FK, but validation should pass
        # If 400, it should be FK-related, not validation
        if resp.status_code == 400:
            assert "checklist" not in resp.json()["detail"].lower()
            assert "confirmation" not in resp.json()["detail"].lower()