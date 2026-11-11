import asyncio
import sqlite3

import pytest

from app import database


def _init_at(path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(path))
    asyncio.run(database.init_db())


def test_fresh_install_creates_distinct_audit_tables_and_car_foreign_key(tmp_path, monkeypatch):
    path = tmp_path / "fresh.db"
    _init_at(path, monkeypatch)
    conn = sqlite3.connect(path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"audit_reports", "audit_findings", "quality_audits", "quality_audit_findings"} <= tables
        columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_findings)")}
        assert "closure_evidence" in columns
        finding_fks = conn.execute("PRAGMA foreign_key_list(audit_findings)").fetchall()
        assert any(row[2] == "corrective_actions" and row[3] == "corrective_action_id" and row[4] == "car_id" for row in finding_fks)
    finally:
        conn.close()


def test_upgrade_adds_audit_provenance_import_table_idempotently(tmp_path, monkeypatch):
    path = tmp_path / "pre-provenance-import.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.execute(
        """INSERT INTO users (user_id, username, email, full_name, role, created_at, updated_at)
           VALUES ('u-admin', 'admin', 'admin@example.test', 'Admin', 'system_admin', 'created', 'updated')"""
    )
    conn.execute("DROP INDEX idx_audit_report_imports_status_created")
    conn.execute("DROP INDEX uq_audit_report_imports_active_number")
    conn.execute("DROP TABLE audit_report_imports")
    conn.commit()
    conn.close()

    _init_at(path, monkeypatch)
    _init_at(path, monkeypatch)

    conn = sqlite3.connect(path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "audit_report_imports" in tables
        assert conn.execute("SELECT full_name FROM users WHERE user_id='u-admin'").fetchone() == ("Admin",)
        indexes = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='audit_report_imports'"
        )}
        assert {"idx_audit_report_imports_status_created", "uq_audit_report_imports_active_number"} <= indexes
        foreign_keys = conn.execute("PRAGMA foreign_key_list(audit_report_imports)").fetchall()
        assert any(row[2] == "users" and row[3] == "source_auditor_id" for row in foreign_keys)
        assert any(row[2] == "audit_reports" and row[3] == "audit_id" for row in foreign_keys)
    finally:
        conn.close()


def test_upgrade_migrates_legacy_internal_findings_without_losing_fields(tmp_path, monkeypatch):
    path = tmp_path / "legacy-internal.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.executescript(
        """
        DROP TABLE audit_findings;
        INSERT INTO quality_audits (audit_id,title,auditor_id,created_at,updated_at,created_by,updated_by)
        VALUES ('QA-1','Legacy quality audit','u-admin','created','updated','u-admin','u-admin');
        CREATE TABLE audit_findings (
            finding_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, finding_type TEXT NOT NULL,
            description TEXT NOT NULL, severity TEXT NOT NULL, root_cause TEXT, evidence TEXT,
            status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO audit_findings VALUES
            ('QF-1', 'QA-1', 'nonconformity', 'Internal description', 'major', 'Cause', 'Proof', 'open', 'created', 'updated');
        """
    )
    conn.close()

    _init_at(path, monkeypatch)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT finding_id, audit_id, finding_type, description, severity, root_cause, evidence, status, created_at, updated_at FROM quality_audit_findings WHERE finding_id='QF-1'"
        ).fetchone()
        assert row == ("QF-1", "QA-1", "nonconformity", "Internal description", "major", "Cause", "Proof", "open", "created", "updated")
        assert conn.execute("SELECT COUNT(*) FROM audit_findings").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM audit_findings__legacy").fetchone()[0] == 0 if conn.execute("SELECT name FROM sqlite_master WHERE name='audit_findings__legacy'").fetchone() else True
    finally:
        conn.close()


def test_upgrade_rebuilds_legacy_external_finding_foreign_key_and_preserves_rows(tmp_path, monkeypatch):
    path = tmp_path / "legacy-external.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.executescript(
        """
        DROP TABLE audit_findings;
        INSERT INTO users (user_id,username,email,full_name,role,created_at,updated_at)
        VALUES ('u-admin','admin','admin@example.test','Admin','system_admin','created','updated');
        INSERT INTO audit_reports (audit_id,audit_number,audit_date,auditor_id,auditee_id,created_at,updated_at)
        VALUES ('AUD-1','AUD-1','2026-01-01','u-admin','u-admin','created','updated');
        INSERT INTO corrective_actions (car_id,title,description,owner_id,created_at,updated_at,created_by,updated_by)
        VALUES ('CAR-1','Action','Action details','u-admin','created','updated','u-admin','u-admin');
        CREATE TABLE audit_findings (
            finding_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, finding_number TEXT NOT NULL,
            area TEXT NOT NULL, level INTEGER NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
            regulatory_reference TEXT, status TEXT NOT NULL DEFAULT 'open', corrective_action_id TEXT,
            due_date TEXT, closed_at TEXT, closed_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY (audit_id) REFERENCES audit_reports(audit_id),
            FOREIGN KEY (corrective_action_id) REFERENCES change_requests(cr_id)
        );
        INSERT INTO audit_findings (finding_id,audit_id,finding_number,area,level,title,description,status,corrective_action_id,created_at,updated_at)
        VALUES ('AF-1','AUD-1','1','Safety',2,'Finding','Description','open','CAR-1','created','updated');
        """
    )
    conn.close()

    _init_at(path, monkeypatch)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT finding_id, audit_id, finding_number, title, description, corrective_action_id FROM audit_findings WHERE finding_id='AF-1'").fetchone()
        assert row == ("AF-1", "AUD-1", "1", "Finding", "Description", "CAR-1")
        fks = conn.execute("PRAGMA foreign_key_list(audit_findings)").fetchall()
        assert any(row[2] == "corrective_actions" and row[3] == "corrective_action_id" and row[4] == "car_id" for row in fks)
        assert conn.execute("PRAGMA foreign_key_check(audit_findings)").fetchall() == []
    finally:
        conn.close()


def test_upgrade_rejects_unmappable_legacy_change_request_links_without_deleting_rows(tmp_path, monkeypatch):
    path = tmp_path / "unmapped-car.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.executescript(
        """
        DROP TABLE audit_findings;
        INSERT INTO users (user_id,username,email,full_name,role,created_at,updated_at)
        VALUES ('u-admin','admin','admin@example.test','Admin','system_admin','created','updated');
        INSERT INTO audit_reports (audit_id,audit_number,audit_date,auditor_id,auditee_id,created_at,updated_at)
        VALUES ('AUD-1','AUD-1','2026-01-01','u-admin','u-admin','created','updated');
        INSERT INTO change_requests (cr_id,document_id,title,description,requester_id,created_at,updated_at,created_by,updated_by)
        VALUES ('CR-1','DOC-1','Change','Description','u-admin','created','updated','u-admin','u-admin');
        CREATE TABLE audit_findings (
            finding_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, finding_number TEXT NOT NULL,
            area TEXT NOT NULL, level INTEGER NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
            regulatory_reference TEXT, status TEXT NOT NULL DEFAULT 'open', corrective_action_id TEXT,
            due_date TEXT, closed_at TEXT, closed_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY (audit_id) REFERENCES audit_reports(audit_id),
            FOREIGN KEY (corrective_action_id) REFERENCES change_requests(cr_id)
        );
        INSERT INTO audit_findings (finding_id,audit_id,finding_number,area,level,title,description,corrective_action_id,created_at,updated_at)
        VALUES ('AF-CR','AUD-1','1','Safety',2,'Finding','Description','CR-1','created','updated');
        """
    )
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    with pytest.raises(RuntimeError, match="no matching corrective_actions.car_id"):
        asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT corrective_action_id FROM audit_findings WHERE finding_id='AF-CR'").fetchone() == ("CR-1",)
        assert not any(row[2] == "corrective_actions" for row in conn.execute("PRAGMA foreign_key_list(audit_findings)"))
    finally:
        conn.close()


def test_upgrade_fails_without_deleting_unclassifiable_legacy_rows(tmp_path, monkeypatch):
    path = tmp_path / "orphan.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.executescript(
        """
        DROP TABLE audit_findings;
        CREATE TABLE audit_findings (
            finding_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, finding_type TEXT NOT NULL,
            description TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO audit_findings VALUES ('ORPHAN','NO-PARENT','observation','Preserve me','minor','open','created','updated');
        """
    )
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    with pytest.raises(RuntimeError, match="cannot classify legacy audit finding ORPHAN"):
        asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT description FROM audit_findings WHERE finding_id='ORPHAN'").fetchone() == ("Preserve me",)
    finally:
        conn.close()


def test_existing_quality_findings_get_actor_columns_without_losing_rows(tmp_path, monkeypatch):
    from app import database
    import asyncio

    path = tmp_path / "pre-actor-columns.db"
    actor_columns = "    created_by TEXT NOT NULL DEFAULT 'system',\n    updated_by TEXT NOT NULL DEFAULT 'system',\n"
    legacy_schema = database.SCHEMA.replace(actor_columns, "", 1)
    assert legacy_schema != database.SCHEMA
    conn = sqlite3.connect(path)
    conn.executescript(legacy_schema)
    conn.execute(
        "INSERT INTO users (user_id, username, email, full_name, role, created_at, updated_at) VALUES ('u-admin', 'admin', 'admin@example.test', 'Admin', 'system_admin', 'created', 'updated')"
    )
    conn.execute(
        "INSERT INTO quality_audits (audit_id, title, auditor_id, created_at, updated_at, created_by, updated_by) VALUES ('QA-OLD', 'Legacy audit', 'u-admin', 'created', 'updated', 'u-admin', 'u-admin')"
    )
    conn.execute(
        "INSERT INTO quality_audit_findings (finding_id, audit_id, finding_type, description, severity, status, created_at, updated_at) VALUES ('QF-OLD', 'QA-OLD', 'observation', 'Preserve me', 'minor', 'open', 'created', 'updated')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(quality_audit_findings)")}
        assert {"created_by", "updated_by"} <= columns
        assert conn.execute(
            "SELECT description, created_by, updated_by FROM quality_audit_findings WHERE finding_id='QF-OLD'"
        ).fetchone() == ("Preserve me", "system", "system")
    finally:
        conn.close()
