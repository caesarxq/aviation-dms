import pytest


class TestTrainingRecords:
    def test_list_training_records(self, client, admin_headers):
        resp = client.get("/api/p1/training-records", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_by_category(self, client, admin_headers):
        resp = client.get("/api/p1/training-records", params={"category": "general"}, headers=admin_headers)
        assert resp.status_code == 200
        assert all(r["training_category"] == "general" for r in resp.json())

    def test_filter_by_person_id(self, client, admin_headers):
        resp = client.get("/api/p1/training-records", params={"person_id": "u-chief-pilot"}, headers=admin_headers)
        assert resp.status_code == 200
        assert all(r["person_id"] == "u-chief-pilot" for r in resp.json())

    def test_create_training_record(self, client, admin_headers):
        payload = {
            "person_id": "u-chief-pilot",
            "training_category": "general",
            "training_type": "Drone Safety",
            "training_date": "2025-01-01",
            "expiry_date": "2026-01-01",
            "certificate_number": "CERT-001",
            "notes": "Annual refresher",
        }
        resp = client.post("/api/p1/training-records", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["record_id"].startswith("TRN")
        assert data["status"] == "valid"

    def test_update_training_record(self, client, admin_headers):
        payload = {
            "person_id": "u-chief-pilot",
            "training_category": "general",
            "training_type": "Drone Safety",
            "training_date": "2025-01-01",
            "expiry_date": "2026-01-01",
            "certificate_number": "CERT-001",
            "notes": "Updated note",
        }
        create = client.post("/api/p1/training-records", json=payload, headers=admin_headers)
        record_id = create.json()["record_id"]
        resp = client.patch(f"/api/p1/training-records/{record_id}", json={"notes": "Updated note"}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated note"

    def test_delete_training_record(self, client, admin_headers):
        payload = {
            "person_id": "u-chief-pilot",
            "training_category": "general",
            "training_type": "Drone Safety",
            "training_date": "2025-01-01",
            "expiry_date": "2026-01-01",
            "certificate_number": "CERT-001",
        }
        create = client.post("/api/p1/training-records", json=payload, headers=admin_headers)
        record_id = create.json()["record_id"]
        resp = client.delete(f"/api/p1/training-records/{record_id}", headers=admin_headers)
        assert resp.status_code == 204
        get = client.get(f"/api/p1/training-records", params={"person_id": "u-chief-pilot"}, headers=admin_headers)
        assert record_id not in [r["record_id"] for r in get.json()]

    def test_unauthorized_access_denied(self, client):
        resp = client.get("/api/p1/training-records", headers={"X-Role": "system_admin", "X-Actor": "nonexistent"})
        assert resp.status_code in (401, 403)
