import sqlite3
import uuid

import pytest


def test_quality_and_external_audit_findings_use_distinct_working_tables(client, admin_headers):
    quality = client.post(
        "/api/p1/quality-audits",
        json={"title": f"quality-{uuid.uuid4().hex}", "auditor_id": "u-admin"},
        headers=admin_headers,
    )
    assert quality.status_code == 201
    quality_id = quality.json()["audit_id"]

    quality_finding = client.post(
        "/api/p1/audit-findings",
        json={"audit_id": quality_id, "description": "Quality finding"},
        headers=admin_headers,
    )
    assert quality_finding.status_code == 201
    assert quality_finding.json()["audit_id"] == quality_id

    external = client.post(
        "/api/p3/audit-reports",
        json={
            "audit_number": f"EXT-{uuid.uuid4().hex[:10]}",
            "audit_date": "2026-11-02",
            "scope": "External audit",
            "auditor_id": "u-auditor",
            "auditee_id": "u-admin",
        },
        headers=admin_headers,
    )
    assert external.status_code == 201
    external_id = external.json()["audit_id"]

    external_finding = client.post(
        "/api/p3/audit-findings",
        json={
            "audit_id": external_id,
            "finding_number": "1",
            "area": "Safety",
            "level": 2,
            "title": "External finding",
            "description": "External audit finding",
        },
        headers=admin_headers,
    )
    assert external_finding.status_code == 201
    assert external_finding.json()["audit_id"] == external_id

    conn = sqlite3.connect(__import__("os").environ["DMS_DB_PATH"])
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "audit_findings" in tables
        assert "quality_audit_findings" in tables
        quality_count = conn.execute(
            "SELECT COUNT(*) FROM quality_audit_findings WHERE audit_id = ?", (quality_id,)
        ).fetchone()[0]
        external_count = conn.execute(
            "SELECT COUNT(*) FROM audit_findings WHERE audit_id = ?", (external_id,)
        ).fetchone()[0]
        assert quality_count == 1
        assert external_count == 1
    finally:
        conn.close()


def test_quality_audit_finding_records_mutation_actor_and_semantic_event(client, admin_headers, quality_headers):
    quality = client.post(
        "/api/p1/quality-audits",
        json={"title": f"quality-{uuid.uuid4().hex}", "auditor_id": "u-admin"},
        headers=admin_headers,
    )
    assert quality.status_code == 201
    finding = client.post(
        "/api/p1/audit-findings",
        json={"audit_id": quality.json()["audit_id"], "description": "Actor attribution test"},
        headers=quality_headers,
    )
    assert finding.status_code == 201, finding.text
    finding_id = finding.json()["finding_id"]

    conn = sqlite3.connect(__import__("os").environ["DMS_DB_PATH"])
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(quality_audit_findings)")}
        assert {"created_by", "updated_by"} <= columns
        row = conn.execute(
            "SELECT created_by, updated_by FROM quality_audit_findings WHERE finding_id = ?", (finding_id,)
        ).fetchone()
        assert row == ("u-quality", "u-quality")
        events = conn.execute(
            "SELECT actor_id, action FROM audit_events WHERE entity_type='quality_audit_finding' AND entity_id=?",
            (finding_id,),
        ).fetchall()
        assert events == [("u-quality", "created")]
        trigger = conn.execute(
            "SELECT actor_id, action FROM audit_events WHERE entity_type='quality_audit_findings' AND entity_id=?",
            (finding_id,),
        ).fetchone()
        assert trigger == ("u-quality", "row_inserted")
    finally:
        conn.close()


def test_legacy_quality_findings_are_preserved_during_schema_upgrade(tmp_path, monkeypatch):
    from app.database import init_db
    import asyncio
    from app import database

    legacy_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DB_PATH", str(legacy_path))
    asyncio.run(init_db())
    upgraded = sqlite3.connect(legacy_path)
    try:
        tables = {row[0] for row in upgraded.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "audit_findings" in tables
        assert "quality_audit_findings" in tables
    finally:
        upgraded.close()

