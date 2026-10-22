"""Audit trail service."""
from datetime import datetime
import json
import aiosqlite
from .database import get_db


async def log_audit_event(entity_type: str, entity_id: str, action: str, actor_id: str, details=None):
    db = await get_db()
    try:
        event_id = f"EVT-{__import__('uuid').uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO audit_events (event_id, entity_type, entity_id, action, actor_id, details, timestamp) VALUES (?,?,?,?,?,?,?)",
            (event_id, entity_type, entity_id, action, actor_id, json.dumps(details) if details else None, now),
        )
        await db.commit()
    finally:
        await db.close()


async def query_audit_events(entity_type=None, entity_id=None, actor_id=None, limit=100, offset=0):
    db = await get_db()
    try:
        conditions = []
        params = []
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)
        if actor_id:
            conditions.append("actor_id = ?")
            params.append(actor_id)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(
            f"SELECT * FROM audit_events WHERE {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_entity_audit_trail(entity_type: str, entity_id: str):
    return await query_audit_events(entity_type=entity_type, entity_id=entity_id)
