import asyncio
import hashlib
import uuid
import pytest

from app import p0_auth, p0_routes
from app.database import get_db


@pytest.fixture
def proposal_only_headers(monkeypatch):
    original_has_permission = p0_routes.has_permission
    proposal_permissions = {"document:propose"}

    def has_permission(role, permission):
        if role == "head_safety" and permission.startswith("document:"):
            return permission in proposal_permissions
        return original_has_permission(role, permission)

    monkeypatch.setattr(p0_routes, "has_permission", has_permission)
    return {"X-Role": "head_safety", "X-Actor": "u-safety"}


@pytest.fixture
def independent_publisher_headers(monkeypatch):
    actor_id = f"u-publisher-test-{uuid.uuid4().hex[:8]}"
    monkeypatch.setitem(p0_auth.DEV_IDENTITY_ROLES, actor_id, (actor_id, "system_admin"))

    async def add_publisher():
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO users (user_id, username, email, full_name, role, is_active, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'system_admin', 1, 'now', 'now')",
                (actor_id, actor_id, f"{actor_id}@example.test", "Test Publisher"),
            )
            await db.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'system_admin')", (actor_id,))
            await db.commit()
        finally:
            await db.close()

    async def remove_publisher():
        db = await get_db()
        try:
            await db.execute("DELETE FROM user_roles WHERE user_id = ?", (actor_id,))
            await db.execute("DELETE FROM user_id_aliases WHERE legacy_user_id = ? OR canonical_user_id = ?", (actor_id, actor_id))
            await db.execute("DELETE FROM users WHERE user_id = ?", (actor_id,))
            await db.commit()
        finally:
            await db.close()

    asyncio.run(add_publisher())
    yield {"X-Role": "system_admin", "X-Actor": actor_id}
    asyncio.run(remove_publisher())


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

    def test_kcaa_publication_requires_retained_verified_evidence(self, client, librarian_headers, quality_headers, admin_headers, tmp_path, monkeypatch, independent_publisher_headers):
        monkeypatch.setattr(p0_routes, "KCAA_EVIDENCE_DIR", tmp_path)
        version = client.post(
            "/api/p0/versions",
            json={"document_id": "DOC-001", "version_number": "03.00.00", "content": "external approval pending"},
            headers=librarian_headers,
        ).json()
        version_id = version["version_id"]
        client.patch(f"/api/p0/versions/{version_id}/state?state=in_review", headers=librarian_headers)
        client.patch(f"/api/p0/versions/{version_id}/state?state=approved", headers=admin_headers)

        rejected_unverified = client.patch(
            f"/api/p0/versions/{version_id}/state?state=kcaa_approved&kcaa_reference=FAKE&kcaa_evidence_sha256={'a' * 64}",
            headers=admin_headers,
        )
        assert rejected_unverified.status_code == 422

        evidence_bytes = b"%PDF-1.7\\nKCAA approval certificate test artifact"
        uploaded = client.post(
            f"/api/p0/versions/{version_id}/kcaa-evidence?reference=KCAA-APPROVAL-2026-001",
            content=evidence_bytes,
            headers={**admin_headers, "Content-Type": "application/pdf"},
        )
        assert uploaded.status_code == 201, uploaded.text
        evidence = uploaded.json()
        expected_hash = hashlib.sha256(evidence_bytes).hexdigest()
        assert evidence["file_sha256"] == expected_hash
        assert (tmp_path / evidence["stored_filename"]).read_bytes() == evidence_bytes

        self_verify = client.post(
            f"/api/p0/versions/{version_id}/kcaa-evidence/{evidence['evidence_id']}/verify",
            headers=admin_headers,
        )
        assert self_verify.status_code == 403
        verified = client.post(
            f"/api/p0/versions/{version_id}/kcaa-evidence/{evidence['evidence_id']}/verify",
            headers=quality_headers,
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "verified"
        accountable_headers = {"X-Role": "accountable_manager", "X-Actor": "u-accountable"}
        stored_file = tmp_path / evidence["stored_filename"]
        stored_file.write_bytes(b"%PDF-1.7 tampered")
        tampered = client.patch(
            f"/api/p0/versions/{version_id}/state?state=kcaa_approved&kcaa_evidence_id={evidence['evidence_id']}",
            headers=accountable_headers,
        )
        assert tampered.status_code == 409
        stored_file.write_bytes(evidence_bytes)

        approved = client.patch(
            f"/api/p0/versions/{version_id}/state?state=kcaa_approved&kcaa_evidence_id={evidence['evidence_id']}",
            headers=accountable_headers,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["kcaa_reference"] == "KCAA-APPROVAL-2026-001"
        assert approved.json()["kcaa_evidence_sha256"] == expected_hash
        assert approved.json()["kcaa_evidence_id"] == evidence["evidence_id"]
        uploader_publish = client.patch(f"/api/p0/versions/{version_id}/state?state=published", headers=admin_headers)
        assert uploader_publish.status_code == 403, uploader_publish.text
        publisher_headers = independent_publisher_headers
        published = client.patch(f"/api/p0/versions/{version_id}/state?state=published", headers=publisher_headers)
        assert published.status_code == 200, published.text

    def test_kcaa_approval_chain_requires_a_distinct_publisher(self, client, librarian_headers, quality_headers, admin_headers, tmp_path, monkeypatch, independent_publisher_headers):
        monkeypatch.setattr(p0_routes, "KCAA_EVIDENCE_DIR", tmp_path)
        version = client.post(
            "/api/p0/versions",
            json={"document_id": "DOC-001", "version_number": "03.01.00", "content": "distinct publisher test"},
            headers=librarian_headers,
        ).json()
        version_id = version["version_id"]
        client.patch(f"/api/p0/versions/{version_id}/state?state=in_review", headers=librarian_headers)
        client.patch(f"/api/p0/versions/{version_id}/state?state=approved", headers=admin_headers)

        evidence_bytes = b"%PDF-1.7\\nDistinct publisher approval artifact"
        uploaded = client.post(
            f"/api/p0/versions/{version_id}/kcaa-evidence?reference=KCAA-DISTINCT-PUBLISHER",
            content=evidence_bytes,
            headers={**admin_headers, "Content-Type": "application/pdf"},
        )
        assert uploaded.status_code == 201, uploaded.text
        evidence_id = uploaded.json()["evidence_id"]
        assert client.post(
            f"/api/p0/versions/{version_id}/kcaa-evidence/{evidence_id}/verify", headers=quality_headers
        ).status_code == 200
        accountable_headers = {"X-Role": "accountable_manager", "X-Actor": "u-accountable"}
        approved = client.patch(
            f"/api/p0/versions/{version_id}/state?state=kcaa_approved&kcaa_evidence_id={evidence_id}",
            headers=accountable_headers,
        )
        assert approved.status_code == 200, approved.text

        publisher_headers = independent_publisher_headers

        for same_chain_actor in (admin_headers, quality_headers, accountable_headers):
            denied = client.patch(
                f"/api/p0/versions/{version_id}/state?state=published", headers=same_chain_actor
            )
            assert denied.status_code == 403, denied.text

        independent_publisher = client.patch(
            f"/api/p0/versions/{version_id}/state?state=published", headers=publisher_headers
        )
        assert independent_publisher.status_code == 200, independent_publisher.text

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

    def test_draft_only_document_is_not_readable_without_draft_permission(self, client, librarian_headers, reporter_headers):
        created = client.post(
            "/api/p0/documents",
            json={"title": "Draft-only document", "doc_class": "sop", "owner_id": "u-lib"},
            headers=librarian_headers,
        )
        assert created.status_code == 201
        document_id = created.json()["document_id"]
        version = client.post(
            "/api/p0/versions",
            json={"document_id": document_id, "version_number": "00.00.01", "content": "Unapproved draft secret"},
            headers=librarian_headers,
        )
        assert version.status_code == 201

        effective = client.get(f"/api/p0/documents/{document_id}/content", headers=reporter_headers)
        assert effective.status_code == 404
        denied_draft = client.get(f"/api/p0/documents/{document_id}/content?include_draft=true", headers=reporter_headers)
        assert denied_draft.status_code == 403
        allowed_draft = client.get(f"/api/p0/documents/{document_id}/content?include_draft=true", headers=librarian_headers)
        assert allowed_draft.status_code == 200
        assert allowed_draft.json()["content"] == "Unapproved draft secret"

    def test_proposal_only_can_read_catalogue_and_published_content_but_not_drafts_or_save(self, client, librarian_headers, proposal_only_headers):
        draft = client.put(
            "/api/p0/documents/DOC-006/content",
            json={"content": "Proposal-only must not read this draft", "change_summary": "test"},
            headers=librarian_headers,
        )
        assert draft.status_code == 200

        listed = client.get("/api/p0/documents", headers=proposal_only_headers)
        assert listed.status_code == 200
        assert any(item["document_id"] == "DOC-006" for item in listed.json())

        detail = client.get("/api/p0/documents/DOC-006", headers=proposal_only_headers)
        assert detail.status_code == 200
        assert detail.json()["document_id"] == "DOC-006"

        published = client.get("/api/p0/documents/DOC-006/content", headers=proposal_only_headers)
        assert published.status_code == 200
        assert published.json()["state"] == "published"
        assert published.json()["content"] != "Proposal-only must not read this draft"

        hidden_draft = client.get(
            "/api/p0/documents/DOC-006/content?include_draft=true",
            headers=proposal_only_headers,
        )
        assert hidden_draft.status_code == 403

        saved = client.put(
            "/api/p0/documents/DOC-006/content",
            json={"content": "Unauthorized save", "change_summary": "test"},
            headers=proposal_only_headers,
        )
        assert saved.status_code == 403

    def test_versions_endpoint_hides_unpublished_content_from_readers(self, client, librarian_headers, reporter_headers, proposal_only_headers):
        marker = "Unpublished version must remain restricted"
        draft = client.put(
            "/api/p0/documents/DOC-006/content",
            json={"content": marker, "change_summary": "version-list visibility test"},
            headers=librarian_headers,
        )
        assert draft.status_code == 200
        draft_id = draft.json()["version_id"]

        for headers in (reporter_headers, proposal_only_headers):
            published_only = client.get("/api/p0/documents/DOC-006/versions", headers=headers)
            assert published_only.status_code == 200, published_only.text
            assert draft_id not in {item["version_id"] for item in published_only.json()}
            assert all(item["state"] == "published" for item in published_only.json())
            denied = client.get(
                "/api/p0/documents/DOC-006/versions?include_draft=true",
                headers=headers,
            )
            assert denied.status_code == 403

        editor_versions = client.get(
            "/api/p0/documents/DOC-006/versions?include_draft=true",
            headers=librarian_headers,
        )
        assert editor_versions.status_code == 200, editor_versions.text
        assert draft_id in {item["version_id"] for item in editor_versions.json()}
        assert any(marker in item["content"] for item in editor_versions.json())

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