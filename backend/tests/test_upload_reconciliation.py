import hashlib
import importlib
import importlib.util
import inspect
import sqlite3

import pytest


def _reconciliation_module():
    if importlib.util.find_spec("app.upload_reconciliation") is None:
        pytest.fail("read-only upload reconciliation is not implemented")
    return importlib.import_module("app.upload_reconciliation")


def test_upload_reconciliation_reports_orphans_without_mutating_database_or_files(tmp_path):
    reconcile = _reconciliation_module().reconcile_upload_storage
    database = tmp_path / "dms.db"
    uploads = tmp_path / "uploads"
    kcaa = tmp_path / "kcaa-evidence"
    attachments = tmp_path / "attachments"
    uploads.mkdir()
    attachments.mkdir()
    registered = uploads / "registered.bin"
    registered.write_bytes(b"abc")
    orphan = uploads / "orphan.bin"
    orphan.write_bytes(b"x")
    unattached = attachments / "unreferenced.pdf"
    unattached.write_bytes(b"pdf")

    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE personnel_uploads (
                upload_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                file_size INTEGER
            );
            CREATE TABLE kcaa_approval_evidence (
                evidence_id TEXT PRIMARY KEY,
                stored_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                file_sha256 TEXT
            );
            CREATE TABLE audit_reports (evidence_file TEXT);
            """
        )
        connection.execute(
            "INSERT INTO personnel_uploads (upload_id, file_path, file_size) VALUES (?, ?, ?)",
            ("UPL-1", str(registered), 3),
        )
        connection.execute(
            "INSERT INTO kcaa_approval_evidence (evidence_id, stored_filename, file_path, file_size, file_sha256) VALUES (?, ?, ?, ?, ?)",
            ("KCAA-1", "missing.pdf", str(kcaa / "missing.pdf"), 8, "a" * 64),
        )
        connection.execute(
            "INSERT INTO audit_reports (evidence_file) VALUES (?)",
            ("attachments/missing-audit.pdf",),
        )

    before_hash = hashlib.sha256(database.read_bytes()).hexdigest()
    report = reconcile(database, uploads, kcaa, attachments)

    assert report["read_only"] is True
    assert report["tables"]["personnel_uploads"]["missing_files"] == 0
    assert report["tables"]["personnel_uploads"]["digest_column_present"] is False
    assert report["tables"]["kcaa_approval_evidence"]["missing_files"] == 1
    assert report["tables"]["audit_reports"]["missing_files"] == 1
    assert report["tables"]["audit_report_imports"]["table_present"] is False
    assert report["roots"]["uploads"]["unreferenced_files"] == 1
    assert report["roots"]["attachments"]["unreferenced_files"] == 1
    assert registered.read_bytes() == b"abc"
    assert orphan.read_bytes() == b"x"
    assert unattached.read_bytes() == b"pdf"
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before_hash


def test_upload_reconciliation_flags_symlinks_without_following_them(tmp_path):
    reconcile = _reconciliation_module().reconcile_upload_storage
    database = tmp_path / "dms.db"
    uploads = tmp_path / "uploads"
    kcaa = tmp_path / "kcaa-evidence"
    attachments = tmp_path / "attachments"
    uploads.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"do not read")
    (uploads / "link.bin").symlink_to(outside)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE personnel_uploads (upload_id TEXT, file_path TEXT, file_size INTEGER)")

    report = reconcile(database, uploads, kcaa, attachments)

    assert report["roots"]["uploads"]["symlink_entries"] == 1
    assert report["roots"]["uploads"]["file_count"] == 0
    assert outside.read_bytes() == b"do not read"


def test_optional_hash_audit_detects_mismatch_without_modifying_data(tmp_path):
    module = _reconciliation_module()
    reconcile = module.reconcile_upload_storage
    if "verify_hashes" not in inspect.signature(reconcile).parameters:
        pytest.fail("optional stored-file digest verification is not implemented")

    database = tmp_path / "dms.db"
    uploads = tmp_path / "uploads"
    kcaa = tmp_path / "kcaa-evidence"
    attachments = tmp_path / "attachments"
    uploads.mkdir()
    evidence = uploads / "file.bin"
    evidence.write_bytes(b"actual bytes")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE personnel_uploads (upload_id TEXT, file_path TEXT, file_size INTEGER, file_sha256 TEXT)"
        )
        connection.execute(
            "INSERT INTO personnel_uploads VALUES (?, ?, ?, ?)",
            ("UPL-1", str(evidence), len(b"actual bytes"), "0" * 64),
        )
    before_hash = hashlib.sha256(database.read_bytes()).hexdigest()

    report = reconcile(database, uploads, kcaa, attachments, verify_hashes=True)

    assert report["tables"]["personnel_uploads"]["hashes_checked"] == 1
    assert report["tables"]["personnel_uploads"]["hash_mismatches"] == 1
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before_hash
    assert evidence.read_bytes() == b"actual bytes"
