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