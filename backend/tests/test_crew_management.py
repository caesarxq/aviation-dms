import pytest


class TestCrewMembers:
    def test_list_crew_members(self, client, admin_headers):
        resp = client.get("/api/p1/crew-members", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_and_update_crew(self, client, admin_headers):
        payload = {
            "full_name": "Test Pilot",
            "role": "PIC",
            "base": "Nairobi",
            "status": "active",
        }
        r = client.post("/api/p1/crew-members", json=payload, headers=admin_headers)
        assert r.status_code == 201
        rec = r.json()
        assert rec["crew_id"].startswith("CREW-")
        assert rec["full_name"] == "Test Pilot"
        upd = client.patch(f"/api/p1/crew-members/{rec['crew_id']}", json={"base": "Mombasa"}, headers=admin_headers)
        assert upd.status_code == 200
        assert upd.json()["base"] == "Mombasa"

    def test_delete_crew(self, client, admin_headers):
        payload = {
            "full_name": "Temp Crew",
            "role": "Observer",
            "base": "Nairobi",
            "status": "inactive",
        }
        r = client.post("/api/p1/crew-members", json=payload, headers=admin_headers)
        assert r.status_code == 201
        rec = r.json()
        d = client.delete(f"/api/p1/crew-members/{rec['crew_id']}", headers=admin_headers)
        assert d.status_code == 204

    def test_crew_requires_auth(self, client):
        r = client.get("/api/p1/crew-members", headers={"X-Role": "unknown", "X-Actor": "nobody"})
        assert r.status_code in {401, 403}


class TestDutyRecords:
    def test_list_duty_records(self, client, admin_headers):
        resp = client.get("/api/p1/duty-records", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_and_update_duty(self, client, admin_headers):
        crew_payload = {
            "full_name": "Duty Pilot",
            "role": "PIC",
            "base": "Nairobi",
            "status": "active",
        }
        crew = client.post("/api/p1/crew-members", json=crew_payload, headers=admin_headers).json()
        payload = {
            "crew_id": crew["crew_id"],
            "duty_start": "2026-01-10T08:00",
            "duty_end": "2026-01-10T12:00",
            "role": "PIC",
            "block_hours": 4.0,
        }
        r = client.post("/api/p1/duty-records", json=payload, headers=admin_headers)
        assert r.status_code == 201
        rec = r.json()
        assert rec["duty_id"].startswith("DUTY-")
        upd = client.patch(f"/api/p1/duty-records/{rec['duty_id']}", json={"notes": "Test duty"}, headers=admin_headers)
        assert upd.status_code == 200
        assert upd.json()["notes"] == "Test duty"

    def test_delete_duty(self, client, admin_headers):
        crew_payload = {
            "full_name": "Duty Pilot 2",
            "role": "PIC",
            "base": "Nairobi",
            "status": "active",
        }
        crew = client.post("/api/p1/crew-members", json=crew_payload, headers=admin_headers).json()
        payload = {
            "crew_id": crew["crew_id"],
            "duty_start": "2026-01-11T08:00",
            "duty_end": "2026-01-11T12:00",
            "role": "PIC",
        }
        r = client.post("/api/p1/duty-records", json=payload, headers=admin_headers)
        assert r.status_code == 201
        rec = r.json()
        d = client.delete(f"/api/p1/duty-records/{rec['duty_id']}", headers=admin_headers)
        assert d.status_code == 204

    def test_duty_requires_auth(self, client):
        r = client.get("/api/p1/duty-records", headers={"X-Role": "unknown", "X-Actor": "nobody"})
        assert r.status_code in {401, 403}


class TestCrewQualifications:
    def test_list_qualifications(self, client, admin_headers):
        resp = client.get("/api/p1/crew-qualifications", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_and_update_qualification(self, client, admin_headers):
        crew_payload = {
            "full_name": "Qual Pilot",
            "role": "PIC",
            "base": "Nairobi",
            "status": "active",
        }
        crew = client.post("/api/p1/crew-members", json=crew_payload, headers=admin_headers).json()
        payload = {
            "crew_id": crew["crew_id"],
            "qual_type": "RPC",
            "issue_date": "2026-01-01",
            "expiry_date": "2027-01-01",
        }
        r = client.post("/api/p1/crew-qualifications", json=payload, headers=admin_headers)
        assert r.status_code == 201
        rec = r.json()
        assert rec["qual_id"].startswith("QUAL-")
        upd = client.patch(f"/api/p1/crew-qualifications/{rec['qual_id']}", json={"rating": "A"}, headers=admin_headers)
        assert upd.status_code == 200
        assert upd.json()["rating"] == "A"

    def test_delete_qualification(self, client, admin_headers):
        crew_payload = {
            "full_name": "Qual Pilot 2",
            "role": "PIC",
            "base": "Nairobi",
            "status": "active",
        }
        crew = client.post("/api/p1/crew-members", json=crew_payload, headers=admin_headers).json()
        payload = {
            "crew_id": crew["crew_id"],
            "qual_type": "Medical",
            "issue_date": "2026-01-01",
            "expiry_date": "2027-01-01",
        }
        r = client.post("/api/p1/crew-qualifications", json=payload, headers=admin_headers)
        assert r.status_code == 201
        rec = r.json()
        d = client.delete(f"/api/p1/crew-qualifications/{rec['qual_id']}", headers=admin_headers)
        assert d.status_code == 204

    def test_qualification_requires_auth(self, client):
        r = client.get("/api/p1/crew-qualifications", headers={"X-Role": "unknown", "X-Actor": "nobody"})
        assert r.status_code in {401, 403}


class TestAppSettings:
    def test_get_app_setting(self, client, admin_headers):
        r = client.get("/api/p1/app-settings/fdtl_max_duty_hours", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["value"] == "14"

    def test_update_app_setting(self, client, admin_headers):
        r = client.put("/api/p1/app-settings/fdtl_max_duty_hours", json={"value": "16"}, headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["value"] == "16"
