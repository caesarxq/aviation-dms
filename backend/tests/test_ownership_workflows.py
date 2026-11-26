"""Ownership and departmental-leadership rules.

Two rules are enforced here:

- a controlled manual is reviewed by the role that owns it, and only the Head of
  Quality approves, rejects, and publishes change requests;
- a department's audit findings are closed by that department's head, and an
  unrecognised department fails closed instead of skipping the gate.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app import rbac
from app.manual_authority import can_approve, can_review


# --- permission matrix -------------------------------------------------------

def test_every_manual_owner_can_raise_and_review_change_requests():
    for role in ("head_quality", "head_safety", "head_security", "head_operations",
                 "head_training", "head_maintenance"):
        assert rbac.has_permission(role, "document:propose"), role
        assert rbac.has_permission(role, "change_request:create"), role
        assert rbac.has_permission(role, "change_request:review"), role


def test_only_quality_and_the_accountable_manager_approve_change_requests():
    holders = {role for role, perms in rbac.ROLE_PERMISSIONS.items()
               if "change_request:approve" in perms}
    # The accountable manager approves the quality manual only; every other
    # manual is approved by the Head of Quality (enforced per document).
    assert holders == {"head_quality", "accountable_manager", "system_admin"}


def test_head_operations_leads_its_department_findings():
    for permission in ("audit_finding:read", "audit_finding:create",
                       "audit_finding:update", "audit_finding:close"):
        assert rbac.has_permission("head_operations", permission), permission


# --- ownership decisions -----------------------------------------------------

def test_review_requires_the_manual_owner():
    authority = {"owner_role": "head_security", "approver_role": "head_quality"}

    assert can_review("head_security", authority) is True
    assert can_review("head_quality", authority) is False
    assert can_review("system_admin", authority) is True


def test_approval_requires_the_approver_role():
    authority = {"owner_role": "head_security", "approver_role": "head_quality"}

    assert can_approve("head_quality", authority) is True
    assert can_approve("head_security", authority) is False
    assert can_approve("system_admin", authority) is True


def test_documents_outside_the_ownership_scheme_are_unconstrained():
    assert can_review("librarian", {}) is True
    assert can_approve("librarian", {}) is True


# --- department closure gate -------------------------------------------------

def _headers(role, actor):
    return {"X-Role": role, "X-Actor": actor}


def _create_finding(client, headers, department=None):
    report = client.post(
        "/api/p3/audit-reports",
        json={
            "audit_number": f"OWN-{uuid.uuid4().hex[:8]}",
            "audit_date": datetime.now(timezone.utc).date().isoformat(),
            "auditor_id": "u-auditor",
            "auditee_id": "u-admin",
        },
        headers=headers,
    )
    assert report.status_code == 201, report.text

    payload = {
        "audit_id": report.json()["audit_id"],
        "finding_number": "1",
        "area": "Operations",
        "level": 1,
        "title": f"Ownership finding {uuid.uuid4().hex[:8]}",
        "description": "Department closure gate coverage.",
    }
    if department is not None:
        payload["department"] = department
    response = client.post("/api/p3/audit-findings", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["finding_id"]


def _advance_to_in_progress(client, finding_id, headers):
    response = client.patch(
        f"/api/p3/audit-findings/{finding_id}", json={"status": "in_progress"}, headers=headers
    )
    assert response.status_code == 200, response.text


def test_operations_head_closes_an_operations_finding(client):
    admin = _headers("system_admin", "admin")
    finding_id = _create_finding(client, admin, department="operations")
    _advance_to_in_progress(client, finding_id, admin)

    response = client.patch(
        f"/api/p3/audit-findings/{finding_id}",
        json={"status": "closed", "closure_evidence": "Corrective action verified"},
        headers=_headers("head_operations", "u-ops"),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "closed"


def test_quality_head_cannot_close_an_operations_finding(client):
    admin = _headers("system_admin", "admin")
    finding_id = _create_finding(client, admin, department="operations")
    _advance_to_in_progress(client, finding_id, admin)

    response = client.patch(
        f"/api/p3/audit-findings/{finding_id}",
        json={"status": "closed", "closure_evidence": "Attempted cross-department closure"},
        headers=_headers("head_quality", "u-quality"),
    )

    assert response.status_code == 403, response.text
    assert "head_operations" in response.json()["detail"]


def test_unmapped_department_fails_closed(client):
    admin = _headers("system_admin", "admin")
    finding_id = _create_finding(client, admin, department="unmapped-dept")
    _advance_to_in_progress(client, finding_id, admin)

    response = client.patch(
        f"/api/p3/audit-findings/{finding_id}",
        json={"status": "closed", "closure_evidence": "Should be refused"},
        headers=admin,
    )

    assert response.status_code == 409, response.text
    assert "no mapped head role" in response.json()["detail"]
