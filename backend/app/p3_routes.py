"""P3 API routes for external audit reports and their findings."""

import json
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from .database import get_db
from .rbac import has_permission

router = APIRouter()


class ReportStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    closed = "closed"
    cancelled = "cancelled"


class FindingStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    closed = "closed"


class AuditReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_number: Optional[str] = Field(default=None, min_length=1, max_length=100)
    audit_date: Optional[date] = None
    auditor_id: str = Field(min_length=1, max_length=100)
    auditee_id: str = Field(min_length=1, max_length=100)
    scope: Optional[str] = Field(default=None, max_length=2000)
    regulatory_basis: Optional[str] = Field(default=None, max_length=2000)
    status: ReportStatus = ReportStatus.open
    evidence_file: Optional[str] = Field(default=None, max_length=1000)


class AuditFindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_id: str = Field(min_length=1, max_length=100)
    finding_number: str = Field(min_length=1, max_length=50)
    area: str = Field(min_length=1, max_length=200)
    level: int = Field(ge=1, le=4)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=10000)
    regulatory_reference: Optional[str] = Field(default=None, max_length=2000)
    due_date: Optional[date] = None


class AuditFindingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    area: Optional[str] = Field(default=None, min_length=1, max_length=200)
    level: Optional[int] = Field(default=None, ge=1, le=4)
    regulatory_reference: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[FindingStatus] = None
    due_date: Optional[date] = None
    corrective_action_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    closure_evidence: Optional[str] = Field(default=None, min_length=1, max_length=5000)


class CorrectiveActionLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corrective_action_id: Optional[str] = Field(default=None, min_length=1, max_length=100)


def _actor(request: Request) -> str:
    return getattr(request.state, "actor", "") or ""


def _role(request: Request) -> str:
    return getattr(request.state, "role", "") or ""


def _check(request: Request, permission: str) -> None:
    if not has_permission(_role(request), permission):
        raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


async def _write_event(db, entity_type: str, entity_id: str, action: str, actor_id: str, details=None) -> None:
    """Persist the P3 audit trail inside the same transaction as the mutation."""
    await db.execute(
        """INSERT INTO audit_events (event_id, entity_type, entity_id, action, actor_id, details, timestamp)
           VALUES (?,?,?,?,?,?,?)""",
        (
            f"EVT-{uuid.uuid4().hex[:12]}", entity_type, entity_id, action, actor_id,
            json.dumps(details, separators=(",", ":")) if details else None, _now(),
        ),
    )


@router.post("/audit-reports", status_code=201)
async def create_audit_report(payload: AuditReportCreate, request: Request):
    _check(request, "audit_report:create")
    actor = _actor(request)
    audit_id = _gen_id("AUD")
    now = _now()
    audit_number = payload.audit_number or f"AUD-{uuid.uuid4().hex[:6].upper()}"
    audit_date = _date(payload.audit_date) or now[:10]
    auditor_id = payload.auditor_id.strip()
    auditee_id = payload.auditee_id.strip()
    if not auditor_id or not auditee_id:
        raise HTTPException(status_code=422, detail="Auditor and auditee are required")
    if auditor_id == auditee_id:
        raise HTTPException(status_code=422, detail="Auditor and auditee must be different people")
    db = await get_db()
    try:
        auditor = await (await db.execute(
            """SELECT u.user_id FROM users u JOIN user_roles ur ON ur.user_id = u.user_id
               WHERE u.user_id = ? AND u.is_active = 1 AND ur.role = 'independent_auditor'""",
            (auditor_id,),
        )).fetchone()
        if not auditor:
            raise HTTPException(status_code=403, detail="Auditor must be an active user assigned the independent_auditor role")
        auditee = await (await db.execute(
            "SELECT user_id FROM users WHERE user_id = ? AND is_active = 1", (auditee_id,)
        )).fetchone()
        if not auditee:
            raise HTTPException(status_code=404, detail=f"Active auditee not found: {auditee_id}")
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """INSERT INTO audit_reports
               (audit_id, audit_number, audit_date, auditor_id, auditee_id, scope, regulatory_basis,
                status, evidence_file, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                audit_id, audit_number, audit_date, auditor_id, auditee_id, payload.scope,
                payload.regulatory_basis, payload.status.value, payload.evidence_file, now, now,
            ),
        )
        await _write_event(db, "audit_report", audit_id, "created", actor, {"audit_number": audit_number})
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
    return {"audit_id": audit_id, "audit_number": audit_number, "status": payload.status.value, "created_at": now}


@router.get("/audit-reports")
async def list_audit_reports(
    request: Request,
    status: Optional[ReportStatus] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
):
    _check(request, "audit_report:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute(
                "SELECT * FROM audit_reports WHERE status = ? ORDER BY audit_date DESC LIMIT ? OFFSET ?",
                (status.value, limit, offset),
            )
        else:
            cursor = await db.execute("SELECT * FROM audit_reports ORDER BY audit_date DESC LIMIT ? OFFSET ?", (limit, offset))
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


@router.post("/audit-findings", status_code=201)
async def create_audit_finding(payload: AuditFindingCreate, request: Request):
    _check(request, "audit_finding:create")
    actor = _actor(request)
    finding_id = _gen_id("AF")
    now = _now()
    db = await get_db()
    try:
        report = await (await db.execute("SELECT audit_id FROM audit_reports WHERE audit_id = ?", (payload.audit_id,))).fetchone()
        if not report:
            raise HTTPException(status_code=404, detail="Audit report not found")
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """INSERT INTO audit_findings
               (finding_id, audit_id, finding_number, area, level, title, description,
                regulatory_reference, status, due_date, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                finding_id, payload.audit_id, payload.finding_number, payload.area, payload.level,
                payload.title, payload.description, payload.regulatory_reference, FindingStatus.open.value,
                _date(payload.due_date), now, now,
            ),
        )
        await _write_event(db, "audit_finding", finding_id, "created", actor, {"finding_number": payload.finding_number})
        await db.commit()
        row = await (await db.execute("SELECT * FROM audit_findings WHERE finding_id = ?", (finding_id,))).fetchone()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
    return dict(row)


@router.get("/audit-findings")
async def list_audit_findings(
    request: Request,
    audit_id: Optional[str] = Query(default=None, min_length=1, max_length=100),
    status: Optional[FindingStatus] = None,
    level: Optional[int] = Query(default=None, ge=1, le=4),
    area: Optional[str] = Query(default=None, min_length=1, max_length=200),
    search: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
):
    _check(request, "audit_finding:read")
    conditions = []
    params = []
    if audit_id:
        conditions.append("audit_id = ?")
        params.append(audit_id)
    if status:
        conditions.append("status = ?")
        params.append(status.value)
    if level is not None:
        conditions.append("level = ?")
        params.append(level)
    if area:
        conditions.append("area = ?")
        params.append(area)
    if search and search.strip():
        search_pattern = f"%{search.strip().lower()}%"
        conditions.append(
            "(LOWER(finding_number) LIKE ? OR LOWER(area) LIKE ? OR LOWER(title) LIKE ? "
            "OR LOWER(description) LIKE ? OR LOWER(COALESCE(regulatory_reference, '')) LIKE ?)"
        )
        params.extend([search_pattern] * 5)
    where = " AND ".join(conditions) if conditions else "1=1"
    db = await get_db()
    try:
        cursor = await db.execute(
            f"SELECT * FROM audit_findings WHERE {where} ORDER BY finding_number, finding_id LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


@router.patch("/audit-findings/{finding_id}")
async def update_audit_finding(finding_id: str, payload: AuditFindingUpdate, request: Request):
    _check(request, "audit_finding:update")
    fields = payload.model_fields_set
    closure_evidence = ""
    if not fields:
        raise HTTPException(status_code=422, detail="At least one finding field must be supplied")
    if "status" in fields and payload.status is not None and payload.status.value == FindingStatus.closed.value:
        _check(request, "audit_finding:close")
        closure_evidence = payload.closure_evidence or ""
        if not closure_evidence.strip():
            raise HTTPException(status_code=422, detail="closure_evidence is required to close a finding")
    elif "closure_evidence" in fields:
        raise HTTPException(status_code=422, detail="closure_evidence may only be supplied while closing a finding")

    actor = _actor(request)
    now = _now()
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute("SELECT * FROM audit_findings WHERE finding_id = ?", (finding_id,))).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Audit finding not found")
        current = dict(row)
        updates = {}
        for field in ("title", "description", "area", "level", "regulatory_reference", "due_date", "corrective_action_id"):
            if field in fields:
                value = getattr(payload, field)
                updates[field] = _date(value) if field == "due_date" else value
        if "status" in fields and payload.status is not None:
            new_status = payload.status.value
            old_status = current["status"]
            transitions = {"open": {"in_progress"}, "in_progress": {"closed"}, "closed": set()}
            if new_status != old_status and new_status not in transitions.get(old_status, set()):
                raise HTTPException(status_code=409, detail=f"Invalid finding status transition: {old_status} -> {new_status}")
            if new_status == FindingStatus.closed.value:
                updates.update(
                    status=new_status,
                    closure_evidence=closure_evidence.strip(),
                    closed_at=now,
                    closed_by=actor,
                )
            else:
                updates["status"] = new_status
        if "corrective_action_id" in updates and updates["corrective_action_id"]:
            car = await (await db.execute("SELECT car_id FROM corrective_actions WHERE car_id = ?", (updates["corrective_action_id"],))).fetchone()
            if not car:
                raise HTTPException(status_code=404, detail="Corrective action not found")
        if updates:
            updates["updated_at"] = now
            assignments = ", ".join(f"{column} = ?" for column in updates)
            await db.execute(
                f"UPDATE audit_findings SET {assignments} WHERE finding_id = ?",
                [*updates.values(), finding_id],
            )
        await _write_event(db, "audit_finding", finding_id, "updated", actor, {"fields": sorted(updates)})
        await db.commit()
        result = await (await db.execute("SELECT * FROM audit_findings WHERE finding_id = ?", (finding_id,))).fetchone()
        return dict(result)
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


@router.post("/audit-findings/{finding_id}/car")
async def link_corrective_action(finding_id: str, payload: CorrectiveActionLink, request: Request):
    _check(request, "audit_finding:update")
    actor = _actor(request)
    now = _now()
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        finding = await (await db.execute("SELECT finding_id FROM audit_findings WHERE finding_id = ?", (finding_id,))).fetchone()
        if not finding:
            raise HTTPException(status_code=404, detail="Audit finding not found")
        car_id = payload.corrective_action_id
        if car_id:
            car = await (await db.execute("SELECT car_id FROM corrective_actions WHERE car_id = ?", (car_id,))).fetchone()
            if not car:
                raise HTTPException(status_code=404, detail="Corrective action not found")
        await db.execute(
            "UPDATE audit_findings SET corrective_action_id = ?, updated_at = ? WHERE finding_id = ?",
            (car_id, now, finding_id),
        )
        await _write_event(db, "audit_finding", finding_id, "car_linked", actor, {"corrective_action_id": car_id})
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
    return {"finding_id": finding_id, "corrective_action_id": car_id}


@router.get("/audit-findings/summary")
async def audit_findings_summary(request: Request):
    _check(request, "audit_finding:read")
    db = await get_db()
    try:
        by_level_rows = await (await db.execute("SELECT level, COUNT(*) AS count FROM audit_findings GROUP BY level")).fetchall()
        by_status_rows = await (await db.execute("SELECT status, COUNT(*) AS count FROM audit_findings GROUP BY status")).fetchall()
        by_area_rows = await (await db.execute("SELECT area, COUNT(*) AS count FROM audit_findings GROUP BY area")).fetchall()
        by_level = {str(row["level"]): row["count"] for row in by_level_rows}
        by_status = {row["status"]: row["count"] for row in by_status_rows}
        by_area = {row["area"]: row["count"] for row in by_area_rows}
        total = sum(by_status.values())
        closed_count = by_status.get("closed", 0)
        return {
            "total": total,
            "open": total - closed_count,
            "closed": closed_count,
            "by_level": by_level,
            "by_status": by_status,
            "by_area": by_area,
        }
    finally:
        await db.close()


@router.get("/audit-findings/{finding_id}")
async def get_audit_finding(finding_id: str, request: Request):
    _check(request, "audit_finding:read")
    db = await get_db()
    try:
        row = await (await db.execute(
            "SELECT * FROM audit_findings WHERE finding_id = ?", (finding_id,)
        )).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Audit finding not found")
        return dict(row)
    finally:
        await db.close()
