import hashlib
import importlib
import importlib.util
import sqlite3

import pytest
from app.database import SCHEMA


def _validation_module():
    if importlib.util.find_spec("app.backup_validation") is None:
        pytest.fail("isolated backup validation is not implemented")
    return importlib.import_module("app.backup_validation")


def _candidate(root):
    for folder in ("uploads", "kcaa-evidence", "attachments"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    database = root / "dms.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT INTO users (user_id, username, email, full_name, role, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("person-a", "person-a", "person-a@example.invalid", "Test Person", "staff", "2026-11-08", "2026-11-08"),
        )
    return database


def test_isolated_backup_manifest_and_sqlite_checks_are_read_only(tmp_path):
    validation = _validation_module()
    root = tmp_path / "restore-candidate"
    root.mkdir()
    database = _candidate(root)
    evidence_path = root / "uploads" / "evidence.bin"
    evidence_bytes = b"verified test bytes"
    evidence_path.write_bytes(evidence_bytes)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO personnel_uploads "
            "(upload_id,person_id,license_type,document_type,file_name,file_path,file_size,file_sha256,created_at,updated_at,created_by,updated_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "UPL-1", "person-a", "license", "certificate", "evidence.bin", str(evidence_path),
                len(evidence_bytes), hashlib.sha256(evidence_bytes).hexdigest(), "2026-11-08", "2026-11-08",
                "person-a", "person-a",
            ),
        )
    before_hash = hashlib.sha256(database.read_bytes()).hexdigest()

    validation.write_backup_manifest(root)
    report = validation.verify_backup_candidate(root)

    assert report["read_only"] is True
    assert report["accepted"] is True
    assert report["manifest"]["matches"] is True
    assert report["sqlite"]["quick_check_ok"] is True
    assert report["sqlite"]["integrity_check_ok"] is True
    assert report["sqlite"]["foreign_key_violation_count"] == 0
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before_hash
    assert evidence_path.read_bytes() == evidence_bytes


def test_tampered_backup_fails_verification_without_repairing_it(tmp_path):
    validation = _validation_module()
    root = tmp_path / "restore-candidate"
    root.mkdir()
    _candidate(root)
    data_file = root / "attachments" / "report.pdf"
    data_file.write_bytes(b"original")
    validation.write_backup_manifest(root)
    data_file.write_bytes(b"changed")

    report = validation.verify_backup_candidate(root)

    assert report["manifest"]["matches"] is False
    assert report["accepted"] is False
    assert data_file.read_bytes() == b"changed"


def test_missing_referenced_evidence_blocks_backup_candidate(tmp_path):
    validation = _validation_module()
    root = tmp_path / "restore-candidate"
    root.mkdir()
    database = _candidate(root)
    missing_file = root / "uploads" / "missing.pdf"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO personnel_uploads "
            "(upload_id,person_id,license_type,document_type,file_name,file_path,file_size,file_sha256,created_at,updated_at,created_by,updated_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "UPL-1", "person-a", "license", "certificate", "missing.pdf", str(missing_file), 10,
                "a" * 64, "2026-11-08", "2026-11-08", "person-a", "person-a",
            ),
        )
    validation.write_backup_manifest(root)

    report = validation.verify_backup_candidate(root)

    assert report["accepted"] is False
    assert report["storage"]["tables"]["personnel_uploads"]["missing_files"] == 1


def test_backup_candidate_rejects_sqlite_file_without_core_dms_schema(tmp_path):
    validation = _validation_module()
    root = tmp_path / "restore-candidate"
    root.mkdir()
    for folder in ("uploads", "kcaa-evidence", "attachments"):
        (root / folder).mkdir()
    with sqlite3.connect(root / "dms.db") as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
    validation.write_backup_manifest(root)

    report = validation.verify_backup_candidate(root)

    assert report["accepted"] is False
    assert "required_dms_schema_missing" in report["blockers"]


def test_backup_candidate_rejects_truncated_integrity_valid_dms_schema(tmp_path):
    validation = _validation_module()
    root = tmp_path / "restore-candidate"
    root.mkdir()
    for folder in ("uploads", "kcaa-evidence", "attachments"):
        (root / folder).mkdir()
    with sqlite3.connect(root / "dms.db") as connection:
        connection.executescript(
            """
            CREATE TABLE users (user_id TEXT PRIMARY KEY);
            CREATE TABLE documents (document_id TEXT PRIMARY KEY);
            CREATE TABLE document_versions (version_id TEXT PRIMARY KEY);
            CREATE TABLE audit_events (event_id TEXT PRIMARY KEY);
            """
        )
    validation.write_backup_manifest(root)

    report = validation.verify_backup_candidate(root)

    assert report["sqlite"]["integrity_check_ok"] is True
    assert report["accepted"] is False
    assert "required_dms_schema_missing" in report["blockers"]


def test_backup_candidate_rejects_missing_required_table_column(tmp_path):
    validation = _validation_module()
    root = tmp_path / "restore-candidate"
    root.mkdir()
    for folder in ("uploads", "kcaa-evidence", "attachments"):
        (root / folder).mkdir()
    with sqlite3.connect(root / "dms.db") as connection:
        connection.executescript(SCHEMA)
        connection.execute("DROP TABLE audit_findings")
        connection.execute(
            "CREATE TABLE audit_findings "
            "(finding_id TEXT, audit_id TEXT, finding_number TEXT, title TEXT, description TEXT)"
        )
    validation.write_backup_manifest(root)

    report = validation.verify_backup_candidate(root)

    assert report["sqlite"]["integrity_check_ok"] is True
    assert report["core_schema"]["missing_column_count"] >= 1
    assert "audit_findings.status" in report["core_schema"]["missing_columns"]
    assert report["accepted"] is False
    assert "required_dms_schema_missing" in report["blockers"]


def test_corrupt_candidate_database_is_reported_without_exception(tmp_path):
    validation = _validation_module()
    root = tmp_path / "restore-candidate"
    root.mkdir()
    for folder in ("uploads", "kcaa-evidence", "attachments"):
        (root / folder).mkdir()
    (root / "dms.db").write_bytes(b"not a sqlite database")
    validation.write_backup_manifest(root)

    try:
        report = validation.verify_backup_candidate(root)
    except Exception as exc:
        pytest.fail(f"corrupt database should be returned as a blocker, not raised: {type(exc).__name__}")

    assert report["accepted"] is False
    assert "sqlite_integrity_check_failed" in report["blockers"]


def test_backup_candidate_rejects_ancestor_and_descendant_of_active_data_root(tmp_path, monkeypatch):
    validation = _validation_module()
    active_data = tmp_path / "active-data"
    nested_candidate = active_data / "uploads"
    nested_candidate.mkdir(parents=True)
    monkeypatch.setattr(validation, "ACTIVE_DEVELOPMENT_DATA_ROOT", active_data)

    with pytest.raises(ValueError, match="active development data"):
        validation._candidate_root(nested_candidate)
    with pytest.raises(ValueError, match="active development data"):
        validation._candidate_root(tmp_path)
