import pytest


class TestDocumentVersioning:
    def test_create_version_starts_draft(self, client, librarian_headers):
        resp = client.post("/api/p0/versions", json={
            "document_id": "DOC-001", "version_number": "02.00.00", "content": "v2 content"
        }, headers=librarian_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["state"] == "draft"
        assert data["kcaa_approved"] == 0

    def test_create_version_nonexistent_doc(self, client, librarian_headers):
        resp = client.post("/api/p0/versions", json={
            "document_id": "NONEXISTENT", "version_number": "01.00.00", "content": "test"
        }, headers=librarian_headers)
        assert resp.status_code == 404

    def test_state_transition_draft_to_in_review(self, client, librarian_headers):
        resp = client.post("/api/p0/versions", json={
            "document_id": "DOC-001", "version_number": "02.01.00", "content": "test"
        }, headers=librarian_headers)
        vid = resp.json()["version_id"]
        resp = client.patch(f"/api/p0/versions/{vid}/state?state=in_review", headers=librarian_headers)
        assert resp.status_code == 200
        assert resp.json()["state"] == "in_review"

    def test_state_transition_requires_permission(self, client, librarian_headers):
        resp = client.post("/api/p0/versions", json={
            "document_id": "DOC-001", "version_number": "02.02.00", "content": "test"
        }, headers=librarian_headers)
        vid = resp.json()["version_id"]
        client.patch(f"/api/p0/versions/{vid}/state?state=in_review", headers=librarian_headers)
        # Librarian cannot approve
        resp = client.patch(f"/api/p0/versions/{vid}/state?state=approved", headers=librarian_headers)
        assert resp.status_code == 403

    def test_kcaa_gate_blocks_publish(self, client, librarian_headers, quality_headers, admin_headers):
        resp = client.post("/api/p0/versions", json={
            "document_id": "DOC-001", "version_number": "02.03.00", "content": "test"
        }, headers=librarian_headers)
        vid = resp.json()["version_id"]
        client.patch(f"/api/p0/versions/{vid}/state?state=in_review", headers=librarian_headers)
        client.patch(f"/api/p0/versions/{vid}/state?state=approved", headers=quality_headers)
        # Publish without KCAA approval should fail
        resp = client.patch(f"/api/p0/versions/{vid}/state?state=published", headers=admin_headers)
        assert resp.status_code == 403
        assert "KCAA" in resp.json()["detail"]

    def test_kcaa_approve_then_publish(self, client, librarian_headers, quality_headers, admin_headers):
        resp = client.post("/api/p0/versions", json={
            "document_id": "DOC-001", "version_number": "02.04.00", "content": "test"
        }, headers=librarian_headers)
        vid = resp.json()["version_id"]
        client.patch(f"/api/p0/versions/{vid}/state?state=in_review", headers=librarian_headers)
        client.patch(f"/api/p0/versions/{vid}/state?state=approved", headers=quality_headers)
        resp = client.patch(f"/api/p0/versions/{vid}/state?state=kcaa_approved", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["kcaa_approved"] == 1
        resp = client.patch(f"/api/p0/versions/{vid}/state?state=published", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["state"] == "published"

    def test_sod_creator_cannot_publish(self, client, librarian_headers, quality_headers, admin_headers):
        resp = client.post("/api/p0/versions", json={
            "document_id": "DOC-002", "version_number": "01.01.00", "content": "test"
        }, headers=librarian_headers)
        vid = resp.json()["version_id"]
        client.patch(f"/api/p0/versions/{vid}/state?state=in_review", headers=librarian_headers)
        client.patch(f"/api/p0/versions/{vid}/state?state=approved", headers=quality_headers)
        # Admin (not creator) can publish, but librarian (creator) cannot
        resp = client.patch(f"/api/p0/versions/{vid}/state?state=published", headers=librarian_headers)
        assert resp.status_code == 403

    def test_nonexistent_version_returns_404(self, client, librarian_headers):
        resp = client.patch("/api/p0/versions/NONEXISTENT/state?state=draft", headers=librarian_headers)
        assert resp.status_code == 404

    def test_get_document_content(self, client, librarian_headers):
        resp = client.get("/api/p0/documents/DOC-001/content", headers=librarian_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "version_number" in data

    def test_nonexistent_document_content(self, client, librarian_headers):
        resp = client.get("/api/p0/documents/NONEXISTENT/content", headers=librarian_headers)
        assert resp.status_code == 404

    def test_save_content_creates_new_version(self, client, librarian_headers):
        resp = client.put("/api/p0/documents/DOC-001/content", json={
            "content": "Updated content", "change_summary": "test update"
        }, headers=librarian_headers)
        assert resp.status_code == 200
        assert resp.status_code == 200
        assert "version_number" in resp.json()


class TestEvidencePack:
    def test_evidence_pack_checksum(self, client, librarian_headers):
        resp = client.post("/api/p0/evidence-pack?entity_type=document&entity_id=DOC-001", headers=librarian_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["checksum"].startswith("sha256-")
        assert len(data["checksum"]) == 7 + 64  # "sha256-" + 64 hex chars

    def test_evidence_pack_deterministic(self, client, librarian_headers):
        resp1 = client.post("/api/p0/evidence-pack?entity_type=document&entity_id=DOC-001", headers=librarian_headers)
        resp2 = client.post("/api/p0/evidence-pack?entity_type=document&entity_id=DOC-001", headers=librarian_headers)
        assert resp1.json()["checksum"] == resp2.json()["checksum"]