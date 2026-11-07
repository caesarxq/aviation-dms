import asyncio
import os
import sqlite3
import uuid


def test_mutation_trigger_records_unlogged_hazard_create(client, safety_headers):
    created = client.post(
        "/api/p1/hazards",
        json={"title": "Audit trigger test", "description": "Must be audited atomically"},
        headers=safety_headers,
    )
    assert created.status_code == 201
    hazard_id = created.json()["hazard_id"]

    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        event = conn.execute(
            "SELECT actor_id, action FROM audit_events WHERE entity_type = 'hazards' AND entity_id = ?",
            (hazard_id,),
        ).fetchone()
        assert event == ("u-safety/security", "row_inserted")
    finally:
        conn.close()


def test_domain_mutation_and_trigger_event_rollback_together():
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    hazard_id = f"HAZ-ROLLBACK-{uuid.uuid4().hex[:8]}"
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """INSERT INTO hazards
               (hazard_id, title, description, identified_by, identified_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (hazard_id, "Rollback test", "Must not persist", "u-safety", "2026-11-02", "2026-11-02", "2026-11-02"),
        )
        conn.rollback()
        assert conn.execute("SELECT 1 FROM hazards WHERE hazard_id = ?", (hazard_id,)).fetchone() is None
        assert conn.execute(
            "SELECT 1 FROM audit_events WHERE entity_type='hazards' AND entity_id = ?", (hazard_id,)
        ).fetchone() is None
    finally:
        conn.close()


def test_existing_database_reinstalls_mutation_audit_triggers(tmp_path, monkeypatch):
    path = tmp_path / "existing.db"
    monkeypatch.setattr("app.database.DB_PATH", str(path))

    from app.database import init_db

    asyncio.run(init_db())
    conn = sqlite3.connect(path)
    try:
        conn.execute("DROP TRIGGER audit_mutation_hazards_insert")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0
    finally:
        conn.close()

    asyncio.run(init_db())
    conn = sqlite3.connect(path)
    try:
        trigger = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='audit_mutation_hazards_insert'"
        ).fetchone()
        assert trigger is not None
        conn.execute(
            "INSERT INTO hazards (hazard_id, title, description, identified_by, identified_at, created_at, updated_at) "
            "VALUES ('HAZ-REINSTALLED', 'Existing DB test', 'Trigger should be restored', 'u-admin', 'now', 'now', 'now')"
        )
        conn.commit()
        event = conn.execute(
            "SELECT actor_id, action FROM audit_events WHERE entity_type='hazards' AND entity_id='HAZ-REINSTALLED'"
        ).fetchone()
        assert event == ("u-admin", "row_inserted")
    finally:
        conn.close()
