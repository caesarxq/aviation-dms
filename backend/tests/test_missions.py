import pytest


class TestMissionStateTransitions:
    def _create_mission(self, client, headers):
        resp = client.post("/api/p1/missions", json={
            "title": "Test mission", "mission_type": "survey",
            "planned_date": "2026-11-01", "location": "Nairobi"
        }, headers=headers)
        assert resp.status_code == 201
        return resp.json()["mission_id"]

    def test_planned_to_in_progress(self, client, admin_headers):
        mid = self._create_mission(client, admin_headers)
        resp = client.patch(f"/api/p1/missions/{mid}/state?state=in_progress", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_in_progress_to_completed(self, client, admin_headers, safety_headers):
        mid = self._create_mission(client, admin_headers)
        client.patch(f"/api/p1/missions/{mid}/state?state=in_progress", headers=admin_headers)
        resp = client.patch(f"/api/p1/missions/{mid}/state?state=completed", headers=safety_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

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
        }, headers=ops_headers)
        assert rel_alt.status_code == 400
        assert "400" in rel_alt.json()["detail"]