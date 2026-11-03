import asyncio
import sqlite3

from app import database
from app import seed_audit_findings


def test_external_seed_uses_only_external_audit_tables(tmp_path, monkeypatch):
    path = tmp_path / "seed.db"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    asyncio.run(database.init_db())
    asyncio.run(seed_audit_findings.seed_audit_findings())

    conn = sqlite3.connect(path)
    try:
        external = conn.execute("SELECT COUNT(*) FROM audit_findings WHERE audit_id = ?", (seed_audit_findings.AUDIT_DATA["audit_id"],)).fetchone()[0]
        internal = conn.execute("SELECT COUNT(*) FROM quality_audit_findings WHERE audit_id = ?", (seed_audit_findings.AUDIT_DATA["audit_id"],)).fetchone()[0]
        report_count = conn.execute("SELECT COUNT(*) FROM audit_reports WHERE audit_id = ?", (seed_audit_findings.AUDIT_DATA["audit_id"],)).fetchone()[0]
        quality_audit_count = conn.execute("SELECT COUNT(*) FROM quality_audits WHERE audit_id = ?", (seed_audit_findings.AUDIT_DATA["audit_id"],)).fetchone()[0]
        assert external == len(seed_audit_findings.FINDINGS)
        assert internal == 0
        assert report_count == 1
        assert quality_audit_count == 0
    finally:
        conn.close()
