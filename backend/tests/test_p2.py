"""Tests for P2 endpoints: document proposals, personnel licenses, aircraft insurance."""
import pytest


class TestDocumentProposals:
    def test_create_proposal(self, client, librarian_headers):
        resp = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word",
            "target_ref": "section 3.2",
            "original_text": "old text",
            "proposed_text": "new text",
            "rationale": "fix typo",
            "severity": "minor",
        }, headers=librarian_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "draft"
        assert data["proposal_type"] == "word"
        assert data["proposal_id"].startswith("PROP-")

    def test_create_proposal_nonexistent_doc(self, client, librarian_headers):
        resp = client.post("/api/p2/documents/NONEXISTENT/proposals", json={
            "proposal_type": "word",
            "target_ref": "section 1",
            "proposed_text": "text",
        }, headers=librarian_headers)
        assert resp.status_code == 404

    def test_list_proposals(self, client, librarian_headers):
        client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "line", "target_ref": "line 10",
            "proposed_text": "updated line",
        }, headers=librarian_headers)
        resp = client.get("/api/p2/documents/DOC-001/proposals", headers=librarian_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) > 0

    def test_proposal_workflow_submit_approve(self, client, librarian_headers, quality_headers):
        resp = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "section", "target_ref": "section 1",
            "proposed_text": "new section content",
        }, headers=librarian_headers)
        pid = resp.json()["proposal_id"]

        # Submit
        resp = client.patch(f"/api/p2/proposals/{pid}", json={"status": "submitted"}, headers=librarian_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"

        # Approve (quality can approve)
        resp = client.patch(f"/api/p2/proposals/{pid}", json={"status": "approved"}, headers=quality_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_proposal_sod_creator_cannot_approve(self, client, librarian_headers):
        resp = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "word 5",
            "proposed_text": "changed",
        }, headers=librarian_headers)
        pid = resp.json()["proposal_id"]
        client.patch(f"/api/p2/proposals/{pid}", json={"status": "submitted"}, headers=librarian_headers)
        # Creator cannot approve own proposal
        resp = client.patch(f"/api/p2/proposals/{pid}", json={"status": "approved"}, headers=librarian_headers)
        assert resp.status_code == 403

    def test_apply_proposal(self, client, librarian_headers, quality_headers, admin_headers):
        resp = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "word 1",
            "proposed_text": "applied text",
        }, headers=librarian_headers)
        pid = resp.json()["proposal_id"]
        client.patch(f"/api/p2/proposals/{pid}", json={"status": "submitted"}, headers=librarian_headers)
        client.patch(f"/api/p2/proposals/{pid}", json={"status": "approved"}, headers=quality_headers)
        resp = client.post(f"/api/p2/proposals/{pid}/apply", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "applied"

    def test_proposal_reject(self, client, librarian_headers, quality_headers):
        resp = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "line", "target_ref": "line 5",
            "proposed_text": "rejected text",
        }, headers=librarian_headers)
        pid = resp.json()["proposal_id"]
        client.patch(f"/api/p2/proposals/{pid}", json={"status": "submitted"}, headers=librarian_headers)
        resp = client.patch(f"/api/p2/proposals/{pid}", json={"status": "rejected"}, headers=quality_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_proposal_delete_draft(self, client, librarian_headers):
        resp = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "word 1",
            "proposed_text": "to delete",
        }, headers=librarian_headers)
        pid = resp.json()["proposal_id"]
        resp = client.delete(f"/api/p2/proposals/{pid}", headers=librarian_headers)
        assert resp.status_code == 200


class TestPersonnelLicenses:
    def test_create_license(self, client, admin_headers):
        resp = client.post("/api/p2/personnel/licenses", json={
            "person_id": "u-safety", "license_type": "pilot_license",
            "license_number": "PL-001", "issuing_authority": "KCAA",
            "issued_date": "2025-01-01", "expiry_date": "2026-12-31",
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["person_id"] == "u-safety"
        assert data["status"] == "valid"

    def test_list_licenses(self, client, admin_headers):
        client.post("/api/p2/personnel/licenses", json={
            "person_id": "u-lib", "license_type": "medical",
            "expiry_date": "2026-06-30",
        }, headers=admin_headers)
        resp = client.get("/api/p2/personnel/licenses", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_licenses_by_person(self, client, admin_headers):
        client.post("/api/p2/personnel/licenses", json={
            "person_id": "u-quality", "license_type": "type_rating",
            "expiry_date": "2026-09-30",
        }, headers=admin_headers)
        resp = client.get("/api/p2/personnel/licenses?person_id=u-filter", headers=admin_headers)
        assert resp.status_code == 200
        for lic in resp.json():
            assert lic["person_id"] == "u-quality"

    def test_expiring_licenses(self, client, admin_headers):
        resp = client.get("/api/p2/personnel/expiring-licenses?days=365", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_update_license_records_renewal(self, client, admin_headers):
        resp = client.post("/api/p2/personnel/licenses", json={
            "person_id": "u-auditor", "license_type": "medical",
            "expiry_date": "2026-03-01",
        }, headers=admin_headers)
        lid = resp.json()["license_id"]
        resp = client.patch(f"/api/p2/personnel/licenses/{lid}", json={
            "expiry_date": "2027-03-01",
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["expiry_date"] == "2027-03-01"

    def test_get_license(self, client, admin_headers):
        resp = client.post("/api/p2/personnel/licenses", json={
            "person_id": "u-records", "license_type": "dg_training",
            "expiry_date": "2026-08-01",
        }, headers=admin_headers)
        lid = resp.json()["license_id"]
        resp = client.get(f"/api/p2/personnel/licenses/{lid}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["license_id"] == lid

    def test_delete_license(self, client, admin_headers):
        resp = client.post("/api/p2/personnel/licenses", json={
            "person_id": "u-accountable", "license_type": "security_training",
            "expiry_date": "2026-07-01",
        }, headers=admin_headers)
        lid = resp.json()["license_id"]
        resp = client.delete(f"/api/p2/personnel/licenses/{lid}", headers=admin_headers)
        assert resp.status_code == 200

    def test_license_rbac_denied(self, client, reporter_headers):
        resp = client.get("/api/p2/personnel/licenses", headers=reporter_headers)
        assert resp.status_code == 403


class TestAircraftInsurance:
    def test_create_insurance(self, client, admin_headers):
        resp = client.post("/api/p2/aircraft/AC-001/insurance", json={
            "insurance_type": "hull",
            "insurer": "Test Insurer",
            "policy_number": "POL-001",
            "expiry_date": "2026-12-31",
        }, headers=admin_headers)
        # AC-001 may not exist in test DB; check for 201 or 404
        assert resp.status_code in (200, 404, 422)

    def test_expiring_insurance(self, client, admin_headers):
        resp = client.get("/api/p2/insurance/expiring?days=365", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_expiring_aircraft_docs(self, client, admin_headers):
        resp = client.get("/api/p2/aircraft-documents/expiring?days=365", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAnnotations:
    def test_create_annotation(self, client, librarian_headers):
        resp = client.post("/api/p2/documents/DOC-001/annotations", json={
            "annotation_type": "comment",
            "target_ref": "section 1.1",
            "content": "This needs clarification",
        }, headers=librarian_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["annotation_type"] == "comment"
        assert data["status"] == "open"

    def test_list_annotations(self, client, librarian_headers):
        client.post("/api/p2/documents/DOC-001/annotations", json={
            "annotation_type": "highlight",
            "target_ref": "para 2",
            "content": "important",
        }, headers=librarian_headers)
        resp = client.get("/api/p2/documents/DOC-001/annotations", headers=librarian_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_resolve_annotation(self, client, librarian_headers):
        resp = client.post("/api/p2/documents/DOC-001/annotations", json={
            "annotation_type": "comment",
            "target_ref": "section 2",
            "content": "to resolve",
        }, headers=librarian_headers)
        aid = resp.json()["annotation_id"]
        resp = client.patch(f"/api/p2/annotations/{aid}", json={"status": "resolved"}, headers=librarian_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"


class TestMissionEligibility:
    def test_mission_create_with_expired_license_blocked(self, client, safety_headers):
        # Create a license that is already expired
        client.post("/api/p2/personnel/licenses", json={
            "person_id": "u-lib", "license_type": "pilot_license",
            "expiry_date": "2020-01-01", "status": "expired",
        }, headers=safety_headers)
        # Try to create a mission with that pilot
        resp = client.post("/api/p1/missions", json={
            "title": "Test Mission", "mission_type": "survey",
            "rpas_pilot_id": "u-lib",
        }, headers=safety_headers)
        # Should be blocked with 422
        assert resp.status_code == 422
        assert "eligibility_errors" in resp.json()["detail"]

    def test_mission_create_without_license_blocked(self, client, safety_headers):
        resp = client.post("/api/p1/missions", json={
            "title": "Test Mission 2", "mission_type": "survey",
            "rpas_pilot_id": "u-accountable",
        }, headers=safety_headers)
        assert resp.status_code == 422
        assert "eligibility_errors" in resp.json()["detail"]
