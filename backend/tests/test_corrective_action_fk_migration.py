import asyncio
import sqlite3

from app import database


def test_upgrade_retargets_corrective_action_finding_fk_and_preserves_car(tmp_path, monkeypatch):
    path = tmp_path / "legacy-car.db"
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
            ('QF-1','QA-1','nonconformity','Internal description','major','Cause','Proof','open','created','updated');
        DROP TABLE corrective_actions;
        CREATE TABLE corrective_actions (
            car_id TEXT PRIMARY KEY, finding_id TEXT, audit_id TEXT, title TEXT NOT NULL,
            description TEXT NOT NULL, finding_level TEXT NOT NULL DEFAULT 'level_2', root_cause TEXT,
            corrective_action TEXT, preventive_action TEXT, owner_id TEXT NOT NULL, due_date TEXT,
            status TEXT NOT NULL DEFAULT 'open', verification TEXT, verified_by TEXT, verified_at TEXT,
            closed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            created_by TEXT NOT NULL, updated_by TEXT NOT NULL,
            FOREIGN KEY (finding_id) REFERENCES audit_findings(finding_id),
            FOREIGN KEY (audit_id) REFERENCES quality_audits(audit_id)
        );
        INSERT INTO corrective_actions (car_id,finding_id,audit_id,title,description,owner_id,created_at,updated_at,created_by,updated_by)
        VALUES ('CAR-1','QF-1','QA-1','Action','Action details','u-admin','created','updated','u-admin','u-admin');
        """
    )
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT car_id,finding_id,audit_id,title FROM corrective_actions WHERE car_id='CAR-1'").fetchone() == ("CAR-1", "QF-1", "QA-1", "Action")
        fks = conn.execute("PRAGMA foreign_key_list(corrective_actions)").fetchall()
        assert any(row[2] == "quality_audit_findings" and row[3] == "finding_id" and row[4] == "finding_id" for row in fks)
        assert conn.execute("PRAGMA foreign_key_check(corrective_actions)").fetchall() == []
    finally:
        conn.close()
