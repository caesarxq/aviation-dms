import sqlite3
import uuid

import pytest


def _create_report(client, headers):
    response = client.post(
        "/api/p3/audit-reports",
        json={"audit_number": f"EXT-{uuid.uuid4().hex[:10]}", "audit_date": "2026-11-02", "scope": "External audit",
              "auditor_id": "u-auditor", "auditee_id": "u-admin"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["audit_id"]


def _create_finding(client, headers):
    audit_id = _create_report(client, headers)
    response = client.post(
        "/api/p3/audit-findings",
        json={"audit_id": audit_id, "finding_number": "1", "area": "Safety", "level": 2,
              "title": "Finding", "description": "Evidence of a control gap"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["finding_id"]


def test_p3_rejects_invalid_payload_status_and_unbounded_pagination(client, admin_headers):
    missing_auditor = client.post("/api/p3/audit-reports", json={
        "audit_number": "EXT-MISSING-AUDITOR", "audit_date": "2026-11-02", "auditee_id": "u-admin",
    }, headers=admin_headers)
    assert missing_auditor.status_code == 422
    invalid_auditor = client.post("/api/p3/audit-reports", json={
        "audit_number": "EXT-INVALID-AUDITOR", "audit_date": "2026-11-02", "auditor_id": "u-admin", "auditee_id": "u-reporter",
    }, headers=admin_headers)
    assert invalid_auditor.status_code == 403
    same_participant = client.post("/api/p3/audit-reports", json={
        "audit_number": "EXT-SAME-PARTICIPANT", "audit_date": "2026-11-02", "auditor_id": "u-auditor", "auditee_id": "u-auditor",
    }, headers=admin_headers)
    assert same_participant.status_code == 422

    assert client.post("/api/p3/audit-reports", json={"audit_number": "EXT-1", "audit_date": "2026-11-02", "auditor_id": "u-auditor", "auditee_id": "u-admin", "status": "bogus"}, headers=admin_headers).status_code == 422
    assert client.post("/api/p3/audit-findings", json={"audit_id": "x", "finding_number": "1", "area": "Safety", "level": 5, "title": "Bad", "description": "Bad"}, headers=admin_headers).status_code == 422
    assert client.post("/api/p3/audit-findings", json={"audit_id": "x"}, headers=admin_headers).status_code == 422
    assert client.get("/api/p3/audit-findings?status=unknown", headers=admin_headers).status_code == 422
    assert client.get("/api/p3/audit-findings?limit=1000", headers=admin_headers).status_code == 422
    assert client.get("/api/p3/audit-reports?limit=-1", headers=admin_headers).status_code == 422


def test_p3_finding_close_requires_separate_permission_valid_transition_and_evidence(client, admin_headers):
    finding_id = _create_finding(client, admin_headers)
    head_quality = {"X-Role": "head_quality", "X-Actor": "u-quality"}

    # Close permission is independent of the broader finding update permission.
    denied = client.patch(
        f"/api/p3/audit-findings/{finding_id}", json={"status": "closed", "closure_evidence": "verified"}, headers=head_quality
    )
    assert denied.status_code == 403

    invalid_transition = client.patch(
        f"/api/p3/audit-findings/{finding_id}", json={"status": "closed", "closure_evidence": "verified"}, headers=admin_headers
    )
    assert invalid_transition.status_code == 409

    in_progress = client.patch(
        f"/api/p3/audit-findings/{finding_id}", json={"status": "in_progress"}, headers=admin_headers
    )
    assert in_progress.status_code == 200
    missing_evidence = client.patch(
        f"/api/p3/audit-findings/{finding_id}", json={"status": "closed"}, headers=admin_headers
    )
    assert missing_evidence.status_code == 422

    closed = client.patch(
        f"/api/p3/audit-findings/{finding_id}", json={"status": "closed", "closure_evidence": "Independent verification completed"}, headers=admin_headers
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_by"] == "u-admin"
    assert closed.json()["closure_evidence"] == "Independent verification completed"

    reopened = client.patch(
        f"/api/p3/audit-findings/{finding_id}", json={"status": "open"}, headers=admin_headers
    )
    assert reopened.status_code == 409

    import os
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        events = conn.execute(
            "SELECT action FROM audit_events WHERE entity_type='audit_finding' AND entity_id=? ORDER BY timestamp, rowid", (finding_id,)
        ).fetchall()
        assert [event[0] for event in events] == ["created", "updated", "updated"]
    finally:
        conn.close()


def test_p3_read_permissions_and_atomic_audit_events(client, admin_headers):
    audit_id = _create_report(client, admin_headers)
    independent_auditor = {"X-Role": "independent_auditor", "X-Actor": "u-auditor"}
    report_list = client.get("/api/p3/audit-reports", headers=independent_auditor)
    assert report_list.status_code == 200
    assert any(row["audit_id"] == audit_id for row in report_list.json())
    forbidden_create = client.post("/api/p3/audit-reports", json={"audit_number": "NOPE", "audit_date": "2026-11-02", "auditor_id": "u-auditor", "auditee_id": "u-admin"}, headers=independent_auditor)
    assert forbidden_create.status_code == 403

    finding_id = _create_finding(client, admin_headers)
    findings = client.get("/api/p3/audit-findings", headers=independent_auditor)
    assert findings.status_code == 200
    assert any(row["finding_id"] == finding_id for row in findings.json())
    forbidden_finding_create = client.post(
        "/api/p3/audit-findings",
        json={"audit_id": audit_id, "finding_number": "X", "area": "Safety", "level": 2, "title": "Finding", "description": "Description"},
        headers=independent_auditor,
    )
    assert forbidden_finding_create.status_code == 403
    conn = sqlite3.connect(__import__("os").environ["DMS_DB_PATH"])
    try:
        events = conn.execute(
            "SELECT action FROM audit_events WHERE entity_type = 'audit_finding' AND entity_id = ? ORDER BY timestamp", (finding_id,)
        ).fetchall()
        assert [row[0] for row in events] == ["created"]
    finally:
        conn.close()


def test_p3_finding_creation_requires_existing_report_and_status_filter_is_bounded(client, admin_headers):
    response = client.post(
        "/api/p3/audit-findings",
        json={"audit_id": "MISSING", "finding_number": "1", "area": "Safety", "level": 1,
              "title": "Finding", "description": "Description"},
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert client.get("/api/p3/audit-findings?offset=100001", headers=admin_headers).status_code == 422


def test_p3_audit_finding_search_and_status_filters_apply_before_pagination(client, admin_headers):
    audit_id = _create_report(client, admin_headers)
    for index in range(50):
        response = client.post(
            "/api/p3/audit-findings",
            json={"audit_id": audit_id, "finding_number": f"{index:03d}", "area": "Safety", "level": 2,
                  "title": f"Routine finding {index:03d}", "description": "Routine evidence"},
            headers=admin_headers,
        )
        assert response.status_code == 201, response.text
    target = client.post(
        "/api/p3/audit-findings",
        json={"audit_id": audit_id, "finding_number": "050", "area": "Security", "level": 3,
              "title": "Unique perimeter control gap", "description": "Evidence of a perimeter issue"},
        headers=admin_headers,
    )
    assert target.status_code == 201, target.text
    target_id = target.json()["finding_id"]
    transitioned = client.patch(
        f"/api/p3/audit-findings/{target_id}", json={"status": "in_progress"}, headers=admin_headers
    )
    assert transitioned.status_code == 200, transitioned.text

    by_status = client.get("/api/p3/audit-findings?status=in_progress&limit=1&offset=0", headers=admin_headers)
    assert by_status.status_code == 200, by_status.text
    assert isinstance(by_status.json(), list)
    assert [row["finding_id"] for row in by_status.json()] == [target_id]

    by_search = client.get("/api/p3/audit-findings?search=perimeter%20control&limit=1&offset=0", headers=admin_headers)
    assert by_search.status_code == 200, by_search.text
    assert isinstance(by_search.json(), list)
    assert [row["finding_id"] for row in by_search.json()] == [target_id]


def test_p3_audit_findings_with_equal_numbers_are_stable_across_pages(client, admin_headers):
    import os

    audit_id = _create_report(client, admin_headers)
    created_ids = []
    for index in range(4):
        response = client.post(
            "/api/p3/audit-findings",
            json={"audit_id": audit_id, "finding_number": "7", "area": "Safety", "level": 2,
                  "title": f"Tied finding {index}", "description": "Equal finding number"},
            headers=admin_headers,
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["finding_id"])

    # Keep insertion order opposite to the required finding_id ordering so the
    # test deterministically exposes pagination ties in the current query.
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        for old_id, new_id in zip(created_ids, ("AF-TIE-D", "AF-TIE-C", "AF-TIE-B", "AF-TIE-A")):
            conn.execute("UPDATE audit_findings SET finding_id = ? WHERE finding_id = ?", (new_id, old_id))
        conn.commit()
    finally:
        conn.close()

    first_page = client.get("/api/p3/audit-findings?audit_id={}&limit=2&offset=0".format(audit_id), headers=admin_headers)
    second_page = client.get("/api/p3/audit-findings?audit_id={}&limit=2&offset=2".format(audit_id), headers=admin_headers)
    assert first_page.status_code == second_page.status_code == 200
    assert [row["finding_id"] for row in first_page.json() + second_page.json()] == [
        "AF-TIE-A", "AF-TIE-B", "AF-TIE-C", "AF-TIE-D"
    ]


def test_p3_audit_finding_search_query_is_bounded(client, admin_headers):
    response = client.get(f"/api/p3/audit-findings?search={'x' * 201}", headers=admin_headers)
    assert response.status_code == 422


def test_p3_get_audit_finding_by_id(client, admin_headers):
    finding_id = _create_finding(client, admin_headers)
    detail = client.get(f"/api/p3/audit-findings/{finding_id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["finding_id"] == finding_id
    assert client.get("/api/p3/audit-findings/AF-MISSING", headers=admin_headers).status_code == 404
