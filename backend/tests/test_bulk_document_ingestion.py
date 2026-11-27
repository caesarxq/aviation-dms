"""Tests for bulk document intake into the Documents section.

Covers classification (incl. historical audits/CARs quarantined to
audit_report_import), deduplication, safeguard integration, and the apply step
with the audit import provenance gate.
"""
import io
import json

import pytest
from fastapi.testclient import TestClient

import app.p0_routes as p0_routes
from app.database import get_db
from app.main import app

client = TestClient(app)


async def _seed_users():
    """Insert the users referenced by audit_report_import FK constraints."""
    now = p0_routes.now_iso()
    db = await get_db()
    try:
        for user_id, username, email, role in (
            ("u-admin", "admin", "admin@example.com", "system_admin"),
            ("u-auditor", "auditor", "auditor@example.com", "independent_auditor"),
            ("u-auditee", "auditee", "auditee@example.com", "head_quality"),
        ):
            await db.execute(
                """INSERT OR IGNORE INTO users
                   (user_id, username, email, full_name, role, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (user_id, username, email, user_id.replace("-", " ").title(), role, now, now),
            )
        await db.commit()
    finally:
        await db.close()


def _stub_upload_safeguards(monkeypatch):
    async def no_scan(content, policy):
        return None

    async def no_validation(content, suffix, max_bytes):
        return None

    monkeypatch.setattr(p0_routes, "load_upload_safety_policy", lambda: object())
    monkeypatch.setattr(p0_routes, "ensure_upload_capacity", lambda *args, **kwargs: None)
    monkeypatch.setattr(p0_routes, "scan_upload_bytes", no_scan)
    monkeypatch.setattr(p0_routes, "validate_upload_content", no_validation)


def _stub_classification(monkeypatch, document_type, target_table, confidence=0.8, fields=None):
    class Result:
        def __init__(self, raw_text):
            self.document_type = document_type
            self.confidence = confidence
            self.extracted_fields = fields or {}
            self.target_table = target_table
            self.raw_text = raw_text[:200]

    monkeypatch.setattr(p0_routes, "extract_pdf_text", lambda b: "extracted text")
    monkeypatch.setattr(p0_routes, "classify_and_extract", lambda text: Result(text))


def _upload_files(monkeypatch, files, classification=None):
    _stub_upload_safeguards(monkeypatch)
    if classification:
        _stub_classification(monkeypatch, *classification)
    return client.post(
        "/api/p0/documents/ingest/bulk",
        files=[("file", (name, content, "application/pdf")) for name, content in files],
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )


@pytest.fixture(autouse=True)
def _clear_staging():
    """Clear durable staging rows between tests so dedupe state is isolated."""
    import asyncio

    async def clear():
        db = await get_db()
        try:
            await db.execute("DELETE FROM document_ingestion_staging")
            await db.execute("DELETE FROM document_ingestion_log")
            await db.commit()
        finally:
            await db.close()

    asyncio.run(clear())
    yield
    asyncio.run(clear())


def test_bulk_ingest_classifies_historical_audit_to_quarantine(monkeypatch):
    """A historical audit report classifies to audit_report_import and is staged."""
    resp = _upload_files(
        monkeypatch,
        [("SS-KFL-SEP-2026.pdf", b"%PDF audit report")],
        classification=(
            "audit_report",
            "audit_report_import",
            0.78,
            {"audit_number": "SS-KFL-SEP-2026", "findings": [{"finding_number": "F-01"}]},
        ),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["staged"] == 1
    assert body["duplicates"] == 0
    item = body["items"][0]
    assert item["status"] == "staged"
    assert item["target_table"] == "audit_report_import"
    assert item["document_type"] == "audit_report"
    assert item["staging_id"]


def test_bulk_ingest_classifies_kcaa_correspondence_to_documents(monkeypatch):
    resp = _upload_files(
        monkeypatch,
        [("kcaa-letter.pdf", b"%PDF KCAA correspondence")],
        classification=("kcaa_correspondence", "documents", 0.75, {"doc_class": "policy"}),
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["target_table"] == "documents"
    assert item["status"] == "staged"


def test_bulk_ingest_deduplicates_by_sha256(monkeypatch):
    _stub_upload_safeguards(monkeypatch)
    _stub_classification(monkeypatch, "audit_report", "audit_report_import", 0.8, {})
    first = client.post(
        "/api/p0/documents/ingest/bulk",
        files=[("file", ("a.pdf", b"%PDF same bytes", "application/pdf"))],
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    assert first.status_code == 200
    first_id = first.json()["items"][0]["staging_id"]

    # Same bytes again -> duplicate.
    second = client.post(
        "/api/p0/documents/ingest/bulk",
        files=[("file", ("b.pdf", b"%PDF same bytes", "application/pdf"))],
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["duplicates"] == 1
    assert body["staged"] == 0
    assert body["items"][0]["status"] == "duplicate"
    assert body["items"][0]["duplicate_of"] == first_id


def test_bulk_ingest_rejects_bad_extension_and_oversize(monkeypatch):
    _stub_upload_safeguards(monkeypatch)
    resp = client.post(
        "/api/p0/documents/ingest/bulk",
        files=[
            ("file", ("bad.exe", b"MZ executable", "application/octet-stream")),
            ("file", ("big.pdf", b"x" * (10 * 1024 * 1024 + 1), "application/pdf")),
        ],
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rejected"] == 2
    assert all(i["status"] == "rejected" for i in body["items"])


def test_apply_bulk_ingestion_creates_document_draft(monkeypatch):
    """Applying a documents-target staged item creates a draft document + version."""
    # Stage one document-target item.
    _stub_upload_safeguards(monkeypatch)
    _stub_classification(monkeypatch, "kcaa_correspondence", "documents", 0.8, {})
    stage = client.post(
        "/api/p0/documents/ingest/bulk",
        files=[("file", ("oa.pdf", b"%PDF oa", "application/pdf"))],
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    assert stage.status_code == 200
    staging_id = stage.json()["items"][0]["staging_id"]

    import asyncio

    async def file_path():
        db = await get_db()
        try:
            row = await (
                await db.execute(
                    "SELECT file_path FROM document_ingestion_staging WHERE staging_id = ?",
                    (staging_id,),
                )
            ).fetchone()
            return row["file_path"]
        finally:
            await db.close()

    path = asyncio.run(file_path())

    # Read the staged file bytes back so apply can attach it as document content.
    staged_bytes = open(path, "rb").read()

    resp = client.post(
        "/api/p0/documents/ingest/bulk/apply",
        json={
            "items": [
                {
                    "staging_id": staging_id,
                    "target_table": "documents",
                }
            ]
        },
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["applied"] == 1
    assert body["results"][0]["status"] == "applied"
    assert "ingested document" in body["results"][0]["detail"]

    # Verify a draft document and version exist.
    import asyncio as _a

    async def check():
        db = await get_db()
        try:
            doc = await (
                await db.execute(
                    "SELECT document_id, title, status, doc_class FROM documents WHERE owner_id = ? ORDER BY created_at DESC LIMIT 1",
                    ("u-admin",),
                )
            ).fetchone()
            assert doc is not None
            assert doc["status"] == "draft"
            assert doc["doc_class"] == "policy"
            ver = await (
                await db.execute(
                    "SELECT version_id FROM document_versions WHERE document_id = ?",
                    (doc["document_id"],),
                )
            ).fetchone()
            assert ver is not None
            # Staging row marked applied.
            st = await (
                await db.execute(
                    "SELECT status FROM document_ingestion_staging WHERE staging_id = ?",
                    (staging_id,),
                )
            ).fetchone()
            assert st["status"] == "applied"
        finally:
            await db.close()

    _a.run(check())


def test_apply_bulk_ingestion_audit_import_requires_system_admin(monkeypatch):
    _stub_upload_safeguards(monkeypatch)
    _stub_classification(monkeypatch, "audit_report", "audit_report_import", 0.8, {})
    stage = client.post(
        "/api/p0/documents/ingest/bulk",
        files=[("file", ("audit.pdf", b"%PDF audit", "application/pdf"))],
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    staging_id = stage.json()["items"][0]["staging_id"]

    # head_quality lacks system_admin + audit_report:import gate.
    resp = client.post(
        "/api/p0/documents/ingest/bulk/apply",
        json={
            "items": [
                {
                    "staging_id": staging_id,
                    "target_table": "audit_report_import",
                    "source_auditor_id": "u-auditor",
                    "source_auditor_name": "External Auditor",
                    "auditee_id": "u-auditee",
                    "audit_number": "SS-KFL-SEP-2026",
                    "audit_date": "2026-09-30",
                    "scope": "SMS",
                    "regulatory_basis": "KCAA",
                }
            ]
        },
        headers={"X-Role": "head_quality", "X-Actor": "u-quality"},
    )
    assert resp.status_code == 403, resp.text


def test_apply_bulk_ingestion_audit_import_missing_source_identities(monkeypatch):
    _stub_upload_safeguards(monkeypatch)
    _stub_classification(monkeypatch, "audit_report", "audit_report_import", 0.8, {})
    stage = client.post(
        "/api/p0/documents/ingest/bulk",
        files=[("file", ("audit.pdf", b"%PDF audit", "application/pdf"))],
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    staging_id = stage.json()["items"][0]["staging_id"]

    resp = client.post(
        "/api/p0/documents/ingest/bulk/apply",
        json={
            "items": [
                {
                    "staging_id": staging_id,
                    "target_table": "audit_report_import",
                    # source identities deliberately missing
                }
            ]
        },
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    assert resp.status_code == 422, resp.text


def test_apply_bulk_ingestion_audit_import_stages_pending_verification(monkeypatch):
    _stub_upload_safeguards(monkeypatch)
    _stub_classification(monkeypatch, "audit_report", "audit_report_import", 0.8, {})
    stage = client.post(
        "/api/p0/documents/ingest/bulk",
        files=[("file", ("audit.pdf", b"%PDF audit", "application/pdf"))],
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    staging_id = stage.json()["items"][0]["staging_id"]
    import asyncio as _a

    _a.run(_seed_users())

    resp = client.post(
        "/api/p0/documents/ingest/bulk/apply",
        json={
            "items": [
                {
                    "staging_id": staging_id,
                    "target_table": "audit_report_import",
                    "source_auditor_id": "u-auditor",
                    "source_auditor_name": "External Auditor",
                    "auditee_id": "u-auditee",
                    "audit_number": "SS-KFL-SEP-2026",
                    "audit_date": "2026-09-30",
                    "scope": "SMS audit",
                    "regulatory_basis": "KCAA Civil Aviation Regulations",
                }
            ]
        },
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["applied"] == 1, body["results"]
    assert "pending provenance verification" in body["results"][0]["detail"]

    import asyncio as _a

    async def check():
        db = await get_db()
        try:
            row = await (
                await db.execute(
                    "SELECT status, audit_number, imported_by FROM audit_report_imports WHERE audit_number = ?",
                    ("SS-KFL-SEP-2026",),
                )
            ).fetchone()
            assert row is not None
            assert row["status"] == "pending_verification"
            assert row["imported_by"] == "u-admin"
            # Staging row marked applied.
            st = await (
                await db.execute(
                    "SELECT status FROM document_ingestion_staging WHERE staging_id = ?",
                    (staging_id,),
                )
            ).fetchone()
            assert st["status"] == "applied"
            # Confirm no direct audit_reports row was created.
            ar = await (
                await db.execute(
                    "SELECT 1 FROM audit_reports WHERE audit_number = ?",
                    ("SS-KFL-SEP-2026",),
                )
            ).fetchone()
            assert ar is None
        finally:
            await db.close()

    _a.run(check())


def test_apply_bulk_ingestion_rejects_unknown_table(monkeypatch):
    _stub_upload_safeguards(monkeypatch)
    _stub_classification(monkeypatch, "unknown", "documents", 0.0, {})
    stage = client.post(
        "/api/p0/documents/ingest/bulk",
        files=[("file", ("x.pdf", b"%PDF", "application/pdf"))],
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    staging_id = stage.json()["items"][0]["staging_id"]

    resp = client.post(
        "/api/p0/documents/ingest/bulk/apply",
        json={
            "items": [
                {"staging_id": staging_id, "target_table": "not_a_table"}
            ]
        },
        headers={"X-Role": "system_admin", "X-Actor": "u-admin"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["rejected"] == 1
    assert body["results"][0]["status"] == "rejected"
