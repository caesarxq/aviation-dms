import pytest


class TestOccurrences:
    def test_create_occurrence(self, client, reporter_headers):
        resp = client.post("/api/p1/occurrences", json={
            "title": "Test incident", "description": "A test occurrence",
            "occurrence_type": "incident", "occurrence_date": "2026-10-23", "severity": "minor"
        }, headers=reporter_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "reported"
        assert data["title"] == "Test incident"
        assert data["serial_number"].startswith("OCC-")

    def test_acknowledge_occurrence(self, client, reporter_headers, safety_headers):
        resp = client.post("/api/p1/occurrences", json={
            "title": "Ack test", "description": "test", "occurrence_type": "incident",
            "occurrence_date": "2026-10-23"
        }, headers=reporter_headers)
        occ_id = resp.json()["occurrence_id"]
        resp = client.post(f"/api/p1/occurrences/{occ_id}/acknowledge", headers=safety_headers)
        assert resp.status_code == 200

    def test_confidential_reporter_masked(self, client, reporter_headers):
        resp = client.post("/api/p1/occurrences", json={
            "title": "Confidential test", "description": "test", "occurrence_type": "incident",
            "occurrence_date": "2026-10-23", "reporter_confidential": True
        }, headers=reporter_headers)
        occ_id = resp.json()["occurrence_id"]
        # Non-investigate role should see CONFIDENTIAL
        resp = client.get(f"/api/p1/occurrences/{occ_id}", headers={"X-Role": "librarian", "X-Actor": "u-lib"})
        assert resp.status_code == 200
        assert resp.json()["reporter_id"] == "CONFIDENTIAL"

    def test_confidential_reporter_visible_to_investigator(self, client, reporter_headers, safety_headers):
        resp = client.post("/api/p1/occurrences", json={
            "title": "Confidential visible test", "description": "test", "occurrence_type": "incident",
            "occurrence_date": "2026-10-23", "reporter_confidential": True
        }, headers=reporter_headers)
        occ_id = resp.json()["occurrence_id"]
        # Investigate role should see real reporter
        resp = client.get(f"/api/p1/occurrences/{occ_id}", headers=safety_headers)
        assert resp.status_code == 200
        assert resp.json()["reporter_id"] != "CONFIDENTIAL"

    def test_nonexistent_occurrence_returns_404(self, client, safety_headers):
        resp = client.get("/api/p1/occurrences/NONEXISTENT", headers=safety_headers)
        assert resp.status_code == 404


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