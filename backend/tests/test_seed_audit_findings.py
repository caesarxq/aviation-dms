import asyncio
import hashlib
import sqlite3

import pytest

from app import database, p3_routes
import app.seed_audit_findings as audit_seed


@pytest.fixture(autouse=True)
def _configure_seed_evidence_safeguards(monkeypatch):
    monkeypatch.setenv("DMS_UPLOAD_QUOTA_SCOPE", "system")
    monkeypatch.setenv("DMS_UPLOAD_STORAGE_QUOTA_BYTES", str(100 * 1024 * 1024))
    monkeypatch.setenv("DMS_CLAMD_HOST", "127.0.0.1")
    monkeypatch.setenv("DMS_CLAMD_PORT", "3310")
    monkeypatch.setenv("DMS_CLAMD_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DMS_CLAMD_MAX_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DMS_AUDIT_EVIDENCE_MAX_BYTES", str(10 * 1024 * 1024))

    async def clean_scan(payload, policy):
        return None

    monkeypatch.setattr(p3_routes, "scan_upload_bytes", clean_scan)


def _valid_pdf_bytes(title="Audit source evidence"):
    from io import BytesIO
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": title})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_external_audit_payload_preserves_confirmed_count_and_gap():
    finding_numbers = [str(finding[0]) for finding in audit_seed.FINDINGS]
    assert finding_numbers == [str(number) for number in [*range(1, 32), *range(33, 40)]]
    assert audit_seed.AUDIT_EVIDENCE_SHA256 == "db99508fabee281f86c52fc182c1f54926538e53a298857b0a9b2a12ad156efd"
    assert audit_seed.AUDIT_DATA["evidence_file"] == "attachments/SAFETY AND SECURITY SEPTEMBER  2026 AUDIT REPORT.pdf"


def test_external_seed_requires_explicit_development_import_mode(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.delenv("AUDIT_IMPORT_ENABLED", raising=False)

    def evidence_validation_is_forbidden(_):
        raise AssertionError("import mode must be checked before evidence or database access")

    async def database_access_is_forbidden():
        raise AssertionError("import mode must be checked before database access")

    monkeypatch.setattr(audit_seed, "_validated_audit_report_evidence_path", evidence_validation_is_forbidden)
    monkeypatch.setattr(audit_seed, "get_db", database_access_is_forbidden)
    with pytest.raises(RuntimeError, match="AUDIT_IMPORT_ENABLED"):
        asyncio.run(audit_seed.seed_audit_findings())


def test_external_seed_requires_source_attribution_confirmation(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ENABLED", "true")
    monkeypatch.delenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", raising=False)

    def evidence_validation_is_forbidden(_):
        raise AssertionError("source attribution must be confirmed before evidence or database access")

    async def database_access_is_forbidden():
        raise AssertionError("source attribution must be confirmed before database access")

    monkeypatch.setattr(audit_seed, "_validated_audit_report_evidence_path", evidence_validation_is_forbidden)
    monkeypatch.setattr(audit_seed, "get_db", database_access_is_forbidden)
    with pytest.raises(RuntimeError, match="AUDIT_IMPORT_ATTRIBUTION_CONFIRMED"):
        asyncio.run(audit_seed.seed_audit_findings())


def test_external_seed_requires_source_reconciliation_before_evidence_or_database_access(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED", "true")
    monkeypatch.delenv("AUDIT_IMPORT_SOURCE_RECONCILED", raising=False)

    def evidence_validation_is_forbidden(_):
        raise AssertionError("source reconciliation must be confirmed before evidence or database access")

    async def database_access_is_forbidden():
        raise AssertionError("source reconciliation must be confirmed before database access")

    monkeypatch.setattr(audit_seed, "_validated_audit_report_evidence_path", evidence_validation_is_forbidden)
    monkeypatch.setattr(audit_seed, "get_db", database_access_is_forbidden)
    with pytest.raises(RuntimeError, match="AUDIT_IMPORT_SOURCE_RECONCILED"):
        asyncio.run(audit_seed.seed_audit_findings())


def test_external_seed_requires_independent_source_checksum_confirmation(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", "true")
    monkeypatch.delenv("AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED", raising=False)
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_RECONCILED", "true")

    def evidence_validation_is_forbidden(_):
        raise AssertionError("source checksum must be confirmed before evidence or database access")

    async def database_access_is_forbidden():
        raise AssertionError("source checksum must be confirmed before database access")

    monkeypatch.setattr(audit_seed, "_validated_audit_report_evidence_path", evidence_validation_is_forbidden)
    monkeypatch.setattr(audit_seed, "get_db", database_access_is_forbidden)
    with pytest.raises(RuntimeError, match="AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED"):
        asyncio.run(audit_seed.seed_audit_findings())


def test_external_seed_rejects_database_outside_system_temp_directory(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_RECONCILED", "true")
    monkeypatch.setattr(database, "DB_PATH", "/var/lib/kfl-dms/dms.db")

    def evidence_validation_is_forbidden(_):
        raise AssertionError("target path must be checked before evidence or database access")

    async def database_access_is_forbidden():
        raise AssertionError("target path must be checked before database access")

    monkeypatch.setattr(audit_seed, "_validated_audit_report_evidence_path", evidence_validation_is_forbidden)
    monkeypatch.setattr(audit_seed, "get_db", database_access_is_forbidden)
    with pytest.raises(RuntimeError, match="system temp directory"):
        asyncio.run(audit_seed.seed_audit_findings())


def test_external_seed_rejects_shared_scratch_database_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_RECONCILED", "true")
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    shared_dir.chmod(0o755)
    monkeypatch.setattr(database, "DB_PATH", str(shared_dir / "dms.db"))

    def evidence_validation_is_forbidden(_):
        raise AssertionError("directory permissions must be checked before evidence or database access")

    async def database_access_is_forbidden():
        raise AssertionError("directory permissions must be checked before database access")

    monkeypatch.setattr(audit_seed, "_validated_audit_report_evidence_path", evidence_validation_is_forbidden)
    monkeypatch.setattr(audit_seed, "get_db", database_access_is_forbidden)
    with pytest.raises(RuntimeError, match="private, owner-only"):
        asyncio.run(audit_seed.seed_audit_findings())


def test_external_seed_rejects_hardlinked_database_target(tmp_path, monkeypatch):
    import os

    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_RECONCILED", "true")
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "import.db"
    source_db.write_bytes(b"do not mutate this database")
    os.link(source_db, target_db)
    monkeypatch.setattr(database, "DB_PATH", str(target_db))

    def evidence_validation_is_forbidden(_):
        raise AssertionError("hard-link targets must be rejected before evidence or database access")

    async def database_access_is_forbidden():
        raise AssertionError("hard-link targets must be rejected before database access")

    monkeypatch.setattr(audit_seed, "_validated_audit_report_evidence_path", evidence_validation_is_forbidden)
    monkeypatch.setattr(audit_seed, "get_db", database_access_is_forbidden)
    with pytest.raises(RuntimeError, match="single-link"):
        asyncio.run(audit_seed.seed_audit_findings())


def test_audit_seed_requires_evidence_pdf_before_database_access(tmp_path, monkeypatch):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    database_path = private_dir / "audit-seed.db"
    sqlite3.connect(database_path).close()
    monkeypatch.setattr(database, "DB_PATH", str(database_path))

    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_RECONCILED", "true")
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", tmp_path / "attachments")

    async def database_access_is_forbidden():
        raise AssertionError("seed must validate evidence before database access")

    monkeypatch.setattr(audit_seed, "get_db", database_access_is_forbidden)
    with pytest.raises(RuntimeError, match="authorized audit evidence PDF"):
        asyncio.run(audit_seed.seed_audit_findings())


def test_external_seed_rejects_a_different_valid_pdf_digest(tmp_path, monkeypatch):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    database_path = private_dir / "seed.db"
    sqlite3.connect(database_path).close()
    monkeypatch.setattr(database, "DB_PATH", str(database_path))

    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    evidence_name = audit_seed.AUDIT_DATA["evidence_file"].split("/", 1)[-1]
    actual_evidence = _valid_pdf_bytes("Unapproved but valid source")
    (evidence_dir / evidence_name).write_bytes(actual_evidence)
    approved_evidence = _valid_pdf_bytes("Approved source")
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_RECONCILED", "true")
    monkeypatch.setattr(audit_seed, "AUDIT_EVIDENCE_SHA256", hashlib.sha256(approved_evidence).hexdigest(), raising=False)
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir)

    async def database_access_is_forbidden():
        raise AssertionError("source digest must be checked before database access")

    monkeypatch.setattr(audit_seed, "get_db", database_access_is_forbidden)
    with pytest.raises(p3_routes.AuditEvidenceIntegrityError):
        asyncio.run(audit_seed.seed_audit_findings())


def test_external_seed_uses_only_external_audit_tables(tmp_path, monkeypatch):
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    path = private_dir / "seed.db"
    evidence_dir = tmp_path / "attachments"
    evidence_dir.mkdir()
    evidence_name = audit_seed.AUDIT_DATA["evidence_file"].split("/", 1)[-1]
    evidence = _valid_pdf_bytes()
    (evidence_dir / evidence_name).write_bytes(evidence)
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setattr(audit_seed, "AUDIT_EVIDENCE_SHA256", hashlib.sha256(evidence).hexdigest())
    monkeypatch.setenv("AUDIT_IMPORT_ENABLED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_ATTRIBUTION_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_CHECKSUM_CONFIRMED", "true")
    monkeypatch.setenv("AUDIT_IMPORT_SOURCE_RECONCILED", "true")
    monkeypatch.setattr(database, "DB_PATH", str(path))
    monkeypatch.setattr(p3_routes, "AUDIT_REPORT_EVIDENCE_DIR", evidence_dir)
    asyncio.run(database.init_db())
    asyncio.run(audit_seed.seed_audit_findings())

    conn = sqlite3.connect(path)
    try:
        external = conn.execute(
            "SELECT COUNT(*) FROM audit_findings WHERE audit_id = ?",
            (audit_seed.AUDIT_DATA["audit_id"],),
        ).fetchone()[0]
        internal = conn.execute(
            "SELECT COUNT(*) FROM quality_audit_findings WHERE audit_id = ?",
            (audit_seed.AUDIT_DATA["audit_id"],),
        ).fetchone()[0]
        report_count = conn.execute(
            "SELECT COUNT(*) FROM audit_reports WHERE audit_id = ?",
            (audit_seed.AUDIT_DATA["audit_id"],),
        ).fetchone()[0]
        imported_auditor = conn.execute(
            """SELECT r.auditor_id, u.full_name FROM audit_reports r
               JOIN users u ON u.user_id=r.auditor_id WHERE r.audit_id=?""",
            (audit_seed.AUDIT_DATA["audit_id"],),
        ).fetchone()
        quality_audit_count = conn.execute(
            "SELECT COUNT(*) FROM quality_audits WHERE audit_id = ?",
            (audit_seed.AUDIT_DATA["audit_id"],),
        ).fetchone()[0]
        report_hash = conn.execute(
            "SELECT evidence_sha256 FROM audit_reports WHERE audit_id = ?",
            (audit_seed.AUDIT_DATA["audit_id"],),
        ).fetchone()[0]
        assert external == 38
        assert internal == 0
        assert report_count == 1
        assert quality_audit_count == 0
        assert report_hash == hashlib.sha256(evidence).hexdigest()
        assert imported_auditor == (audit_seed.AUDITOR_ID, "Brian Swanya")
    finally:
        conn.close()
