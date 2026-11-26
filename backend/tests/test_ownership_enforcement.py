"""The same ownership rule must hold on every path that can change a manual.

Change requests were gated first; document-version approval/publishing, document
proposals and change-request redirect were not, so a manual could still be
approved or published by a role that is neither its owner nor the approver.
"""
import uuid

import pytest

APPROVER = {"X-Role": "head_quality", "X-Actor": "u-quality"}
ACCOUNTABLE = {"X-Role": "accountable_manager", "X-Actor": "u-accountable"}
SECURITY_OWNER = {"X-Role": "head_security", "X-Actor": "u-security"}
CONTROLLER = {"X-Role": "librarian", "X-Actor": "u-lib"}
ADMIN = {"X-Role": "system_admin", "X-Actor": "admin"}

# DOC-006 is the security manual: owner head_security, approver head_quality.
MANUAL_DOC = "DOC-006"
# DOC-002 is the safety manual: used for version-state tests so their drafts do
# not make the DOC-006 proposals look stale (a proposal must be based on the
# document's latest version).
VERSION_DOC = "DOC-002"


def _reviewable_version(client):
    """A fresh DOC-006 version sitting in in_review, so any transition is legal."""
    minor = uuid.uuid4().int % 90 + 10
    patch = uuid.uuid4().int % 90 + 10
    created = client.post(
        "/api/p0/versions",
        json={
            "document_id": VERSION_DOC,
            "version_number": f"99.{minor:02d}.{patch:02d}",
            "content": "Ownership enforcement probe",
        },
        headers=ADMIN,
    )
    assert created.status_code == 201, created.text
    version_id = created.json()["version_id"]

    submitted = client.patch(
        f"/api/p0/versions/{version_id}/state?state=in_review", headers=ADMIN
    )
    assert submitted.status_code == 200, submitted.text
    return version_id


# --- G1: document-version approval and publishing ---------------------------

def test_version_approval_authority_blocks_non_approver_on_a_manual(client):
    version_id = _reviewable_version(client)

    response = client.patch(
        f"/api/p0/versions/{version_id}/state?state=approved", headers=ACCOUNTABLE
    )

    assert response.status_code == 403, response.text
    assert "head_quality" in response.json()["detail"]


@pytest.mark.parametrize("headers", [ACCOUNTABLE, APPROVER])
def test_version_publish_belongs_to_the_document_controller(client, headers):
    """Neither the approver nor the accountable manager may publish a manual."""
    version_id = _reviewable_version(client)
    approved = client.patch(
        f"/api/p0/versions/{version_id}/state?state=approved", headers=APPROVER
    )
    assert approved.status_code == 200, approved.text

    response = client.patch(
        f"/api/p0/versions/{version_id}/state?state=published", headers=headers
    )

    assert response.status_code == 403, response.text


def test_document_controller_is_the_publisher():
    from app import rbac

    publishers = {r for r, p in rbac.ROLE_PERMISSIONS.items() if "document:publish" in p}
    assert publishers == {"librarian", "system_admin"}
    approvers = {r for r, p in rbac.ROLE_PERMISSIONS.items() if "document:approve" in p}
    assert "head_quality" in approvers
    assert "head_quality" not in publishers


def test_version_approval_is_allowed_for_the_approver(client):
    version_id = _reviewable_version(client)

    response = client.patch(
        f"/api/p0/versions/{version_id}/state?state=approved", headers=APPROVER
    )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "approved"


# --- G2: document proposals --------------------------------------------------

def _reset_manual(doc_id=MANUAL_DOC):
    """Drop draft versions other test modules left behind.

    A proposal must be based on the document's latest version, so a stray draft
    from another module would make every proposal here look stale.
    """
    import os
    import sqlite3

    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        row = conn.execute(
            "SELECT version_id FROM document_versions "
            "WHERE document_id = ? AND state = 'published' "
            "ORDER BY created_at DESC LIMIT 1",
            (doc_id,),
        ).fetchone()
        if row:
            conn.execute(
                "DELETE FROM document_versions WHERE document_id = ? AND state != 'published'",
                (doc_id,),
            )
            conn.execute(
                "UPDATE documents SET current_version_id = ? WHERE document_id = ?",
                (row[0], doc_id),
            )
            conn.commit()
    finally:
        conn.close()


def _submitted_proposal(client):
    _reset_manual()
    created = client.post(
        f"/api/p2/documents/{MANUAL_DOC}/proposals",
        json={
            "target_ref": "4.2",
            "proposed_text": f"Access control revision {uuid.uuid4().hex[:8]}",
            "rationale": "Ownership coverage for the proposal workflow.",
            "severity": "minor",
        },
        headers=ADMIN,
    )
    assert created.status_code in (200, 201), created.text
    proposal_id = created.json()["proposal_id"]

    submitted = client.patch(
        f"/api/p2/proposals/{proposal_id}",
        json={"status": "submitted"},
        headers=ADMIN,
    )
    assert submitted.status_code == 200, submitted.text
    return proposal_id


def test_proposal_review_requires_the_owner(client):
    proposal_id = _submitted_proposal(client)

    response = client.patch(
        f"/api/p2/proposals/{proposal_id}",
        json={"status": "under_review"},
        headers=APPROVER,
    )

    assert response.status_code == 403, response.text
    assert "head_security" in response.json()["detail"]


def test_proposal_approval_requires_the_approver_role(client):
    proposal_id = _submitted_proposal(client)

    response = client.patch(
        f"/api/p2/proposals/{proposal_id}",
        json={"status": "approved", "disposition": "Approved by the wrong role"},
        headers=ACCOUNTABLE,
    )

    assert response.status_code == 403, response.text
    assert "head_quality" in response.json()["detail"]


def _approved_proposal(client):
    proposal_id = _submitted_proposal(client)
    reviewed = client.patch(
        f"/api/p2/proposals/{proposal_id}",
        json={"status": "under_review"},
        headers=SECURITY_OWNER,
    )
    assert reviewed.status_code == 200, reviewed.text
    approved = client.patch(
        f"/api/p2/proposals/{proposal_id}",
        json={"status": "approved", "disposition": "Approved"},
        headers=APPROVER,
    )
    assert approved.status_code == 200, approved.text
    return proposal_id


@pytest.mark.parametrize("headers", [ACCOUNTABLE, APPROVER])
def test_proposal_apply_belongs_to_the_document_controller(client, headers):
    """Approval is the Head of Quality's; applying (publishing) is the controller's."""
    proposal_id = _approved_proposal(client)

    response = client.post(f"/api/p2/proposals/{proposal_id}/apply", headers=headers)

    assert response.status_code == 403, response.text


def test_proposal_apply_succeeds_for_the_document_controller(client):
    proposal_id = _approved_proposal(client)

    response = client.post(f"/api/p2/proposals/{proposal_id}/apply", headers=CONTROLLER)

    assert response.status_code == 200, response.text


# --- G4: change-request redirect ---------------------------------------------

def _under_review_change_request(client):
    _reset_manual()
    created = client.post(
        "/api/p1/change-requests",
        json={
            "document_id": MANUAL_DOC,
            "title": f"Redirect coverage {uuid.uuid4().hex[:8]}",
            "description": "Ensure redirect honours manual authority.",
            "change_type": "minor",
        },
        headers=ADMIN,
    )
    assert created.status_code == 201, created.text
    cr_id = created.json()["cr_id"]

    submitted = client.post(f"/api/p1/change-requests/{cr_id}/submit", headers=ADMIN)
    assert submitted.status_code == 200, submitted.text

    reviewed = client.post(f"/api/p1/change-requests/{cr_id}/review", headers=SECURITY_OWNER)
    assert reviewed.status_code == 200, reviewed.text
    return cr_id


def test_redirect_requires_the_approver_role(client):
    cr_id = _under_review_change_request(client)

    response = client.post(
        f"/api/p1/change-requests/{cr_id}/redirect",
        json={"rejection_reason": "Rework requested"},
        headers=SECURITY_OWNER,
    )

    assert response.status_code == 403, response.text


def test_redirect_is_allowed_for_the_approver(client):
    cr_id = _under_review_change_request(client)

    response = client.post(
        f"/api/p1/change-requests/{cr_id}/redirect",
        json={"rejection_reason": "Rework requested"},
        headers=APPROVER,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "open"


# --- G3: direct content writes on an owned manual ----------------------------

def test_direct_content_write_on_owned_manual_is_refused(client):
    response = client.put(
        f"/api/p0/documents/{MANUAL_DOC}/content",
        json={"content": "Written straight into the manual", "change_summary": "bypass"},
        headers=CONTROLLER,
    )

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert "document proposal" in detail
    assert "head_security" in detail


def test_new_version_on_owned_manual_is_refused(client):
    response = client.post(
        "/api/p0/versions",
        json={
            "document_id": MANUAL_DOC,
            "version_number": "98.01.01",
            "content": "Draft created outside the proposal workflow",
        },
        headers=CONTROLLER,
    )

    assert response.status_code == 409, response.text
    assert "document proposal" in response.json()["detail"]


def test_direct_write_still_allowed_outside_the_ownership_scheme(client):
    """Documents with no owner keep the existing document:update behaviour."""
    import sqlite3
    import os

    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        row = conn.execute(
            "SELECT document_id FROM documents "
            "WHERE (manual_owner_role IS NULL OR manual_owner_role = '') "
            "AND document_category NOT IN ('roc_ops_spec', 'oem_publication') "
            "ORDER BY document_id LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        pytest.skip("no unowned, editable document in the seed data")

    response = client.put(
        f"/api/p0/documents/{row[0]}/content",
        json={"content": "Ordinary edit", "change_summary": "ordinary"},
        headers=CONTROLLER,
    )

    assert response.status_code == 200, response.text


# --- System publication on approval -----------------------------------------

def _draft_in_review(client, doc_id):
    import uuid as _uuid

    created = client.post(
        "/api/p0/versions",
        json={
            "document_id": doc_id,
            "version_number": f"97.{_uuid.uuid4().int % 90 + 10:02d}.{_uuid.uuid4().int % 90 + 10:02d}",
            "content": "system publication probe",
        },
        headers=ADMIN,
    )
    assert created.status_code == 201, created.text
    version_id = created.json()["version_id"]
    submitted = client.patch(
        f"/api/p0/versions/{version_id}/state?state=in_review", headers=ADMIN
    )
    assert submitted.status_code == 200, submitted.text
    return version_id


def test_approving_a_non_kcaa_manual_publishes_it_as_the_system(client):
    """DOC-004 is the training manual: owned, but no KCAA approval gate."""
    version_id = _draft_in_review(client, "DOC-004")

    response = client.patch(
        f"/api/p0/versions/{version_id}/state?state=approved", headers=APPROVER
    )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "published"
    assert response.json()["published_at"]


def test_approval_does_not_publish_documents_outside_the_scheme(client):
    """DOC-010 is a form with no owner: the controller still publishes it."""
    version_id = _draft_in_review(client, "DOC-010")

    response = client.patch(
        f"/api/p0/versions/{version_id}/state?state=approved", headers=APPROVER
    )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "approved"
    assert not response.json()["published_at"]
