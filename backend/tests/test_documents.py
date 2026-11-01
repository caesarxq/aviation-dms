import pytest


class TestDocumentVersioning:
    def test_catalogue_labels_and_kcaa_requirements(self, client, librarian_headers):
        response = client.get("/api/p0/documents", headers=librarian_headers)
        assert response.status_code == 200
        by_id = {item["document_id"]: item for item in response.json()}
        assert by_id["DOC-006"]["title"] == "Security Management System Manual"
        assert by_id["DOC-007"]["title"] == "Dangerous Goods Manual"
        assert by_id["DOC-012"]["title"] == "Quality Management System Manual"
        assert by_id["DOC-012"]["doc_class"] == "quality_manual"
        for document_id in ("DOC-006", "DOC-007", "DOC-012"):
            assert by_id[document_id]["kcaa_approval_required"] is True

    def test_qms_and_security_content_matches_catalogue(self, client, librarian_headers):
        expected = {
            "DOC-006": "Security Management System Manual",
            "DOC-012": "Quality Management System Manual",
        }
        for document_id, title in expected.items():
            response = client.get(f"/api/p0/documents/{document_id}/content", headers=librarian_headers)
            assert response.status_code == 200
            assert title in response.json()["content"]

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
        client.patch(f"/api/p0/versions/{vid}/state?state=approved", headers=admin_headers)
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
        client.patch(f"/api/p0/versions/{vid}/state?state=approved", headers=admin_headers)
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
        client.patch(f"/api/p0/versions/{vid}/state?state=approved", headers=admin_headers)
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
        assert "version_number" in resp.json()

    def test_draft_version_does_not_replace_effective_published_content(self, client, librarian_headers):
        baseline = client.get("/api/p0/documents/DOC-006/content", headers=librarian_headers)
        assert baseline.status_code == 200
        baseline_data = baseline.json()
        assert baseline_data["state"] == "published"

        draft = client.put("/api/p0/documents/DOC-006/content", json={
            "content": "Unapproved draft modification", "change_summary": "draft only"
        }, headers=librarian_headers)
        assert draft.status_code == 200
        assert draft.json()["state"] == "draft"

        effective = client.get("/api/p0/documents/DOC-006/content", headers=librarian_headers)
        assert effective.status_code == 200
        assert effective.json()["state"] == "published"
        assert effective.json()["version_id"] == baseline_data["version_id"]

    def test_source_reconciliation_and_embedded_manual_mapping(self, client, librarian_headers):
        resp = client.get("/api/p0/documents", headers=librarian_headers)
        assert resp.status_code == 200
        by_id = {d["document_id"]: d for d in resp.json()}

        assert by_id["DOC-001"]["source_sha256"] == "92a2509879ca39aafd88e69a5a7cbfdfb536715753da674e27689b2929af07b3"
        assert by_id["DOC-012"]["status"] == "published"
        assert by_id["DOC-007"]["source_issued_date"] == "2024-05-01"
        assert by_id["DOC-007"]["approval_evidence_status"] == "pending_letter"
        assert by_id["DOC-004"]["parent_document_id"] == "DOC-001"
        assert by_id["DOC-004"]["parent_section_ref"] == "Part D"
        assert by_id["DOC-005"]["parent_document_id"] == "DOC-001"
        assert by_id["DOC-005"]["parent_section_ref"] == "Part B"

    def test_p0_change_request_cannot_skip_review_to_approved(self, client, librarian_headers, admin_headers):
        cr = client.post("/api/p0/change-requests", json={
            "document_id": "DOC-001",
            "title": "Controlled amendment test",
            "description": "Must pass through review before approval",
            "change_type": "minor",
        }, headers=librarian_headers).json()

        skipped = client.patch(
            f"/api/p0/change-requests/{cr['cr_id']}?status=approved",
            headers=admin_headers,
        )
        assert skipped.status_code in (400, 422)


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