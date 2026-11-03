import asyncio
import sqlite3

import pytest

from app import database


def test_init_db_is_idempotent_when_migration_columns_already_exist(tmp_path, monkeypatch):
    path = tmp_path / "already-upgraded.db"
    monkeypatch.setattr(database, "DB_PATH", str(path))

    asyncio.run(database.init_db())
    asyncio.run(database.init_db())

    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
    assert {"kcaa_approval_required", "review_due_date", "source_sha256"} <= columns


def test_init_db_propagates_operational_column_migration_failure(tmp_path, monkeypatch):
    path = tmp_path / "column-migration-failure.db"
    legacy_schema = database.SCHEMA.replace("    change_set_id TEXT,\n", "", 1).replace("    source_sha256 TEXT,\n", "", 1)
    assert legacy_schema != database.SCHEMA
    with sqlite3.connect(path) as conn:
        conn.executescript(legacy_schema)
    monkeypatch.setattr(database, "DB_PATH", str(path))

    original_get_db = database.get_db
    get_db_calls = 0

    class FailingConnection:
        def __init__(self, connection):
            self.connection = connection

        async def execute(self, sql, *args, **kwargs):
            if sql.replace('"', "") == "ALTER TABLE documents ADD COLUMN source_sha256 TEXT":
                raise sqlite3.OperationalError("database is locked")
            return await self.connection.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.connection, name)

    async def get_db_with_locked_migration():
        nonlocal get_db_calls
        get_db_calls += 1
        connection = await original_get_db()
        if get_db_calls == 2:
            return FailingConnection(connection)
        return connection

    monkeypatch.setattr(database, "get_db", get_db_with_locked_migration)

    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        asyncio.run(database.init_db())

    with sqlite3.connect(path) as conn:
        proposal_columns = {row[1] for row in conn.execute("PRAGMA table_info(document_proposals)")}
        document_columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
    assert "change_set_id" not in proposal_columns
    assert "source_sha256" not in document_columns


def test_init_db_rolls_back_initial_schema_when_precommit_migration_fails(tmp_path, monkeypatch):
    path = tmp_path / "initial-schema-rollback.db"
    monkeypatch.setattr(database, "DB_PATH", str(path))

    async def fail_after_schema(_db):
        raise RuntimeError("forced initial migration failure")

    monkeypatch.setattr(database, "_ensure_unique_mission_lifecycle_indexes", fail_after_schema)

    with pytest.raises(RuntimeError, match="forced initial migration failure"):
        asyncio.run(database.init_db())

    with sqlite3.connect(path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert tables == set()


def test_audit_report_unique_index_fails_with_duplicate_data_message(tmp_path):
    path = tmp_path / "duplicate-audit-report-ids.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE audit_reports (audit_id TEXT NOT NULL)")
        conn.executemany("INSERT INTO audit_reports (audit_id) VALUES (?)", [("AUD-1",), ("AUD-1",)])

    async def create_index():
        db = await database.aiosqlite.connect(str(path))
        db.row_factory = database.aiosqlite.Row
        try:
            await database._ensure_unique_audit_report_index(db)
        finally:
            await db.close()

    with pytest.raises(RuntimeError, match=r"duplicate audit ID AUD-1.*reconcile"):
        asyncio.run(create_index())


def test_audit_report_unique_index_fails_with_null_data_message(tmp_path):
    path = tmp_path / "null-audit-report-id.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE audit_reports (audit_id TEXT)")
        conn.execute("INSERT INTO audit_reports (audit_id) VALUES (NULL)")

    async def create_index():
        db = await database.aiosqlite.connect(str(path))
        db.row_factory = database.aiosqlite.Row
        try:
            await database._ensure_unique_audit_report_index(db)
        finally:
            await db.close()

    with pytest.raises(RuntimeError, match=r"NULL audit ID.*reconcile"):
        asyncio.run(create_index())


def test_init_db_migrates_legacy_audit_report_key_before_audit_findings_fk_check(tmp_path, monkeypatch):
    path = tmp_path / "legacy-audit-report-key.db"
    legacy_schema = database.SCHEMA.replace(
        "CREATE TABLE IF NOT EXISTS audit_reports (\n    audit_id TEXT PRIMARY KEY,",
        "CREATE TABLE IF NOT EXISTS audit_reports (\n    audit_id TEXT,",
        1,
    )
    assert legacy_schema != database.SCHEMA
    with sqlite3.connect(path) as conn:
        conn.executescript(legacy_schema)
        conn.execute(
            """INSERT INTO audit_reports
               (audit_id, audit_number, audit_date, auditor_id, auditee_id, created_at, updated_at)
               VALUES ('AUD-LEGACY', 'AN-LEGACY', '2025-01-01', 'auditor', 'auditee', 'now', 'now')"""
        )
        conn.execute(
            """INSERT INTO audit_findings
               (finding_id, audit_id, finding_number, area, level, title, description, created_at, updated_at)
               VALUES ('F-LEGACY', 'AUD-LEGACY', '1', 'operations', 1, 'Legacy finding', 'existing record', 'now', 'now')"""
        )
    monkeypatch.setattr(database, "DB_PATH", str(path))

    asyncio.run(database.init_db())

    with sqlite3.connect(path) as conn:
        indexes = {
            row[1]: row[2]
            for row in conn.execute("PRAGMA index_list(audit_reports)")
        }
        finding = conn.execute(
            "SELECT finding_id, audit_id FROM audit_findings WHERE finding_id = 'F-LEGACY'"
        ).fetchone()
        violations = conn.execute("PRAGMA foreign_key_check(audit_findings)").fetchall()
    assert indexes.get("idx_audit_reports_audit_id") == 1
    assert finding == ("F-LEGACY", "AUD-LEGACY")
    assert violations == []
