import asyncio
import os
import sqlite3

import pytest

from app.audit import log_audit_event
from app.database import get_db


class TestAuditTrail:
    def test_list_audit_events(self, client, admin_headers):
        resp = client.get("/api/p0/audit-events", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_filter_by_entity_type(self, client, admin_headers):
        resp = client.get("/api/p0/audit-events", params={"entity_type": "document"}, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["entity_type"] == "document" for e in data)

    def test_filter_by_entity_id(self, client, admin_headers):
        resp = client.get("/api/p0/audit-events", params={"entity_id": "DOC-001"}, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["entity_id"] == "DOC-001" for e in data)

    def test_audit_event_fields(self, client, admin_headers):
        resp = client.get("/api/p0/audit-events", params={"limit": 1}, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        if len(data) > 0:
            event = data[0]
            assert "event_id" in event
            assert "entity_type" in event
            assert "entity_id" in event
            assert "action" in event
            assert "actor_id" in event
            assert "timestamp" in event

    def test_unauthorized_access_denied(self, client):
        resp = client.get("/api/p0/audit-events", headers={"X-Role": "unknown", "X-Actor": "nobody"})
        assert resp.status_code in (401, 403)

    def test_event_can_share_domain_transaction_and_roll_back_atomically(self):
        entity_id = "atomic-audit-test"

        async def write_then_rollback():
            db = await get_db()
            try:
                await db.execute("BEGIN IMMEDIATE")
                await log_audit_event("test_entity", entity_id, "changed", "u-admin", {"field": "status"}, db=db)
                await db.rollback()
            finally:
                await db.close()

        asyncio.run(write_then_rollback())
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            assert conn.execute(
                "SELECT 1 FROM audit_events WHERE entity_type = 'test_entity' AND entity_id = ?", (entity_id,)
            ).fetchone() is None
        finally:
            conn.close()
