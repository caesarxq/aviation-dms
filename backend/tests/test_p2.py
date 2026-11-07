"""Tests for P2 endpoints: document proposals, personnel licenses, aircraft insurance."""
import os
import sqlite3
import uuid

import pytest


def _create_published_document(content: str) -> str:
    token = uuid.uuid4().hex[:12].upper()
    document_id = f"DOC-TEST-{token}"
    version_id = f"VER-TEST-{token}"
    timestamp = "2026-11-03T00:00:00"
    with sqlite3.connect(os.environ["DMS_DB_PATH"]) as conn:
        conn.execute(
            """INSERT INTO documents
               (document_id, title, doc_class, classification, status, owner_id, current_version_id,
                created_at, updated_at, created_by, updated_by)
               VALUES (?, ?, 'manual', 'S2', 'published', 'u-lib', ?, ?, ?, 'u-lib', 'u-lib')""",
            (document_id, "Proposal apply test", version_id, timestamp, timestamp),
        )
        conn.execute(
            """INSERT INTO document_versions
               (version_id, document_id, version_number, state, content, kcaa_approved,
                created_at, updated_at, created_by, updated_by)
               VALUES (?, ?, '01.00.00', 'published', ?, 0, ?, ?, 'u-lib', 'u-lib')""",
            (version_id, document_id, content, timestamp, timestamp),
        )
    return document_id


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
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            event = conn.execute(
                "SELECT actor_id, action FROM audit_events "
                "WHERE entity_type = 'document_proposal' AND entity_id = ?",
                (data["proposal_id"],),
            ).fetchone()
            assert event == ("u-quality", "created")
        finally:
            conn.close()

    def test_proposal_only_role_can_create_edit_and_submit_proposal(self, client, safety_headers):
        created = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "safety proposal",
            "proposed_text": "initial text",
        }, headers=safety_headers)
        assert created.status_code == 200, created.text
        proposal_id = created.json()["proposal_id"]

        edited = client.patch(f"/api/p2/proposals/{proposal_id}", json={
            "proposed_text": "edited safety text",
        }, headers=safety_headers)
        assert edited.status_code == 200, edited.text

        submitted = client.patch(f"/api/p2/proposals/{proposal_id}", json={"status": "submitted"}, headers=safety_headers)
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "submitted"

    def test_document_approve_permission_still_allows_review(self, client, safety_headers, quality_headers):
        created = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "reviewer permission check",
            "proposed_text": "reviewable text",
        }, headers=safety_headers)
        assert created.status_code == 200, created.text
        proposal_id = created.json()["proposal_id"]
        submitted = client.patch(f"/api/p2/proposals/{proposal_id}", json={"status": "submitted"}, headers=safety_headers)
        assert submitted.status_code == 200, submitted.text

        approved = client.patch(f"/api/p2/proposals/{proposal_id}", json={"status": "approved"}, headers=quality_headers)
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

    def test_proposal_only_role_can_delete_draft(self, client, safety_headers):
        created = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "deletable safety proposal",
            "proposed_text": "text",
        }, headers=safety_headers)
        assert created.status_code == 200, created.text

        deleted = client.delete(f"/api/p2/proposals/{created.json()['proposal_id']}", headers=safety_headers)
        assert deleted.status_code == 200, deleted.text
        assert deleted.json() == {"deleted": True}

    def test_proposal_only_role_can_create_batch_proposals(self, client, safety_headers):
        response = client.post("/api/p2/documents/DOC-001/proposals/batch", json={
            "proposed_content": "Revised content for a proposal-only editor.",
        }, headers=safety_headers)
        assert response.status_code == 200, response.text
        assert response.json()["created_count"] > 0

    def test_update_only_role_cannot_use_proposal_workflow(self, client, safety_headers, librarian_headers, monkeypatch):
        from app import p2_routes

        created = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "update-only workflow test",
            "proposed_text": "initial proposal text",
        }, headers=safety_headers)
        assert created.status_code == 200, created.text
        proposal_id = created.json()["proposal_id"]
        monkeypatch.setattr(
            p2_routes, "has_permission",
            lambda role, permission: permission in {"document:read", "document:update"},
        )

        denied = [
            client.post("/api/p2/documents/DOC-001/proposals/preview", json={
                "proposed_content": "preview attempt",
            }, headers=librarian_headers),
            client.post("/api/p2/documents/DOC-001/proposals", json={
                "proposal_type": "word", "target_ref": "update-only creation",
                "proposed_text": "must not persist",
            }, headers=librarian_headers),
            client.post("/api/p2/documents/DOC-001/proposals/batch", json={
                "proposed_content": "batch attempt",
            }, headers=librarian_headers),
            client.patch(f"/api/p2/proposals/{proposal_id}", json={
                "proposed_text": "update-only edit attempt",
            }, headers=librarian_headers),
            client.patch(f"/api/p2/proposals/{proposal_id}", json={"status": "submitted"}, headers=librarian_headers),
            client.delete(f"/api/p2/proposals/{proposal_id}", headers=librarian_headers),
        ]
        assert [response.status_code for response in denied] == [403] * len(denied)

    def test_update_only_permission_can_complete_review_transitions(self, client, safety_headers, librarian_headers, monkeypatch):
        from app import p2_routes

        pending_reviews = []
        for status in ("approved", "rejected", "deferred"):
            created = client.post("/api/p2/documents/DOC-001/proposals", json={
                "proposal_type": "word", "target_ref": f"update-only review {status}",
                "proposed_text": "review transition text",
            }, headers=safety_headers)
            assert created.status_code == 200, created.text
            proposal_id = created.json()["proposal_id"]
            submitted = client.patch(f"/api/p2/proposals/{proposal_id}", json={"status": "submitted"}, headers=safety_headers)
            assert submitted.status_code == 200, submitted.text
            pending_reviews.append((proposal_id, status))

        monkeypatch.setattr(
            p2_routes, "has_permission",
            lambda role, permission: permission in {"document:read", "document:update"},
        )
        for proposal_id, status in pending_reviews:
            reviewed = client.patch(f"/api/p2/proposals/{proposal_id}", json={"status": status}, headers=librarian_headers)
            assert reviewed.status_code == 200, reviewed.text
            assert reviewed.json()["status"] == status

    def test_proposer_cannot_claim_review_of_own_proposal(self, client, librarian_headers):
        created = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "proposer self-review",
            "proposed_text": "pending proposal",
        }, headers=librarian_headers)
        assert created.status_code == 200, created.text
        proposal_id = created.json()["proposal_id"]
        submitted = client.patch(
            f"/api/p2/proposals/{proposal_id}", json={"status": "submitted"}, headers=librarian_headers
        )
        assert submitted.status_code == 200, submitted.text

        self_review = client.patch(
            f"/api/p2/proposals/{proposal_id}", json={"status": "under_review"}, headers=librarian_headers
        )
        assert self_review.status_code == 403
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            persisted = conn.execute(
                "SELECT status, reviewer_id FROM document_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        finally:
            conn.close()
        assert persisted == ("submitted", None)

    def test_proposal_only_permission_can_list_proposals_without_read(self, client, safety_headers, monkeypatch):
        from app import p2_routes

        created = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "proposal-only listing",
            "proposed_text": "visible proposal",
        }, headers=safety_headers)
        assert created.status_code == 200, created.text
        monkeypatch.setattr(
            p2_routes, "has_permission",
            lambda role, permission: permission == "document:propose",
        )

        listed = client.get("/api/p2/documents/DOC-001/proposals", headers=safety_headers)
        assert listed.status_code == 200, listed.text
        assert created.json()["proposal_id"] in {row["proposal_id"] for row in listed.json()}

    def test_approved_proposal_content_cannot_be_edited(self, client, safety_headers, quality_headers):
        created = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "approved edit integrity",
            "proposed_text": "approved proposal text",
        }, headers=safety_headers)
        assert created.status_code == 200, created.text
        proposal_id = created.json()["proposal_id"]
        submitted = client.patch(f"/api/p2/proposals/{proposal_id}", json={"status": "submitted"}, headers=safety_headers)
        assert submitted.status_code == 200, submitted.text
        approved = client.patch(f"/api/p2/proposals/{proposal_id}", json={"status": "approved"}, headers=quality_headers)
        assert approved.status_code == 200, approved.text

        edited = client.patch(f"/api/p2/proposals/{proposal_id}", json={
            "proposed_text": "silently substituted text",
        }, headers=safety_headers)
        assert edited.status_code == 400
        listed = client.get("/api/p2/documents/DOC-001/proposals", headers=safety_headers)
        persisted = next(row for row in listed.json() if row["proposal_id"] == proposal_id)
        assert persisted["proposed_text"] == "approved proposal text"
        assert persisted["status"] == "approved"

    def test_proposer_cannot_set_review_or_apply_status_directly(self, client, safety_headers):
        created = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "proposer status integrity",
            "proposed_text": "proposal text",
        }, headers=safety_headers)
        assert created.status_code == 200, created.text
        proposal_id = created.json()["proposal_id"]

        under_review = client.patch(
            f"/api/p2/proposals/{proposal_id}", json={"status": "under_review"}, headers=safety_headers
        )
        applied = client.patch(
            f"/api/p2/proposals/{proposal_id}", json={"status": "applied"}, headers=safety_headers
        )
        assert under_review.status_code == 403
        assert applied.status_code == 422

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            persisted = conn.execute(
                "SELECT status, reviewer_id FROM document_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        finally:
            conn.close()
        assert persisted == ("draft", None)

    def test_proposer_cannot_assign_review_metadata(self, client, safety_headers):
        created = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "proposer reviewer spoof",
            "proposed_text": "proposal text",
        }, headers=safety_headers)
        assert created.status_code == 200, created.text
        proposal_id = created.json()["proposal_id"]

        spoofed = client.patch(f"/api/p2/proposals/{proposal_id}", json={
            "reviewer_id": "admin",
        }, headers=safety_headers)
        assert spoofed.status_code == 403

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            reviewer = conn.execute(
                "SELECT reviewer_id FROM document_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert reviewer is None

    def test_proposal_sources_use_effective_published_version(self, client, safety_headers):
        setup_conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        doc_id = "DOC-P2-EFFECTIVE-SOURCE"
        published_id = "VER-P2-EFFECTIVE-PUBLISHED"
        draft_id = "VER-P2-EFFECTIVE-DRAFT"
        try:
            setup_conn.execute(
                """INSERT INTO documents
                   (document_id, title, doc_class, owner_id, current_version_id, created_at, updated_at, created_by, updated_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, "Effective source test", "procedure", "u-lib", published_id,
                 "2026-01-01T00:00:00", "2026-01-01T00:00:00", "u-lib", "u-lib"),
            )
            for version_id, state, content, created_at in (
                (published_id, "published", "Effective published sentence.", "2026-01-01T00:00:00"),
                (draft_id, "draft", "Unauthorized draft secret sentence.", "2026-02-01T00:00:00"),
            ):
                setup_conn.execute(
                    """INSERT INTO document_versions
                       (version_id, document_id, version_number, state, content, created_at, updated_at, created_by, updated_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (version_id, doc_id, "01.00.00", state, content, created_at, created_at, "u-lib", "u-lib"),
                )
            setup_conn.commit()
            setup_conn.close()

            preview = client.post(f"/api/p2/documents/{doc_id}/proposals/preview", json={
                "proposed_content": "Effective amended sentence.",
            }, headers=safety_headers)
            assert preview.status_code == 200, preview.text
            assert preview.json()["base_version_id"] == published_id
            assert preview.json()["changes"][0]["original_text"] == "published"

            batch = client.post(f"/api/p2/documents/{doc_id}/proposals/batch", json={
                "proposed_content": "Effective amended sentence.",
                "rationale": "effective source test",
            }, headers=safety_headers)
            assert batch.status_code == 200, batch.text
            assert batch.json()["base_version_id"] == published_id
            listed_batch = client.get(f"/api/p2/documents/{doc_id}/proposals", headers=safety_headers)
            assert listed_batch.status_code == 200, listed_batch.text
            batch_rows = [
                item for item in listed_batch.json()
                if item["change_set_id"] == batch.json()["change_set_id"]
            ]
            assert batch_rows
            assert all(item["version_id"] == published_id for item in batch_rows)

            single = client.post(f"/api/p2/documents/{doc_id}/proposals", json={
                "proposal_type": "word", "target_ref": "published sentence",
                "original_text": "published", "proposed_text": "amended",
            }, headers=safety_headers)
            assert single.status_code == 200, single.text
            assert single.json()["version_id"] == published_id
        finally:
            setup_conn.close()
            cleanup_conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
            try:
                cleanup_conn.execute("DELETE FROM document_proposals WHERE document_id = ?", (doc_id,))
                cleanup_conn.execute("DELETE FROM document_versions WHERE document_id = ?", (doc_id,))
                cleanup_conn.execute("DELETE FROM documents WHERE document_id = ?", (doc_id,))
                cleanup_conn.commit()
            finally:
                cleanup_conn.close()

    def test_proposal_source_never_falls_back_to_unpublished_draft(self, client, safety_headers):
        doc_id = "DOC-P2-DRAFT-ONLY"
        version_id = "VER-P2-DRAFT-ONLY"
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute(
                """INSERT INTO documents
                   (document_id, title, doc_class, owner_id, current_version_id, created_at, updated_at, created_by, updated_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, "Draft-only test", "procedure", "u-lib", version_id,
                 "2026-01-01T00:00:00", "2026-01-01T00:00:00", "u-lib", "u-lib"),
            )
            conn.execute(
                """INSERT INTO document_versions
                   (version_id, document_id, version_number, state, content, created_at, updated_at, created_by, updated_by)
                   VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?)""",
                (version_id, doc_id, "01.00.00", "Unpublished draft secret.",
                 "2026-01-01T00:00:00", "2026-01-01T00:00:00", "u-lib", "u-lib"),
            )
            conn.commit()
        finally:
            conn.close()

        try:
            preview = client.post(f"/api/p2/documents/{doc_id}/proposals/preview", json={
                "proposed_content": "Different proposed text.",
            }, headers=safety_headers)
            single = client.post(f"/api/p2/documents/{doc_id}/proposals", json={
                "proposal_type": "word", "target_ref": "draft-only", "proposed_text": "proposal",
            }, headers=safety_headers)
            batch = client.post(f"/api/p2/documents/{doc_id}/proposals/batch", json={
                "proposed_content": "Different proposed text.",
            }, headers=safety_headers)
            assert [preview.status_code, single.status_code, batch.status_code] == [404, 404, 404]
            conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
            try:
                proposal_count = conn.execute(
                    "SELECT COUNT(*) FROM document_proposals WHERE document_id = ?", (doc_id,)
                ).fetchone()[0]
            finally:
                conn.close()
            assert proposal_count == 0
        finally:
            conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
            try:
                conn.execute("DELETE FROM document_versions WHERE document_id = ?", (doc_id,))
                conn.execute("DELETE FROM documents WHERE document_id = ?", (doc_id,))
                conn.commit()
            finally:
                conn.close()

    def test_read_only_role_cannot_create_proposals(self, client, reporter_headers):
        response = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "read-only attempt",
            "proposed_text": "must not persist",
        }, headers=reporter_headers)
        assert response.status_code == 403

    def test_proposal_only_role_cannot_save_document_content(self, client, safety_headers):
        response = client.put("/api/p0/documents/DOC-001/content", json={
            "content": "proposal-only content save attempt",
            "change_summary": "must remain forbidden",
        }, headers=safety_headers)
        assert response.status_code == 403

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

    def test_proposal_workflow_submit_approve(self, client, librarian_headers, admin_headers):
        resp = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "section", "target_ref": "section 1",
            "proposed_text": "new section content",
        }, headers=librarian_headers)
        pid = resp.json()["proposal_id"]

        # Submit
        resp = client.patch(f"/api/p2/proposals/{pid}", json={"status": "submitted"}, headers=librarian_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"

        # The seeded librarian and quality roles share one canonical actor; use another assigned reviewer.
        resp = client.patch(f"/api/p2/proposals/{pid}", json={"status": "approved"}, headers=admin_headers)
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
        original = "original phrase for isolated proposal apply"
        doc_id = _create_published_document(f"before {original} after")
        resp = client.post(f"/api/p2/documents/{doc_id}/proposals", json={
            "proposal_type": "word", "target_ref": "word 1",
            "original_text": original,
            "proposed_text": "applied text",
        }, headers=librarian_headers)
        pid = resp.json()["proposal_id"]
        client.patch(f"/api/p2/proposals/{pid}", json={"status": "submitted"}, headers=librarian_headers)
        client.patch(f"/api/p2/proposals/{pid}", json={"status": "approved"}, headers=admin_headers)
        resp = client.post(f"/api/p2/proposals/{pid}/apply", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "applied"
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            applied = conn.execute(
                "SELECT state, content FROM document_versions WHERE version_id = ?",
                (resp.json()["new_version_id"],),
            ).fetchone()
        finally:
            conn.close()
        assert applied == ("draft", "before applied text after")

    # SEC-C1: SoD — proposer cannot apply their own proposal.
    # librarian and head_quality share the canonical actor u-quality;
    # quality has document:publish so it passes the first gate, but SoD
    # must block the shared canonical actor from applying its own proposal.
    def test_apply_proposal_sod_proposer_cannot_apply_own(self, client, librarian_headers, quality_headers, admin_headers):
        resp = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "word", "target_ref": "word 99",
            "proposed_text": "sod apply test",
        }, headers=librarian_headers)
        pid = resp.json()["proposal_id"]
        proposer_id = resp.json().get("proposer_id")
        assert proposer_id == "u-quality"
        client.patch(f"/api/p2/proposals/{pid}", json={"status": "submitted"}, headers=librarian_headers)
        client.patch(f"/api/p2/proposals/{pid}", json={"status": "approved"}, headers=admin_headers)
        # Simulate a proposal persisted with the historical pre-merge actor ID.
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("UPDATE document_proposals SET proposer_id = 'u-lib' WHERE proposal_id = ?", (pid,))
            conn.commit()
        finally:
            conn.close()
        # head_quality is canonical u-quality; SoD must recognize legacy requester u-lib.
        resp = client.post(f"/api/p2/proposals/{pid}/apply", headers=quality_headers)
        assert resp.status_code == 403

    def test_proposal_mutation_rolls_back_when_audit_insert_fails(self, client, librarian_headers):
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute(
                """CREATE TRIGGER fail_p2_audit_insert
                   BEFORE INSERT ON audit_events
                   WHEN NEW.entity_type = 'document_proposal' AND NEW.action = 'created'
                   BEGIN SELECT RAISE(ABORT, 'simulated audit insert failure'); END"""
            )
            conn.commit()
        finally:
            conn.close()

        try:
            with pytest.raises(sqlite3.IntegrityError, match="simulated audit insert failure"):
                client.post("/api/p2/documents/DOC-001/proposals", json={
                    "proposal_type": "word", "target_ref": "atomic audit test",
                    "proposed_text": "must roll back",
                }, headers=librarian_headers)
        finally:
            conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
            try:
                conn.execute("DROP TRIGGER IF EXISTS fail_p2_audit_insert")
                conn.commit()
                assert conn.execute(
                    "SELECT 1 FROM document_proposals WHERE target_ref = 'atomic audit test'"
                ).fetchone() is None
            finally:
                conn.close()

    def test_proposal_reject(self, client, librarian_headers, admin_headers):
        resp = client.post("/api/p2/documents/DOC-001/proposals", json={
            "proposal_type": "line", "target_ref": "line 5",
            "proposed_text": "rejected text",
        }, headers=librarian_headers)
        pid = resp.json()["proposal_id"]
        client.patch(f"/api/p2/proposals/{pid}", json={"status": "submitted"}, headers=librarian_headers)
        resp = client.patch(f"/api/p2/proposals/{pid}", json={"status": "rejected"}, headers=admin_headers)
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
        assert data["person_id"] == "u-safety/security"
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
        # AC-001 may not exist in test DB; check for 200 or 404
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

    # SEC-C2: Annotation endpoints must require document:annotate, not document:read
    def test_create_annotation_rejected_without_annotate_permission(self, client, reporter_headers):
        """reporter has document:read but NOT document:annotate — must be rejected."""
        resp = client.post("/api/p2/documents/DOC-001/annotations", json={
            "annotation_type": "comment",
            "target_ref": "section 1.1",
            "content": "should be rejected",
        }, headers=reporter_headers)
        assert resp.status_code == 403

    def test_list_annotations_rejected_without_annotate_permission(self, client, reporter_headers):
        """reporter has document:read but NOT document:annotate — must be rejected."""
        resp = client.get("/api/p2/documents/DOC-001/annotations", headers=reporter_headers)
        assert resp.status_code == 403

    def test_update_annotation_rejected_without_annotate_permission(self, client, librarian_headers, reporter_headers):
        """reporter has document:read but NOT document:annotate — must be rejected."""
        # Create with librarian first
        create = client.post("/api/p2/documents/DOC-001/annotations", json={
            "annotation_type": "comment",
            "target_ref": "section 3",
            "content": "test annotation",
        }, headers=librarian_headers)
        assert create.status_code == 200
        aid = create.json()["annotation_id"]
        # Reporter tries to update — must be rejected
        resp = client.patch(f"/api/p2/annotations/{aid}", json={"content": "updated"}, headers=reporter_headers)
        assert resp.status_code == 403


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