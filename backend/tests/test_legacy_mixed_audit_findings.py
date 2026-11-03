import asyncio
import sqlite3

from app import database


def test_upgrade_splits_mixed_internal_and_external_rows_without_loss(tmp_path, monkeypatch):
    path = tmp_path / "mixed-audits.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.executescript(
        """
        INSERT INTO users (user_id,username,email,full_name,role,created_at,updated_at)
        VALUES ('u-admin','admin','admin@example.test','Admin','system_admin','created','updated');
        INSERT INTO quality_audits (audit_id,title,auditor_id,created_at,updated_at,created_by,updated_by)
        VALUES ('QA-1','Internal audit','u-admin','created','updated','u-admin','u-admin');
        INSERT INTO audit_reports (audit_id,audit_number,audit_date,auditor_id,auditee_id,created_at,updated_at)
        VALUES ('AUD-1','EXT-1','2026-01-01','u-admin','u-admin','created','updated');
        DROP TABLE audit_findings;
        CREATE TABLE audit_findings (
            finding_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, finding_number TEXT, area TEXT,
            level INTEGER, title TEXT, description TEXT NOT NULL, regulatory_reference TEXT,
            status TEXT NOT NULL, corrective_action_id TEXT, due_date TEXT, closed_at TEXT,
            closed_by TEXT, closure_evidence TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            finding_type TEXT, severity TEXT, root_cause TEXT, evidence TEXT
        );
        INSERT INTO audit_findings
            (finding_id,audit_id,finding_type,description,severity,root_cause,evidence,status,created_at,updated_at)
        VALUES ('QF-1','QA-1','nonconformity','Internal row','major','Cause','Proof','open','created','updated');
        INSERT INTO audit_findings
            (finding_id,audit_id,finding_number,area,level,title,description,status,created_at,updated_at)
        VALUES ('AF-1','AUD-1','1','Safety',2,'External row','External details','open','created','updated');
        """
    )
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT description,severity,root_cause,evidence FROM quality_audit_findings WHERE finding_id='QF-1'").fetchone() == ("Internal row", "major", "Cause", "Proof")
        assert conn.execute("SELECT finding_number,title,description FROM audit_findings WHERE finding_id='AF-1'").fetchone() == ("1", "External row", "External details")
        assert conn.execute("SELECT COUNT(*) FROM audit_findings").fetchone()[0] == 1
    finally:
        conn.close()


def test_upgrade_keeps_external_finding_when_parent_ids_collide(tmp_path, monkeypatch):
    path = tmp_path / "colliding-audit-ids.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.executescript(
        """
        INSERT INTO users (user_id,username,email,full_name,role,created_at,updated_at)
        VALUES ('u-admin','admin','admin@example.test','Admin','system_admin','created','updated');
        INSERT INTO quality_audits (audit_id,title,auditor_id,created_at,updated_at,created_by,updated_by)
        VALUES ('AUD-COLLIDE','Internal audit','u-admin','created','updated','u-admin','u-admin');
        INSERT INTO audit_reports (audit_id,audit_number,audit_date,auditor_id,auditee_id,created_at,updated_at)
        VALUES ('AUD-COLLIDE','EXT-1','2026-01-01','u-admin','u-admin','created','updated');
        DROP TABLE audit_findings;
        CREATE TABLE audit_findings (
            finding_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, finding_number TEXT, area TEXT,
            level INTEGER, title TEXT, description TEXT NOT NULL, regulatory_reference TEXT,
            status TEXT NOT NULL DEFAULT 'open', corrective_action_id TEXT, due_date TEXT,
            closed_at TEXT, closed_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            finding_type TEXT NOT NULL DEFAULT 'observation', severity TEXT NOT NULL DEFAULT 'minor',
            root_cause TEXT, evidence TEXT
        );
        INSERT INTO audit_findings
            (finding_id,audit_id,finding_number,area,level,title,description,regulatory_reference,status,created_at,updated_at)
        VALUES ('AF-EXT','AUD-COLLIDE','1','Safety',2,'External finding','Description','KCARs','open','created','updated');
        INSERT INTO audit_reports (audit_id,audit_number,audit_date,auditor_id,auditee_id,created_at,updated_at)
        VALUES ('AUD-EXT-ONLY','EXT-2','2026-01-02','u-admin','u-admin','created','updated');
        INSERT INTO audit_findings
            (finding_id,audit_id,finding_number,area,level,title,description,regulatory_reference,status,created_at,updated_at)
        VALUES ('AF-EXT-ONLY','AUD-EXT-ONLY','2','Security',2,'External-only finding','Description','KCARs','open','created','updated');
        """
    )
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        assert conn.execute(
            "SELECT finding_number,area,level,title,description,regulatory_reference FROM audit_findings WHERE finding_id='AF-EXT'"
        ).fetchone() == ("1", "Safety", 2, "External finding", "Description", "KCARs")
        assert conn.execute(
            "SELECT finding_number,area,level,title,description,regulatory_reference FROM audit_findings WHERE finding_id='AF-EXT-ONLY'"
        ).fetchone() == ("2", "Security", 2, "External-only finding", "Description", "KCARs")
        assert conn.execute("SELECT COUNT(*) FROM audit_findings").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM quality_audit_findings").fetchone()[0] == 0
    finally:
        conn.close()


def test_upgrade_still_fails_on_ambiguous_internal_row_when_parent_ids_collide(tmp_path, monkeypatch):
    path = tmp_path / "ambiguous-audit-ids.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.executescript(
        """
        INSERT INTO users (user_id,username,email,full_name,role,created_at,updated_at)
        VALUES ('u-admin','admin','admin@example.test','Admin','system_admin','created','updated');
        INSERT INTO quality_audits (audit_id,title,auditor_id,created_at,updated_at,created_by,updated_by)
        VALUES ('AUD-COLLIDE','Internal audit','u-admin','created','updated','u-admin','u-admin');
        INSERT INTO audit_reports (audit_id,audit_number,audit_date,auditor_id,auditee_id,created_at,updated_at)
        VALUES ('AUD-COLLIDE','EXT-1','2026-01-01','u-admin','u-admin','created','updated');
        DROP TABLE audit_findings;
        CREATE TABLE audit_findings (
            finding_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, finding_number TEXT, area TEXT,
            level INTEGER, title TEXT, description TEXT NOT NULL, regulatory_reference TEXT,
            status TEXT NOT NULL DEFAULT 'open', corrective_action_id TEXT, due_date TEXT,
            closed_at TEXT, closed_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            finding_type TEXT NOT NULL DEFAULT 'observation', severity TEXT NOT NULL DEFAULT 'minor',
            root_cause TEXT, evidence TEXT
        );
        INSERT INTO audit_findings
            (finding_id,audit_id,finding_type,description,severity,root_cause,status,created_at,updated_at)
        VALUES ('QF-AMBIGUOUS','AUD-COLLIDE','nonconformity','Internal finding','major','Cause','open','created','updated');
        """
    )
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    import pytest
    with pytest.raises(RuntimeError, match="audit_id exists in both audit systems"):
        asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT description FROM audit_findings WHERE finding_id='QF-AMBIGUOUS'").fetchone() == ("Internal finding",)
        assert conn.execute("SELECT COUNT(*) FROM quality_audit_findings").fetchone()[0] == 0
    finally:
        conn.close()


def test_upgrade_does_not_reclassify_external_shape_without_report_parent(tmp_path, monkeypatch):
    path = tmp_path / "external-shape-without-report.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.executescript(
        """
        INSERT INTO users (user_id,username,email,full_name,role,created_at,updated_at)
        VALUES ('u-admin','admin','admin@example.test','Admin','system_admin','created','updated');
        INSERT INTO quality_audits (audit_id,title,auditor_id,created_at,updated_at,created_by,updated_by)
        VALUES ('AUD-COLLIDE','Internal audit','u-admin','created','updated','u-admin','u-admin');
        DROP TABLE audit_findings;
        CREATE TABLE audit_findings (
            finding_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, finding_number TEXT, area TEXT,
            level INTEGER, title TEXT, description TEXT NOT NULL, regulatory_reference TEXT,
            status TEXT NOT NULL DEFAULT 'open', corrective_action_id TEXT, due_date TEXT,
            closed_at TEXT, closed_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            finding_type TEXT NOT NULL DEFAULT 'observation', severity TEXT NOT NULL DEFAULT 'minor',
            root_cause TEXT, evidence TEXT
        );
        INSERT INTO audit_findings
            (finding_id,audit_id,finding_number,area,level,title,description,regulatory_reference,status,created_at,updated_at)
        VALUES ('AF-ORPHAN','AUD-COLLIDE','1','Safety',2,'External-shaped row','Description','KCARs','open','created','updated');
        """
    )
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    import pytest
    with pytest.raises(RuntimeError, match="external finding shape has no audit report"):
        asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT finding_number,title FROM audit_findings WHERE finding_id='AF-ORPHAN'").fetchone() == ("1", "External-shaped row")
        assert conn.execute("SELECT COUNT(*) FROM quality_audit_findings").fetchone()[0] == 0
    finally:
        conn.close()
