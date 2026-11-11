import asyncio
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from app import p3_routes


@pytest.fixture(autouse=True)
def _configure_p3_evidence_safeguards(monkeypatch):
    monkeypatch.setenv("DMS_UPLOAD_QUOTA_SCOPE", "system")
    monkeypatch.setenv("DMS_UPLOAD_STORAGE_QUOTA_BYTES", str(100 * 1024 * 1024))
    monkeypatch.setenv("DMS_CLAMD_HOST", "127.0.0.1")
    monkeypatch.setenv("DMS_CLAMD_PORT", "3310")
    monkeypatch.setenv("DMS_CLAMD_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DMS_CLAMD_MAX_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DMS_AUDIT_EVIDENCE_MAX_BYTES", str(10 * 1024 * 1024))
    monkeypatch.setenv("DMS_P3_IMPORT_BODY_MAX_BYTES", str(50 * 1024 * 1024))

    async def clean_scan(payload, policy):
        return None

    monkeypatch.setattr(p3_routes, "scan_upload_bytes", clean_scan)


def _create_report(client, headers):
    response = client.post(
        "/api/p3/audit-reports",
        json={"audit_number": f"EXT-{uuid.uuid4().hex[:10]}", "audit_date": datetime.now(timezone.utc).date().isoformat(), "scope": "External audit",
              "auditor_id": "u-auditor", "auditee_id": "u-admin"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["audit_id"]


def test_cancelled_audit_evidence_copy_keeps_io_slot_until_worker_finishes(tmp_path, monkeypatch):
    import io
    from app import p3_routes

    snapshot = io.BytesIO(b"bounded evidence")
    started = threading.Event()
    finished = threading.Event()

    def slow_copy(*_args):
        started.set()
        time.sleep(0.2)
        finished.set()
        return snapshot, "a" * 64, snapshot.getbuffer().nbytes

    monkeypatch.setattr(p3_routes, "_copy_audit_evidence_snapshot", slow_copy)

    async def cancel_copy():
        task = asyncio.create_task(p3_routes._snapshot_audit_evidence(tmp_path / "source.pdf"))
        deadline = asyncio.get_running_loop().time() + 1
        while not started.is_set() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.005)
        assert started.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)
        assert finished.is_set()
        assert snapshot.closed

    asyncio.run(cancel_copy())


def test_p3_import_body_limit_runs_before_pydantic_body_parsing(client, admin_headers, monkeypatch):
    monkeypatch.setenv("DMS_P3_IMPORT_BODY_MAX_BYTES", "1")

    response = client.post(
        "/api/p3/audit-report-imports",
        content=b"{}",
        headers={**admin_headers, "Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_p3_import_body_guard_fails_closed_when_limit_is_missing(client, admin_headers, monkeypatch):
    monkeypatch.delenv("DMS_P3_IMPORT_BODY_MAX_BYTES", raising=False)

    response = client.post(
        "/api/p3/audit-report-imports",
        content=b"{}",
        headers={**admin_headers, "Content-Type": "application/json"},
    )

    assert response.status_code == 503


def test_audit_report_search_and_pagination_are_stable(client, admin_headers):
    import os

    audit_ids = ["AUD-PAGEKEY-A", "AUD-PAGEKEY-B", "AUD-PAGEKEY-C"]
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        for suffix, audit_id in reversed(list(zip("ABC", audit_ids))):
            conn.execute(
                """INSERT INTO audit_reports
                   (audit_id, audit_number, audit_date, auditor_id, auditee_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (audit_id, f"PAGEKEY-{suffix}", "2026-01-01", "u-auditor", "u-admin", "open", "2026-01-01", "2026-01-01"),
            )
        conn.execute(
            """INSERT INTO audit_reports
               (audit_id, audit_number, audit_date, auditor_id, auditee_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("AUD-UNRELATED", "OTHER-001", "2026-01-02", "u-auditor", "u-admin", "open", "2026-01-02", "2026-01-02"),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        first = client.get(
            "/api/p3/audit-reports",
            params={"search": "PAGEKEY", "limit": 2, "offset": 0},
            headers=admin_headers,
        )
        second = client.get(
            "/api/p3/audit-reports",
            params={"search": "PAGEKEY", "limit": 2, "offset": 2},
            headers=admin_headers,
        )
        assert [row["audit_id"] for row in first.json()] == audit_ids[:2]
        assert [row["audit_id"] for row in second.json()] == audit_ids[2:]
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            conn.execute("DELETE FROM audit_reports WHERE audit_id LIKE 'AUD-PAGEKEY-%'")
            conn.execute("DELETE FROM audit_reports WHERE audit_id = 'AUD-UNRELATED'")
            conn.commit()
        finally:
            conn.close()


def test_backdated_audit_report_must_use_provenance_import(client, admin_headers):
    import os

    audit_number = f"BACKDATED-{uuid.uuid4().hex[:10]}"
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    response = client.post(
        "/api/p3/audit-reports",
        json={
            "audit_number": audit_number,
            "audit_date": yesterday,
            "auditor_id": "u-auditor",
            "auditee_id": "u-admin",
            "scope": "Audit source reconciliation",
        },
        headers=admin_headers,
    )
    try:
        assert response.status_code == 422
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            audit_ids = [row[0] for row in conn.execute(
                "SELECT audit_id FROM audit_reports WHERE audit_number = ?", (audit_number,)
            ).fetchall()]
            for audit_id in audit_ids:
                conn.execute(
                    "DELETE FROM audit_events WHERE entity_type = 'audit_report' AND entity_id = ?",
                    (audit_id,),
                )
                conn.execute("DELETE FROM audit_reports WHERE audit_id = ?", (audit_id,))
            conn.commit()
        finally:
            conn.close()


def _valid_pdf_bytes(title="Audit evidence"):
    from io import BytesIO
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": title})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _audit_import_payload(
    evidence_bytes, *, audit_number=None, evidence_file="attachments/source.pdf",
    source_auditor_id="u-safety/security", source_auditor_name="Brian Swanya",
    auditee_id="u-accountable",
):
    import hashlib

    return {
        "audit_number": audit_number or f"IMPORT-{uuid.uuid4().hex[:10]}",
        "audit_date": "2026-09-28",
        "source_auditor_id": source_auditor_id,
        "source_auditor_name": source_auditor_name,
        "auditee_id": auditee_id,
        "scope": "Safety and Security",
        "regulatory_basis": "Controlled source report",
        "evidence_file": evidence_file,
        "expected_evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "findings": [
            {
                "finding_number": "1",
                "area": "Safety",
                "level": 2,
                "title": "Source-reconciled finding",
                "description": "A representative finding from the controlled source.",
                "regulatory_reference": "KCAA source report",
            }
        ],
    }


def _cleanup_audit_import(import_id):
    import os

    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        row = conn.execute(
            "SELECT audit_id FROM audit_report_imports WHERE import_id = ?", (import_id,)
        ).fetchone()
        audit_id = row[0] if row else None
        finding_ids = []
        if audit_id:
            finding_ids = [item[0] for item in conn.execute(
                "SELECT finding_id FROM audit_findings WHERE audit_id = ?", (audit_id,)
            ).fetchall()]
        conn.execute("DELETE FROM audit_report_imports WHERE import_id = ?", (import_id,))
        if audit_id:
            conn.execute("DELETE FROM audit_findings WHERE audit_id = ?", (audit_id,))
            conn.execute("DELETE FROM audit_reports WHERE audit_id = ?", (audit_id,))
        for entity_id in [import_id, audit_id, *finding_ids]:
            if entity_id:
                conn.execute("DELETE FROM audit_events WHERE entity_id = ?", (entity_id,))
        conn.commit()
    finally:
        conn.close()


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
        "audit_number": "EXT-MISSING-AUDITOR", "audit_date": datetime.now(timezone.utc).date().isoformat(), "auditee_id": "u-admin",
    }, headers=admin_headers)
    assert missing_auditor.status_code == 422
    invalid_auditor = client.post("/api/p3/audit-reports", json={
        "audit_number": "EXT-INVALID-AUDITOR", "audit_date": datetime.now(timezone.utc).date().isoformat(), "auditor_id": "u-admin", "auditee_id": "u-reporter",
    }, headers=admin_headers)
    assert invalid_auditor.status_code == 403
    same_participant = client.post("/api/p3/audit-reports", json={
        "audit_number": "EXT-SAME-PARTICIPANT", "audit_date": datetime.now(timezone.utc).date().isoformat(), "auditor_id": "u-auditor", "auditee_id": "u-auditor",
    }, headers=admin_headers)
    assert same_participant.status_code == 422

    assert client.post("/api/p3/audit-reports", json={"audit_number": "EXT-1", "audit_date": datetime.now(timezone.utc).date().isoformat(), "auditor_id": "u-auditor", "auditee_id": "u-admin", "status": "bogus"}, headers=admin_headers).status_code == 422
    assert client.post("/api/p3/audit-findings", json={"audit_id": "x", "finding_number": "1", "area": "Safety", "level": 5, "title": "Bad", "description": "Bad"}, headers=admin_headers).status_code == 422
    assert client.post("/api/p3/audit-findings", json={"audit_id": "x"}, headers=admin_headers).status_code == 422
    assert client.get("/api/p3/audit-findings?status=unknown", headers=admin_headers).status_code == 422
    assert client.get("/api/p3/audit-findings?limit=1000", headers=admin_headers).status_code == 422
    assert client.get("/api/p3/audit-reports?limit=-1", headers=admin_headers).status_code == 422


def test_p3_create_rejects_missing_or_outside_evidence_references(client, admin_headers, tmp_path, monkeypatch):
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\nOutside evidence")
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    audit_numbers = [f"EXT-EVIDENCE-{uuid.uuid4().hex[:10]}" for _ in range(2)]

    for audit_number, evidence_file in zip(audit_numbers, ("attachments/missing.pdf", "attachments/../outside.pdf")):
        response = client.post("/api/p3/audit-reports", json={
            "audit_number": audit_number, "audit_date": datetime.now(timezone.utc).date().isoformat(), "auditor_id": "u-auditor",
            "auditee_id": "u-admin", "evidence_file": evidence_file,
        }, headers=admin_headers)
        assert response.status_code == 422

    conn = sqlite3.connect(__import__("os").environ["DMS_DB_PATH"])
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM audit_reports WHERE audit_number IN (?, ?)", audit_numbers,
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_p3_create_rejects_pdf_magic_prefix_without_valid_structure(client, admin_headers, tmp_path, monkeypatch):
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    (evidence_dir / "malformed.pdf").write_bytes(b"%PDF-1.7\nnot a complete PDF document")
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    response = client.post(
        "/api/p3/audit-reports",
        json={"audit_number": f"EXT-MALFORMED-{uuid.uuid4().hex[:8]}", "audit_date": datetime.now(timezone.utc).date().isoformat(),
              "auditor_id": "u-auditor", "auditee_id": "u-admin", "evidence_file": "attachments/malformed.pdf"},
        headers=admin_headers,
    )
    assert response.status_code == 422


def test_p3_snapshot_enforces_explicit_evidence_size_limit(tmp_path, monkeypatch):
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    path = evidence_dir / "oversized.pdf"
    payload = _valid_pdf_bytes("Bounded audit evidence")
    path.write_bytes(payload)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    monkeypatch.setenv("DMS_AUDIT_EVIDENCE_MAX_BYTES", str(len(payload) - 1))

    with pytest.raises(p3_routes.InvalidAuditEvidence):
        asyncio.run(p3_routes._snapshot_audit_evidence(path))


def test_p3_evidence_reference_fails_closed_without_size_policy(client, admin_headers, tmp_path, monkeypatch):
    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    (evidence_dir / "source.pdf").write_bytes(_valid_pdf_bytes())
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    monkeypatch.delenv("DMS_AUDIT_EVIDENCE_MAX_BYTES", raising=False)

    response = client.post(
        "/api/p3/audit-reports",
        json={
            "audit_number": f"EXT-NO-LIMIT-{uuid.uuid4().hex[:8]}",
            "audit_date": datetime.now(timezone.utc).date().isoformat(),
            "auditor_id": "u-auditor",
            "auditee_id": "u-admin",
            "evidence_file": "attachments/source.pdf",
        },
        headers=admin_headers,
    )

    assert response.status_code == 503


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
    forbidden_create = client.post("/api/p3/audit-reports", json={"audit_number": "NOPE", "audit_date": datetime.now(timezone.utc).date().isoformat(), "auditor_id": "u-auditor", "auditee_id": "u-admin"}, headers=independent_auditor)
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


@pytest.mark.parametrize(
    ("role", "actor"),
    [("accountable_manager", "u-accountable"), ("head_quality", "u-quality")],
)
def test_internal_audit_readers_can_list_reports_without_create_access(client, admin_headers, role, actor):
    audit_id = _create_report(client, admin_headers)
    headers = {"X-Role": role, "X-Actor": actor}

    response = client.get("/api/p3/audit-reports", headers=headers)
    assert response.status_code == 200
    assert any(report["audit_id"] == audit_id for report in response.json())

    create = client.post(
        "/api/p3/audit-reports",
        json={"audit_number": f"NO-CREATE-{uuid.uuid4().hex[:8]}", "audit_date": datetime.now(timezone.utc).date().isoformat(),
              "auditor_id": "u-auditor", "auditee_id": "u-admin"},
        headers=headers,
    )
    assert create.status_code == 403


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


def test_p3_downloads_audit_report_evidence_for_authorized_reader(client, admin_headers, tmp_path, monkeypatch):
    import hashlib
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    evidence = _valid_pdf_bytes("Audit evidence")
    (evidence_dir / "report.pdf").write_bytes(evidence)
    created = client.post(
        "/api/p3/audit-reports",
        json={"audit_number": f"EXT-{uuid.uuid4().hex[:10]}", "audit_date": datetime.now(timezone.utc).date().isoformat(), "scope": "External audit",
              "auditor_id": "u-auditor", "auditee_id": "u-admin", "evidence_file": "attachments/report.pdf"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    audit_id = created.json()["audit_id"]
    assert created.json()["evidence_sha256"] == hashlib.sha256(evidence).hexdigest()
    report = next(row for row in client.get("/api/p3/audit-reports", headers=admin_headers).json() if row["audit_id"] == audit_id)
    assert report["evidence_sha256"] == hashlib.sha256(evidence).hexdigest()

    response = client.get(f"/api/p3/audit-reports/{audit_id}/evidence", headers=admin_headers)

    assert response.status_code == 200, response.text
    assert response.content == evidence
    assert response.headers["content-length"] == str(len(evidence))
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert 'attachment; filename="report.pdf"' in response.headers["content-disposition"]

    (evidence_dir / "report.pdf").write_bytes(_valid_pdf_bytes("Replacement evidence"))
    tampered = client.get(f"/api/p3/audit-reports/{audit_id}/evidence", headers=admin_headers)
    assert tampered.status_code == 409


def test_p3_evidence_download_serves_verified_bytes_after_path_replacement(client, admin_headers, tmp_path, monkeypatch):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    evidence = _valid_pdf_bytes("Verified evidence")
    replacement = _valid_pdf_bytes("Different evidence")
    (evidence_dir / "race.pdf").write_bytes(evidence)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    created = client.post(
        "/api/p3/audit-reports",
        json={"audit_number": f"EXT-{uuid.uuid4().hex[:10]}", "audit_date": datetime.now(timezone.utc).date().isoformat(),
              "auditor_id": "u-auditor", "auditee_id": "u-admin", "evidence_file": "attachments/race.pdf"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    audit_id = created.json()["audit_id"]
    original_snapshot = p3_routes._snapshot_audit_evidence

    async def replace_after_snapshot(path, expected_sha256=None):
        snapshot, digest, size = await original_snapshot(path, expected_sha256)
        replacement_path = path.with_name(f"{path.name}.replacement")
        replacement_path.write_bytes(replacement)
        os.replace(replacement_path, path)
        return snapshot, digest, size

    monkeypatch.setattr(p3_routes, "_snapshot_audit_evidence", replace_after_snapshot)
    response = client.get(f"/api/p3/audit-reports/{audit_id}/evidence", headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.content == evidence


def test_p3_evidence_download_rejects_attachment_directory_symlink_swap(client, admin_headers, tmp_path, monkeypatch):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    displaced_dir = tmp_path / "attachments-original"
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    evidence = _valid_pdf_bytes("Bound evidence")
    (evidence_dir / "report.pdf").write_bytes(evidence)
    (outside_dir / "report.pdf").write_bytes(evidence)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    created = client.post(
        "/api/p3/audit-reports",
        json={"audit_number": f"EXT-{uuid.uuid4().hex[:10]}", "audit_date": datetime.now(timezone.utc).date().isoformat(),
              "auditor_id": "u-auditor", "auditee_id": "u-admin", "evidence_file": "attachments/report.pdf"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    audit_id = created.json()["audit_id"]
    original_snapshot = p3_routes._snapshot_audit_evidence

    async def swap_directory_then_snapshot(path, expected_sha256=None):
        os.rename(evidence_dir, displaced_dir)
        evidence_dir.symlink_to(outside_dir, target_is_directory=True)
        return await original_snapshot(path, expected_sha256)

    monkeypatch.setattr(p3_routes, "_snapshot_audit_evidence", swap_directory_then_snapshot)
    response = client.get(f"/api/p3/audit-reports/{audit_id}/evidence", headers=admin_headers)
    assert response.status_code == 409


def test_p3_evidence_download_fails_closed_for_hashless_legacy_report(client, admin_headers, tmp_path, monkeypatch):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    (evidence_dir / "legacy.pdf").write_bytes(b"%PDF-1.4\nLegacy attachment\n")
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    audit_id = _create_report(client, admin_headers)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute(
            "UPDATE audit_reports SET evidence_file=? WHERE audit_id=?",
            ("attachments/legacy.pdf", audit_id),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.get(f"/api/p3/audit-reports/{audit_id}/evidence", headers=admin_headers)
    assert response.status_code == 409


def test_p3_evidence_download_rejects_paths_outside_attachments(client, admin_headers, tmp_path, monkeypatch):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\nNot authorized\n")
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    audit_id = _create_report(client, admin_headers)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute(
            "UPDATE audit_reports SET evidence_file=? WHERE audit_id=?",
            ("attachments/../outside.pdf", audit_id),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.get(f"/api/p3/audit-reports/{audit_id}/evidence", headers=admin_headers)

    assert response.status_code == 404
    assert b"Not authorized" not in response.content


def test_p3_evidence_download_requires_audit_report_read_permission(client, admin_headers, tmp_path, monkeypatch):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    (evidence_dir / "report.pdf").write_bytes(b"%PDF-1.4\nAudit evidence\n")
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    audit_id = _create_report(client, admin_headers)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute(
            "UPDATE audit_reports SET evidence_file=? WHERE audit_id=?",
            ("attachments/report.pdf", audit_id),
        )
        conn.commit()
    finally:
        conn.close()

    reporter_headers = {"X-Role": "occurrence_reporter", "X-Actor": "u-reporter"}
    response = client.get(f"/api/p3/audit-reports/{audit_id}/evidence", headers=reporter_headers)

    assert response.status_code == 403


def test_p3_evidence_download_returns_404_when_report_has_no_evidence(client, admin_headers):
    audit_id = _create_report(client, admin_headers)

    response = client.get(f"/api/p3/audit-reports/{audit_id}/evidence", headers=admin_headers)

    assert response.status_code == 404


def test_p3_evidence_download_rejects_non_pdf_file(client, admin_headers, tmp_path, monkeypatch):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    (evidence_dir / "not-pdf.pdf").write_bytes(b"not a PDF")
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    audit_id = _create_report(client, admin_headers)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute(
            "UPDATE audit_reports SET evidence_file=? WHERE audit_id=?",
            ("attachments/not-pdf.pdf", audit_id),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.get(f"/api/p3/audit-reports/{audit_id}/evidence", headers=admin_headers)

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("column", "tampered_value"),
    (("audit_date", "2026-09-29"), ("scope", "Tampered scope"), ("regulatory_basis", "Tampered basis")),
)
def test_import_verification_rejects_mismatched_duplicated_metadata(
    client, admin_headers, tmp_path, monkeypatch, column, tampered_value
):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    evidence = _valid_pdf_bytes("Duplicated metadata consistency")
    (evidence_dir / "source.pdf").write_bytes(evidence)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    created = client.post(
        "/api/p3/audit-report-imports",
        json=_audit_import_payload(evidence),
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    import_id = created.json()["import_id"]
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        update_sql = {
            "audit_date": "UPDATE audit_report_imports SET audit_date = ? WHERE import_id = ?",
            "scope": "UPDATE audit_report_imports SET scope = ? WHERE import_id = ?",
            "regulatory_basis": "UPDATE audit_report_imports SET regulatory_basis = ? WHERE import_id = ?",
        }
        conn.execute(update_sql[column], (tampered_value, import_id))
        conn.commit()
    finally:
        conn.close()

    try:
        verify = client.post(
            f"/api/p3/audit-report-imports/{import_id}/verify",
            json={
                "source_checksum_confirmed": True,
                "findings_reconciled": True,
                "verification_notes": "Independent source and finding reconciliation completed.",
            },
            headers={"X-Role": "independent_auditor", "X-Actor": "u-auditor"},
        )
        assert verify.status_code == 409
    finally:
        _cleanup_audit_import(import_id)


def test_audit_import_evidence_validation_happens_before_sqlite_write_transaction(
    client, admin_headers, tmp_path, monkeypatch
):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    evidence = _valid_pdf_bytes("Verification lock boundary")
    (evidence_dir / "source.pdf").write_bytes(evidence)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    created = client.post(
        "/api/p3/audit-report-imports",
        json=_audit_import_payload(evidence),
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    import_id = created.json()["import_id"]
    original_snapshot = p3_routes._snapshot_audit_evidence
    validation_sees_unlocked_db = False

    async def inspect_before_validation(path, expected_sha256):
        nonlocal validation_sees_unlocked_db
        connection = sqlite3.connect(os.environ["DMS_DB_PATH"], timeout=0.05)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()
            validation_sees_unlocked_db = True
        finally:
            connection.close()
        return await original_snapshot(path, expected_sha256)

    monkeypatch.setattr(p3_routes, "_snapshot_audit_evidence", inspect_before_validation)
    try:
        verified = client.post(
            f"/api/p3/audit-report-imports/{import_id}/verify",
            json={
                "source_checksum_confirmed": True,
                "findings_reconciled": True,
                "verification_notes": "Independent source and finding reconciliation completed.",
            },
            headers={"X-Role": "independent_auditor", "X-Actor": "u-auditor"},
        )
        assert verified.status_code == 200, verified.text
        assert validation_sees_unlocked_db is True
    finally:
        _cleanup_audit_import(import_id)


def test_historical_audit_import_preserves_source_auditor_and_requires_independent_verifier(
    client, admin_headers, tmp_path, monkeypatch
):
    import hashlib
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    evidence = _valid_pdf_bytes("Historical audit source")
    evidence_path = evidence_dir / "historical-report.pdf"
    evidence_path.write_bytes(evidence)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    audit_number = f"IMPORT-{uuid.uuid4().hex[:10]}"
    payload = {
        "audit_number": audit_number,
        "audit_date": "2026-09-28",
        "source_auditor_id": "u-safety/security",
        "source_auditor_name": "Brian Swanya",
        "auditee_id": "u-accountable",
        "scope": "Safety and Security",
        "regulatory_basis": "Controlled source report",
        "evidence_file": "attachments/historical-report.pdf",
        "expected_evidence_sha256": hashlib.sha256(evidence).hexdigest(),
        "findings": [
            {
                "finding_number": "1",
                "area": "Safety",
                "level": 2,
                "title": "Source-reconciled finding",
                "description": "A representative finding from the controlled source.",
                "regulatory_reference": "KCAA source report",
            }
        ],
    }
    import_id = None
    audit_id = None
    try:
        same_actor_payload = dict(payload)
        same_actor_payload["source_auditor_id"] = "u-admin"
        same_actor_payload["source_auditor_name"] = "System administrator"
        same_actor = client.post(
            "/api/p3/audit-report-imports", json=same_actor_payload, headers=admin_headers
        )
        assert same_actor.status_code == 403

        wrong_checksum_payload = dict(payload)
        wrong_checksum_payload["expected_evidence_sha256"] = "0" * 64
        wrong_checksum = client.post(
            "/api/p3/audit-report-imports", json=wrong_checksum_payload, headers=admin_headers
        )
        assert wrong_checksum.status_code == 409

        imported = client.post("/api/p3/audit-report-imports", json=payload, headers=admin_headers)
        assert imported.status_code == 201, imported.text
        import_id = imported.json()["import_id"]
        assert imported.json()["status"] == "pending_verification"
        assert imported.json()["source_auditor_id"] == "u-safety/security"
        assert imported.json()["imported_by"] == "u-admin"
        unrelated_reader = {"X-Role": "head_quality", "X-Actor": "u-quality"}
        assert client.get("/api/p3/audit-report-imports", headers=unrelated_reader).status_code == 403

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            assert conn.execute("SELECT COUNT(*) FROM audit_reports WHERE audit_number = ?", (audit_number,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM audit_findings WHERE title = ?", ("Source-reconciled finding",)).fetchone()[0] == 0
        finally:
            conn.close()

        verifier_headers = {"X-Role": "independent_auditor", "X-Actor": "u-auditor"}
        forbidden_import = client.post("/api/p3/audit-report-imports", json=payload, headers=verifier_headers)
        assert forbidden_import.status_code == 403
        forbidden_verification = client.post(
            f"/api/p3/audit-report-imports/{import_id}/verify",
            json={
                "source_checksum_confirmed": True,
                "findings_reconciled": True,
                "verification_notes": "Independent source and payload review completed.",
            },
            headers=admin_headers,
        )
        assert forbidden_verification.status_code == 403

        candidate = client.get(f"/api/p3/audit-report-imports/{import_id}", headers=verifier_headers)
        assert candidate.status_code == 200, candidate.text
        assert candidate.json()["source_auditor_name"] == "Brian Swanya"
        assert candidate.json()["payload_sha256"]
        evidence_response = client.get(
            f"/api/p3/audit-report-imports/{import_id}/evidence", headers=verifier_headers
        )
        assert evidence_response.status_code == 200, evidence_response.text
        assert evidence_response.content == evidence

        incomplete_review = client.post(
            f"/api/p3/audit-report-imports/{import_id}/verify",
            json={
                "source_checksum_confirmed": False,
                "findings_reconciled": True,
                "verification_notes": "Independent source review was not completed.",
            },
            headers=verifier_headers,
        )
        assert incomplete_review.status_code == 422

        evidence_path.write_bytes(evidence + b"tampered")
        tampered_source = client.post(
            f"/api/p3/audit-report-imports/{import_id}/verify",
            json={
                "source_checksum_confirmed": True,
                "findings_reconciled": True,
                "verification_notes": "Independent source and finding reconciliation completed.",
            },
            headers=verifier_headers,
        )
        assert tampered_source.status_code == 409
        evidence_path.write_bytes(evidence)

        verified = client.post(
            f"/api/p3/audit-report-imports/{import_id}/verify",
            json={
                "source_checksum_confirmed": True,
                "findings_reconciled": True,
                "verification_notes": "Independent source and finding reconciliation completed.",
            },
            headers=verifier_headers,
        )
        assert verified.status_code == 200, verified.text
        audit_id = verified.json()["audit_id"]
        assert verified.json()["status"] == "imported"
        assert verified.json()["source_auditor_id"] == "u-safety/security"
        assert verified.json()["imported_by"] == "u-admin"
        assert verified.json()["verified_by"] == "u-auditor"

        report = next(row for row in client.get("/api/p3/audit-reports", headers=admin_headers).json() if row["audit_id"] == audit_id)
        assert report["auditor_id"] == "u-safety/security"
        findings = client.get(f"/api/p3/audit-findings?audit_id={audit_id}", headers=admin_headers)
        assert findings.status_code == 200, findings.text
        assert len(findings.json()) == 1
        assert findings.json()[0]["finding_number"] == "1"
        assert findings.json()[0]["title"] == "Source-reconciled finding"

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            import_row = conn.execute(
                "SELECT status, source_auditor_id, source_auditor_name, imported_by, verified_by, audit_id "
                "FROM audit_report_imports WHERE import_id = ?",
                (import_id,),
            ).fetchone()
            assert import_row == (
                "imported", "u-safety/security", "Brian Swanya", "u-admin", "u-auditor", audit_id
            )
            events = conn.execute(
                "SELECT action, actor_id FROM audit_events WHERE entity_type = 'audit_report_import' AND entity_id = ? ORDER BY timestamp, rowid",
                (import_id,),
            ).fetchall()
            assert events == [("created", "u-admin"), ("provenance_verified", "u-auditor")]
            finding_id = conn.execute(
                "SELECT finding_id FROM audit_findings WHERE audit_id = ?", (audit_id,)
            ).fetchone()[0]
            finding_events = conn.execute(
                "SELECT action, actor_id FROM audit_events WHERE entity_type = 'audit_finding' AND entity_id = ?",
                (finding_id,),
            ).fetchall()
            assert finding_events == [("imported", "u-auditor")]
        finally:
            conn.close()
    finally:
        if import_id:
            conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
            try:
                conn.execute("DELETE FROM audit_report_imports WHERE import_id = ?", (import_id,))
                if audit_id:
                    conn.execute("DELETE FROM audit_findings WHERE audit_id = ?", (audit_id,))
                    conn.execute("DELETE FROM audit_reports WHERE audit_id = ?", (audit_id,))
                conn.execute("DELETE FROM audit_events WHERE entity_id = ?", (import_id,))
                if audit_id:
                    conn.execute("DELETE FROM audit_events WHERE entity_id = ?", (audit_id,))
                conn.commit()
            finally:
                conn.close()


def test_import_verifier_must_be_distinct_from_source_auditor(client, admin_headers, tmp_path, monkeypatch):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    evidence = _valid_pdf_bytes("Source auditor separation")
    (evidence_dir / "source.pdf").write_bytes(evidence)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    payload = _audit_import_payload(
        evidence, source_auditor_id="u-auditor", source_auditor_name="Independent Auditor"
    )
    import_id = None
    try:
        response = client.post("/api/p3/audit-report-imports", json=payload, headers=admin_headers)
        assert response.status_code == 201, response.text
        import_id = response.json()["import_id"]

        verifier_headers = {"X-Role": "independent_auditor", "X-Actor": "u-auditor"}
        verify = client.post(
            f"/api/p3/audit-report-imports/{import_id}/verify",
            json={
                "source_checksum_confirmed": True,
                "findings_reconciled": True,
                "verification_notes": "Review attempted by the source auditor account.",
            },
            headers=verifier_headers,
        )
        assert verify.status_code == 403
        current = client.get(f"/api/p3/audit-report-imports/{import_id}", headers=admin_headers)
        assert current.status_code == 200
        assert current.json()["status"] == "pending_verification"

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            assert conn.execute(
                "SELECT COUNT(*) FROM audit_reports WHERE audit_number = ?", (payload["audit_number"],)
            ).fetchone()[0] == 0
        finally:
            conn.close()
    finally:
        if import_id:
            _cleanup_audit_import(import_id)


def test_import_operator_cannot_verify_through_a_second_role_alias(
    client, admin_headers, tmp_path, monkeypatch
):
    import os
    from app import p0_auth, p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    evidence = _valid_pdf_bytes("Import operator separation")
    (evidence_dir / "source.pdf").write_bytes(evidence)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    payload = _audit_import_payload(evidence)
    import_id = None
    role_added = False
    try:
        response = client.post("/api/p3/audit-report-imports", json=payload, headers=admin_headers)
        assert response.status_code == 201, response.text
        import_id = response.json()["import_id"]

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            existing = conn.execute(
                "SELECT 1 FROM user_roles WHERE user_id = 'u-admin' AND role = 'independent_auditor'"
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO user_roles (user_id, role) VALUES ('u-admin', 'independent_auditor')"
                )
                conn.commit()
                role_added = True
        finally:
            conn.close()
        monkeypatch.setitem(
            p0_auth.DEV_IDENTITY_ROLES,
            "admin-as-auditor-test",
            ("u-admin", "independent_auditor"),
        )
        same_principal = client.post(
            f"/api/p3/audit-report-imports/{import_id}/verify",
            json={
                "source_checksum_confirmed": True,
                "findings_reconciled": True,
                "verification_notes": "The import operator attempted a second-role review.",
            },
            headers={"X-Role": "independent_auditor", "X-Actor": "admin-as-auditor-test"},
        )
        assert same_principal.status_code == 403
        current = client.get(f"/api/p3/audit-report-imports/{import_id}", headers=admin_headers)
        assert current.status_code == 200
        assert current.json()["status"] == "pending_verification"
    finally:
        if import_id:
            _cleanup_audit_import(import_id)
        if role_added:
            conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
            try:
                conn.execute(
                    "DELETE FROM user_roles WHERE user_id = 'u-admin' AND role = 'independent_auditor'"
                )
                conn.commit()
            finally:
                conn.close()


def test_independent_auditor_can_reject_import_without_publishing_report(
    client, admin_headers, tmp_path, monkeypatch
):
    import os
    from app import p3_routes

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    evidence = _valid_pdf_bytes("Rejected source")
    (evidence_dir / "source.pdf").write_bytes(evidence)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir, raising=False)
    payload = _audit_import_payload(evidence)
    import_id = None
    try:
        response = client.post("/api/p3/audit-report-imports", json=payload, headers=admin_headers)
        assert response.status_code == 201, response.text
        import_id = response.json()["import_id"]
        rejected = client.post(
            f"/api/p3/audit-report-imports/{import_id}/reject",
            json={"reason": "Source copy did not reconcile with the controlled record."},
            headers={"X-Role": "independent_auditor", "X-Actor": "u-auditor"},
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "rejected"
        assert rejected.json()["rejected_by"] == "u-auditor"

        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            status, verified_by, notes = conn.execute(
                "SELECT status, verified_by, verification_notes FROM audit_report_imports WHERE import_id = ?",
                (import_id,),
            ).fetchone()
            assert status == "rejected"
            assert verified_by is None
            assert notes == "Source copy did not reconcile with the controlled record."
            assert conn.execute(
                "SELECT COUNT(*) FROM audit_reports WHERE audit_number = ?", (payload["audit_number"],)
            ).fetchone()[0] == 0
            event = conn.execute(
                "SELECT action, actor_id FROM audit_events WHERE entity_type = 'audit_report_import' AND entity_id = ? ORDER BY rowid DESC LIMIT 1",
                (import_id,),
            ).fetchone()
            assert event == ("provenance_rejected", "u-auditor")
        finally:
            conn.close()
    finally:
        if import_id:
            _cleanup_audit_import(import_id)
