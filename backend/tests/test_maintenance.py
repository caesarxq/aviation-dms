import pytest


class TestMaintenanceRecords:
    def test_list_maintenance_records(self, client, admin_headers):
        resp = client.get("/api/p1/maintenance-records", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_and_update_maintenance(self, client, admin_headers):
        payload = {
            "aircraft_registration": "5Y-ABC",
            "maintenance_type": "A-Check",
            "description": "Routine inspection",
            "performed_by": "tech-1",
            "performed_at": "2026-01-02",
        }
        r = client.post("/api/p1/maintenance-records", json=payload, headers=admin_headers)
        assert r.status_code == 201
        rec = r.json()
        assert rec["record_id"].startswith("MAINT-")
        assert rec["status"] == "completed"
        upd = client.patch(f"/api/p1/maintenance-records/{rec['record_id']}", json={"status": "overdue"}, headers=admin_headers)
        assert upd.status_code == 200
        assert upd.json()["status"] == "overdue"

    def test_delete_maintenance(self, client, admin_headers):
        payload = {
            "aircraft_registration": "5Y-XYZ",
            "maintenance_type": "B-Check",
            "description": "Heavy check",
            "performed_by": "tech-2",
            "performed_at": "2026-01-03",
        }
        r = client.post("/api/p1/maintenance-records", json=payload, headers=admin_headers)
        assert r.status_code == 201
        rec = r.json()
        d = client.delete(f"/api/p1/maintenance-records/{rec['record_id']}", headers=admin_headers)
        assert d.status_code == 204

    def test_maintenance_requires_auth(self, client):
        r = client.get("/api/p1/maintenance-records", headers={"X-Role": "unknown", "X-Actor": "nobody"})
        assert r.status_code in {401, 403}

    def test_maintenance_defaults(self, client, admin_headers):
        payload = {
            "aircraft_registration": "5Y-DEF",
            "maintenance_type": "C-Check",
            "description": "Full inspection",
            "performed_by": "tech-3",
            "performed_at": "2026-01-04",
        }
        r = client.post("/api/p1/maintenance-records", json=payload, headers=admin_headers)
        assert r.status_code == 201
        rec = r.json()
        assert rec["status"] == "completed"
        assert rec["next_due"] is None
        assert rec["notes"] is None
