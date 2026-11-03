import asyncio
import sqlite3

from app import database


def test_upgrade_adds_kcaa_evidence_hash_column_without_losing_document_versions(tmp_path, monkeypatch):
    path = tmp_path / "pre-kcaa-hash.db"
    old_schema = database.SCHEMA.replace("    kcaa_evidence_sha256 TEXT,\n", "").replace("    kcaa_evidence_id TEXT,\n", "")
    conn = sqlite3.connect(path)
    conn.executescript(old_schema)
    conn.execute(
        """INSERT INTO documents (document_id,title,doc_class,status,owner_id,created_at,updated_at,created_by,updated_by)
           VALUES ('DOC-OLD','Legacy manual','manual','draft','u-admin','created','updated','u-admin','u-admin')"""
    )
    conn.execute(
        """INSERT INTO document_versions (version_id,document_id,version_number,state,created_at,updated_at,created_by,updated_by)
           VALUES ('VER-OLD','DOC-OLD','1','draft','created','updated','u-admin','u-admin')"""
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(document_versions)")}
        assert "kcaa_evidence_sha256" in cols
        assert "kcaa_evidence_id" in cols
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kcaa_approval_evidence'").fetchone() == ("kcaa_approval_evidence",)
        assert conn.execute("SELECT version_id, document_id, kcaa_evidence_sha256, kcaa_evidence_id FROM document_versions WHERE version_id='VER-OLD'").fetchone() == ("VER-OLD", "DOC-OLD", None, None)
    finally:
        conn.close()
