"""P1 API routes - Safety, ROC, Aircraft."""
from fastapi import APIRouter, HTTPException, Request, Response
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import json
from collections import Counter

from .database import get_db
from .notifications import send_email, get_notifications, mark_notification_read, check_and_notify, NOTIFICATION_ENABLED, SMTP_HOST
from .audit import log_audit_event
from .rbac import has_permission
from .p1_models import *

router = APIRouter()


def _actor(request: Request) -> str:
    return getattr(request.state, "actor", "admin")


def _role(request: Request) -> str:
    return getattr(request.state, "role", "system_admin")


def _check(request: Request, perm: str):
    if not has_permission(_role(request), perm):
        raise HTTPException(status_code=403, detail=f"Permission denied: {perm}")


def _notify_qualification_expiry(crew_id: str, qual_type: str, expiry_date: str):
    try:
        from datetime import datetime, timedelta
        from .database import get_db
        from .notifications import persist_notification

        async def _persist():
            db = await get_db()
            try:
                cursor = await db.execute("SELECT value FROM app_settings WHERE key = 'crew_currency_warning_days'")
                row = await cursor.fetchone()
                warning_days = int(row["value"]) if row else 30
                cutoff = datetime.now() + timedelta(days=warning_days)
                expiry = datetime.fromisoformat(expiry_date)
                if expiry <= cutoff:
                    subject = f"Crew Qualification Expiry Warning — {qual_type}"
                    body = (
                        f"Crew {crew_id} {qual_type} expires on {expiry_date}. "
                        f"Renewal is required within {warning_days} days."
                    )
                    persist_notification(
                        recipient="safety",
                        subject=subject,
                        body=body,
                        entity_type="crew_qualification",
                        entity_id=crew_id,
                        priority="high",
                        status="pending",
                    )
            finally:
                await db.close()

        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_persist())
        else:
            loop.run_until_complete(_persist())
    except Exception:
        pass


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


async def _check_mission_eligibility(db, aircraft_id=None, rpas_pilot_id=None, visual_observer_id=None):
    """Hard-block on expiry: verify crew licenses and aircraft insurance are valid."""
    errors = []
    today = datetime.now().date().isoformat()

    # Check pilot licenses
    for person_id in [rpas_pilot_id, visual_observer_id]:
        if not person_id:
            continue
        cursor = await db.execute(
            "SELECT license_type, expiry_date, status FROM personnel_licenses WHERE person_id = ? AND status IN ('valid', 'expiring_soon')",
            (person_id,)
        )
        rows = await cursor.fetchall()
        if not rows:
            errors.append(f"Person {person_id} has no valid licenses on record")
            continue
        for r in rows:
            if r["expiry_date"] and r["expiry_date"] < today:
                errors.append(f"Person {person_id} has expired {r['license_type']} (expired {r['expiry_date']})")

    # Check aircraft insurance
    if aircraft_id:
        cursor = await db.execute(
            "SELECT insurance_type, expiry_date, status FROM aircraft_insurance WHERE aircraft_id = ? AND status IN ('valid', 'expiring_soon')",
            (aircraft_id,)
        )
        rows = await cursor.fetchall()
        if not rows:
            errors.append(f"Aircraft {aircraft_id} has no valid insurance on record")
        for r in rows:
            if r["expiry_date"] and r["expiry_date"] < today:
                errors.append(f"Aircraft {aircraft_id} has expired {r['insurance_type']} insurance (expired {r['expiry_date']})")

    if errors:
        raise HTTPException(status_code=422, detail={"eligibility_errors": errors})


def now_iso() -> str:
    return datetime.now().isoformat()


# ==================== OCCURRENCES ====================

@router.post("/occurrences", response_model=OccurrenceResponse, status_code=201)
async def create_occurrence(occ: OccurrenceCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    occ_id = _gen_id("OCC")
    serial = f"OCC-{datetime.now().year}-{uuid.uuid4().hex[:4].upper()}"
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO occurrences (occurrence_id, serial_number, title, description, occurrence_type, severity, status, reporter_id, reporter_confidential, location, occurred_at, reported_at, mor_required, mor_deadline, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (occ_id, serial, occ.title, occ.description, occ.occurrence_type, occ.severity, "reported", actor, 1 if occ.reporter_confidential else 0, occ.location, occ.occurred_at, now, 1 if occ.mor_required else 0, occ.mor_deadline, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("occurrence", occ_id, "reported", actor, {"title": occ.title})
    return OccurrenceResponse(occurrence_id=occ_id, serial_number=serial, title=occ.title, description=occ.description, occurrence_type=occ.occurrence_type, severity=occ.severity, status="reported", reporter_id=actor, reporter_confidential=occ.reporter_confidential, location=occ.location, occurred_at=occ.occurred_at, reported_at=now, mor_required=occ.mor_required, mor_deadline=occ.mor_deadline, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/occurrences", response_model=List[OccurrenceResponse])
async def list_occurrences(request: Request, status: Optional[str] = None, occurrence_type: Optional[str] = None, severity: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if occurrence_type:
            conditions.append("occurrence_type = ?")
            params.append(occurrence_type)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM occurrences WHERE {where} ORDER BY reported_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        role = _role(request)
        result = []
        for r in rows:
            d = dict(r)
            if d.get("reporter_confidential") and not has_permission(role, "occurrence:investigate"):
                d["reporter_id"] = "CONFIDENTIAL"
            result.append(OccurrenceResponse(**d))
        return result
    finally:
        await db.close()


@router.get("/occurrences/{occ_id}", response_model=OccurrenceResponse)
async def get_occurrence(occ_id: str, request: Request):
    _check(request, "safety:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM occurrences WHERE occurrence_id = ?", (occ_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Occurrence not found")
        d = dict(row)
        role = _role(request)
        if d.get("reporter_confidential") and not has_permission(role, "occurrence:investigate"):
            d["reporter_id"] = "CONFIDENTIAL"
        return OccurrenceResponse(**d)
    finally:
        await db.close()


@router.patch("/occurrences/{occ_id}", response_model=OccurrenceResponse)
async def update_occurrence(occ_id: str, update: OccurrenceUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM occurrences WHERE occurrence_id = ?", (occ_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Occurrence not found")
        updates = []
        params = []
        field_map = {
            "title": update.title, "description": update.description, "occurrence_type": update.occurrence_type,
            "severity": update.severity, "status": update.status, "location": update.location,
            "occurred_at": update.occurred_at, "mor_deadline": update.mor_deadline, "mor_submitted_at": update.mor_submitted_at,
        }
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if update.mor_required is not None:
            updates.append("mor_required = ?")
            params.append(1 if update.mor_required else 0)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(occ_id)
            await db.execute(f"UPDATE occurrences SET {', '.join(updates)} WHERE occurrence_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM occurrences WHERE occurrence_id = ?", (occ_id,))
        row = await cursor.fetchone()
        return OccurrenceResponse(**dict(row))
    finally:
        await db.close()


@router.post("/occurrences/{occ_id}/acknowledge")
async def acknowledge_occurrence(occ_id: str, request: Request):
    _check(request, "occurrence:acknowledge")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        await db.execute("UPDATE occurrences SET status = 'acknowledged', acknowledged_at = ?, acknowledged_by = ?, updated_at = ?, updated_by = ? WHERE occurrence_id = ?", (now, actor, now, actor, occ_id))
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("occurrence", occ_id, "acknowledged", actor)
    return {"status": "acknowledged"}


# ==================== HAZARDS ====================

@router.post("/hazards", response_model=HazardResponse, status_code=201)
async def create_hazard(hazard: HazardCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    hazard_id = _gen_id("HAZ")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO hazards (hazard_id, title, description, category, status, risk_level, likelihood, severity, mitigation, owner_id, identified_by, identified_at, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (hazard_id, hazard.title, hazard.description, hazard.category, "identified", hazard.risk_level, hazard.likelihood, hazard.severity, hazard.mitigation, hazard.owner_id, actor, now, now, now),
        )
        await db.commit()
    finally:
        await db.close()
    return HazardResponse(hazard_id=hazard_id, title=hazard.title, description=hazard.description, category=hazard.category, status="identified", risk_level=hazard.risk_level, likelihood=hazard.likelihood, severity=hazard.severity, mitigation=hazard.mitigation, owner_id=hazard.owner_id, identified_by=actor, identified_at=now, created_at=now, updated_at=now)


@router.get("/hazards", response_model=List[HazardResponse])
async def list_hazards(request: Request, status: Optional[str] = None, risk_level: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if risk_level:
            conditions.append("risk_level = ?")
            params.append(risk_level)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM hazards WHERE {where} ORDER BY identified_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [HazardResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/hazards/{hazard_id}", response_model=HazardResponse)
async def update_hazard(hazard_id: str, update: HazardUpdate, request: Request):
    _check(request, "safety:update")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM hazards WHERE hazard_id = ?", (hazard_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Hazard not found")
        updates = []
        params = []
        field_map = {"title": update.title, "description": update.description, "category": update.category, "status": update.status, "risk_level": update.risk_level, "likelihood": update.likelihood, "severity": update.severity, "mitigation": update.mitigation, "owner_id": update.owner_id}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            params.append(hazard_id)
            await db.execute(f"UPDATE hazards SET {', '.join(updates)} WHERE hazard_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM hazards WHERE hazard_id = ?", (hazard_id,))
        row = await cursor.fetchone()
        return HazardResponse(**dict(row))
    finally:
        await db.close()


# ==================== RISK ASSESSMENTS ====================

@router.post("/risk-assessments", response_model=RiskAssessmentResponse, status_code=201)
async def create_risk_assessment(ra: RiskAssessmentCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    ra_id = _gen_id("RA")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO risk_assessments (assessment_id, hazard_id, occurrence_id, mission_id, title, description, likelihood, severity, risk_level, mitigation_measures, residual_risk, assessor_id, assessed_at, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ra_id, ra.hazard_id, ra.occurrence_id, ra.mission_id, ra.title, ra.description, ra.likelihood, ra.severity, ra.risk_level, ra.mitigation_measures, ra.residual_risk, actor, now, "draft", now, now),
        )
        await db.commit()
    finally:
        await db.close()
    return RiskAssessmentResponse(assessment_id=ra_id, hazard_id=ra.hazard_id, occurrence_id=ra.occurrence_id, mission_id=ra.mission_id, title=ra.title, description=ra.description, likelihood=ra.likelihood, severity=ra.severity, risk_level=ra.risk_level, mitigation_measures=ra.mitigation_measures, residual_risk=ra.residual_risk, assessor_id=actor, assessed_at=now, status="draft", created_at=now, updated_at=now)


@router.get("/risk-assessments", response_model=List[RiskAssessmentResponse])
async def list_risk_assessments(request: Request, hazard_id: Optional[str] = None, occurrence_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if hazard_id:
            conditions.append("hazard_id = ?")
            params.append(hazard_id)
        if occurrence_id:
            conditions.append("occurrence_id = ?")
            params.append(occurrence_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM risk_assessments WHERE {where} ORDER BY assessed_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [RiskAssessmentResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/risk-assessments/{assessment_id}", response_model=RiskAssessmentResponse)
async def update_risk_assessment(assessment_id: str, update: RiskAssessmentUpdate, request: Request):
    _check(request, "safety:update")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM risk_assessments WHERE assessment_id = ?", (assessment_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Risk assessment not found")
        updates = []
        params = []
        field_map = {"title": update.title, "description": update.description, "likelihood": update.likelihood, "severity": update.severity, "risk_level": update.risk_level, "mitigation_measures": update.mitigation_measures, "residual_risk": update.residual_risk, "status": update.status, "reviewed_by": update.reviewed_by}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            params.append(assessment_id)
            await db.execute(f"UPDATE risk_assessments SET {', '.join(updates)} WHERE assessment_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM risk_assessments WHERE assessment_id = ?", (assessment_id,))
        row = await cursor.fetchone()
        return RiskAssessmentResponse(**dict(row))
    finally:
        await db.close()


# ==================== INVESTIGATIONS ====================

@router.post("/investigations", response_model=InvestigationResponse, status_code=201)
async def create_investigation(inv: InvestigationCreate, request: Request):
    _check(request, "safety:update")
    inv_id = _gen_id("INV")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO investigations (investigation_id, occurrence_id, investigator_id, status, findings, root_cause, recommendations, started_at, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (inv_id, inv.occurrence_id, inv.investigator_id, "open", inv.findings, inv.root_cause, inv.recommendations, now, now, now),
        )
        # Update occurrence status to investigating
        await db.execute("UPDATE occurrences SET status = 'investigating', investigation_id = ?, updated_at = ?, updated_by = ? WHERE occurrence_id = ?", (inv_id, now, _actor(request), inv.occurrence_id))
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("investigation", inv_id, "opened", _actor(request), {"occurrence_id": inv.occurrence_id})
    return InvestigationResponse(investigation_id=inv_id, occurrence_id=inv.occurrence_id, investigator_id=inv.investigator_id, status="open", findings=inv.findings, root_cause=inv.root_cause, recommendations=inv.recommendations, started_at=now, created_at=now, updated_at=now)


@router.get("/investigations", response_model=List[InvestigationResponse])
async def list_investigations(request: Request, occurrence_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if occurrence_id:
            conditions.append("occurrence_id = ?")
            params.append(occurrence_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM investigations WHERE {where} ORDER BY started_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [InvestigationResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/investigations/{inv_id}", response_model=InvestigationResponse)
async def update_investigation(inv_id: str, update: InvestigationUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM investigations WHERE investigation_id = ?", (inv_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Investigation not found")
        updates = []
        params = []
        field_map = {"status": update.status, "findings": update.findings, "root_cause": update.root_cause, "recommendations": update.recommendations, "completed_at": update.completed_at}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            params.append(inv_id)
            await db.execute(f"UPDATE investigations SET {', '.join(updates)} WHERE investigation_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM investigations WHERE investigation_id = ?", (inv_id,))
        row = await cursor.fetchone()
        return InvestigationResponse(**dict(row))
    finally:
        await db.close()


# ==================== SAFETY ACTIONS ====================

@router.post("/safety-actions", response_model=SafetyActionResponse, status_code=201)
async def create_safety_action(sa: SafetyActionCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    sa_id = _gen_id("SA")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO safety_actions (action_id, occurrence_id, hazard_id, investigation_id, title, description, action_type, owner_id, due_date, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sa_id, sa.occurrence_id, sa.hazard_id, sa.investigation_id, sa.title, sa.description, sa.action_type, sa.owner_id, sa.due_date, "open", now, now),
        )
        await db.commit()
    finally:
        await db.close()
    return SafetyActionResponse(action_id=sa_id, occurrence_id=sa.occurrence_id, hazard_id=sa.hazard_id, investigation_id=sa.investigation_id, title=sa.title, description=sa.description, action_type=sa.action_type, owner_id=sa.owner_id, due_date=sa.due_date, status="open", created_at=now, updated_at=now)


@router.get("/safety-actions", response_model=List[SafetyActionResponse])
async def list_safety_actions(request: Request, occurrence_id: Optional[str] = None, hazard_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if occurrence_id:
            conditions.append("occurrence_id = ?")
            params.append(occurrence_id)
        if hazard_id:
            conditions.append("hazard_id = ?")
            params.append(hazard_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM safety_actions WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [SafetyActionResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/safety-actions/{sa_id}", response_model=SafetyActionResponse)
async def update_safety_action(sa_id: str, update: SafetyActionUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM safety_actions WHERE action_id = ?", (sa_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Safety action not found")
        updates = []
        params = []
        field_map = {"title": update.title, "description": update.description, "action_type": update.action_type, "owner_id": update.owner_id, "due_date": update.due_date, "status": update.status, "evidence": update.evidence, "verified_by": update.verified_by, "verified_at": update.verified_at, "effectiveness_check": update.effectiveness_check, "closed_at": update.closed_at}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            params.append(sa_id)
            await db.execute(f"UPDATE safety_actions SET {', '.join(updates)} WHERE action_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM safety_actions WHERE action_id = ?", (sa_id,))
        row = await cursor.fetchone()
        return SafetyActionResponse(**dict(row))
    finally:
        await db.close()


# ==================== SAFETY TRENDS ====================

@router.get("/safety/trends", response_model=SafetyTrendsResponse)
async def get_safety_trends(request: Request):
    _check(request, "safety:read")
    db = await get_db()
    try:
        # Occurrences by type
        cursor = await db.execute("SELECT occurrence_type, COUNT(*) as cnt FROM occurrences GROUP BY occurrence_type")
        occ_by_type = {r["occurrence_type"]: r["cnt"] for r in await cursor.fetchall()}
        # Occurrences by severity
        cursor = await db.execute("SELECT severity, COUNT(*) as cnt FROM occurrences GROUP BY severity")
        occ_by_sev = {r["severity"]: r["cnt"] for r in await cursor.fetchall()}
        # Safety actions by status
        cursor = await db.execute("SELECT status, COUNT(*) as cnt FROM safety_actions GROUP BY status")
        sa_by_status = {r["status"]: r["cnt"] for r in await cursor.fetchall()}
        # Hazards by risk level
        cursor = await db.execute("SELECT risk_level, COUNT(*) as cnt FROM hazards GROUP BY risk_level")
        haz_by_rl = {r["risk_level"]: r["cnt"] for r in await cursor.fetchall()}
        # Occurrences last 30 days
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM occurrences WHERE reported_at >= date('now', '-30 days')")
        row = await cursor.fetchone()
        occ_30 = row["cnt"] if row else 0
        return SafetyTrendsResponse(
            occurrences_by_type=occ_by_type,
            occurrences_by_severity=occ_by_sev,
            safety_actions_by_status=sa_by_status,
            hazards_by_risk_level=haz_by_rl,
            occurrences_last_30_days=occ_30,
        )
    finally:
        await db.close()


# ==================== ROC REGISTER ====================

@router.post("/roc", response_model=ROCRegisterResponse, status_code=201)
async def create_roc(roc: ROCRegisterCreate, request: Request):
    _check(request, "roc:manage")
    actor = _actor(request)
    roc_id = _gen_id("ROC")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO roc_register (roc_id, roc_number, serial_number, kcaa_reference, issue_date, expiry_date, status, categories, bvlos_authorized, night_authorized, max_altitude_agl, evlos_authorized, dg_category, notes, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (roc_id, roc.roc_number, roc.serial_number, roc.kcaa_reference, roc.issue_date, roc.expiry_date, "active", roc.categories, 1 if roc.bvlos_authorized else 0, 1 if roc.night_authorized else 0, roc.max_altitude_agl, 1 if roc.evlos_authorized else 0, roc.dg_category, roc.notes, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return ROCRegisterResponse(roc_id=roc_id, roc_number=roc.roc_number, serial_number=roc.serial_number, kcaa_reference=roc.kcaa_reference, issue_date=roc.issue_date, expiry_date=roc.expiry_date, status="active", categories=roc.categories, bvlos_authorized=roc.bvlos_authorized, night_authorized=roc.night_authorized, max_altitude_agl=roc.max_altitude_agl, evlos_authorized=roc.evlos_authorized, dg_category=roc.dg_category, notes=roc.notes, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/roc", response_model=List[ROCRegisterResponse])
async def list_roc(request: Request, status: Optional[str] = None):
    _check(request, "roc:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM roc_register WHERE status = ? ORDER BY expiry_date", (status,))
        else:
            cursor = await db.execute("SELECT * FROM roc_register ORDER BY expiry_date")
        rows = await cursor.fetchall()
        return [ROCRegisterResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.get("/roc/{roc_id}", response_model=ROCRegisterResponse)
async def get_roc(roc_id: str, request: Request):
    _check(request, "roc:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM roc_register WHERE roc_id = ?", (roc_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="ROC not found")
        return ROCRegisterResponse(**dict(row))
    finally:
        await db.close()


@router.patch("/roc/{roc_id}", response_model=ROCRegisterResponse)
async def update_roc(roc_id: str, update: ROCRegisterUpdate, request: Request):
    _check(request, "roc:manage")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM roc_register WHERE roc_id = ?", (roc_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="ROC not found")
        updates = []
        params = []
        field_map = {"roc_number": update.roc_number, "serial_number": update.serial_number, "kcaa_reference": update.kcaa_reference, "issue_date": update.issue_date, "expiry_date": update.expiry_date, "status": update.status, "categories": update.categories, "max_altitude_agl": update.max_altitude_agl, "dg_category": update.dg_category, "notes": update.notes}
        bool_fields = {"bvlos_authorized": update.bvlos_authorized, "night_authorized": update.night_authorized, "evlos_authorized": update.evlos_authorized}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        for col, val in bool_fields.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(1 if val else 0)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(roc_id)
            await db.execute(f"UPDATE roc_register SET {', '.join(updates)} WHERE roc_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM roc_register WHERE roc_id = ?", (roc_id,))
        row = await cursor.fetchone()
        return ROCRegisterResponse(**dict(row))
    finally:
        await db.close()


# ==================== AIRCRAFT ====================

@router.post("/aircraft", response_model=AircraftResponse, status_code=201)
async def create_aircraft(ac: AircraftCreate, request: Request):
    _check(request, "aircraft:manage")
    actor = _actor(request)
    ac_id = _gen_id("AC")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO aircraft (aircraft_id, registration, model, manufacturer, serial_number, roc_id, status, category, weight_class, max_takeoff_weight_kg, acquired_date, notes, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ac_id, ac.registration, ac.model, ac.manufacturer, ac.serial_number, ac.roc_id, "active", ac.category, ac.weight_class, ac.max_takeoff_weight_kg, ac.acquired_date, ac.notes, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return AircraftResponse(aircraft_id=ac_id, registration=ac.registration, model=ac.model, manufacturer=ac.manufacturer, serial_number=ac.serial_number, roc_id=ac.roc_id, status="active", category=ac.category, weight_class=ac.weight_class, max_takeoff_weight_kg=ac.max_takeoff_weight_kg, acquired_date=ac.acquired_date, notes=ac.notes, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/aircraft", response_model=List[AircraftResponse])
async def list_aircraft(request: Request, roc_id: Optional[str] = None, status: Optional[str] = None, registration: Optional[str] = None, limit: int = 100, offset: int = 0):
    _check(request, "aircraft:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if roc_id:
            conditions.append("roc_id = ?")
            params.append(roc_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if registration:
            conditions.append("registration = ?")
            params.append(registration)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM aircraft WHERE {where} ORDER BY registration LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [AircraftResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.get("/aircraft/{ac_id}", response_model=AircraftResponse)
async def get_aircraft(ac_id: str, request: Request):
    _check(request, "aircraft:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM aircraft WHERE aircraft_id = ?", (ac_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Aircraft not found")
        return AircraftResponse(**dict(row))
    finally:
        await db.close()


@router.patch("/aircraft/{ac_id}", response_model=AircraftResponse)
async def update_aircraft(ac_id: str, update: AircraftUpdate, request: Request):
    _check(request, "aircraft:manage")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM aircraft WHERE aircraft_id = ?", (ac_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Aircraft not found")
        updates = []
        params = []
        field_map = {"registration": update.registration, "model": update.model, "manufacturer": update.manufacturer, "serial_number": update.serial_number, "roc_id": update.roc_id, "status": update.status, "category": update.category, "weight_class": update.weight_class, "max_takeoff_weight_kg": update.max_takeoff_weight_kg, "acquired_date": update.acquired_date, "notes": update.notes}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(ac_id)
            await db.execute(f"UPDATE aircraft SET {', '.join(updates)} WHERE aircraft_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM aircraft WHERE aircraft_id = ?", (ac_id,))
        row = await cursor.fetchone()
        return AircraftResponse(**dict(row))
    finally:
        await db.close()

# ==================== MISSIONS (P1 Phase 3) ====================

@router.post("/missions", response_model=MissionResponse, status_code=201)
async def create_mission(mission: MissionCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    mission_id = _gen_id("MSN")
    now = now_iso()
    db = await get_db()
    try:
        # Hard-block on expiry: verify crew licenses and aircraft insurance
        await _check_mission_eligibility(db, mission.aircraft_id, mission.rpas_pilot_id, mission.visual_observer_id)
        await db.execute(
            """INSERT INTO missions (mission_id, title, description, mission_type, status, priority, planned_date, location, aircraft_id, roc_id, rpas_pilot_id, visual_observer_id, dg_category, max_altitude_agl, bvlos_required, night_required, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mission_id, mission.title, mission.description, mission.mission_type, "planned", mission.priority, mission.planned_date, mission.location, mission.aircraft_id, mission.roc_id, mission.rpas_pilot_id, mission.visual_observer_id, mission.dg_category, mission.max_altitude_agl, 1 if mission.bvlos_required else 0, 1 if mission.night_required else 0, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("mission", mission_id, "created", actor, {"title": mission.title})
    return MissionResponse(mission_id=mission_id, title=mission.title, description=mission.description, mission_type=mission.mission_type, status="planned", priority=mission.priority, planned_date=mission.planned_date, location=mission.location, aircraft_id=mission.aircraft_id, roc_id=mission.roc_id, rpas_pilot_id=mission.rpas_pilot_id, visual_observer_id=mission.visual_observer_id, dg_category=mission.dg_category, max_altitude_agl=mission.max_altitude_agl, bvlos_required=mission.bvlos_required, night_required=mission.night_required, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/missions", response_model=List[MissionResponse])
async def list_missions(request: Request, status: Optional[str] = None, mission_type: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if mission_type:
            conditions.append("mission_type = ?")
            params.append(mission_type)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM missions WHERE {where} ORDER BY planned_date DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [MissionResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.get("/missions/{mission_id}", response_model=MissionResponse)
async def get_mission(mission_id: str, request: Request):
    _check(request, "safety:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Mission not found")
        return MissionResponse(**dict(row))
    finally:
        await db.close()


@router.patch("/missions/{mission_id}", response_model=MissionResponse)
async def update_mission(mission_id: str, update: MissionUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Mission not found")
        # Hard-block on expiry when aircraft or crew is being changed
        if update.aircraft_id is not None or update.rpas_pilot_id is not None or update.visual_observer_id is not None:
            # Get current mission to fill in unchanged values
            cursor = await db.execute("SELECT aircraft_id, rpas_pilot_id, visual_observer_id FROM missions WHERE mission_id = ?", (mission_id,))
            row = await cursor.fetchone()
            aid = update.aircraft_id if update.aircraft_id is not None else (row["aircraft_id"] if row else None)
            pid = update.rpas_pilot_id if update.rpas_pilot_id is not None else (row["rpas_pilot_id"] if row else None)
            vid = update.visual_observer_id if update.visual_observer_id is not None else (row["visual_observer_id"] if row else None)
            await _check_mission_eligibility(db, aid, pid, vid)
        updates = []
        params = []
        field_map = {"title": update.title, "description": update.description, "mission_type": update.mission_type, "priority": update.priority, "planned_date": update.planned_date, "location": update.location, "aircraft_id": update.aircraft_id, "roc_id": update.roc_id, "rpas_pilot_id": update.rpas_pilot_id, "visual_observer_id": update.visual_observer_id, "dg_category": update.dg_category, "max_altitude_agl": update.max_altitude_agl, "risk_assessment_id": update.risk_assessment_id}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if update.bvlos_required is not None:
            updates.append("bvlos_required = ?")
            params.append(1 if update.bvlos_required else 0)
        if update.night_required is not None:
            updates.append("night_required = ?")
            params.append(1 if update.night_required else 0)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(mission_id)
            await db.execute(f"UPDATE missions SET {', '.join(updates)} WHERE mission_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,))
        row = await cursor.fetchone()
        return MissionResponse(**dict(row))
    finally:
        await db.close()


@router.patch("/missions/{mission_id}/state", response_model=MissionResponse)
async def transition_mission_state(mission_id: str, state: str, request: Request):
    """Transition mission state with validation."""
    _check(request, "safety:update")
    actor = _actor(request)
    role = _role(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Mission not found")
        row = dict(row)
        current = row["status"]

        # Valid transitions
        VALID_TRANSITIONS = {
            "planned": ["in_progress", "cancelled"],
            "in_progress": ["completed", "aborted"],
            "released": ["in_progress", "aborted"],
        }
        if state not in VALID_TRANSITIONS.get(current, []):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition: {current} → {state}. Allowed: {VALID_TRANSITIONS.get(current, [])}",
            )

        # Permission checks
        if state in ("completed", "aborted"):
            if not has_permission(role, "safety:close"):
                raise HTTPException(status_code=403, detail="safety:close permission required")

        now = now_iso()
        await db.execute(
            "UPDATE missions SET status = ?, updated_at = ?, updated_by = ? WHERE mission_id = ?",
            (state, now, actor, mission_id),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,))
        row = await cursor.fetchone()
        await log_audit_event("mission", mission_id, f"state:{state}", actor, {"from": current, "to": state})
        return MissionResponse(**dict(row))
    finally:
        await db.close()


# ==================== FLIGHT PLANS ====================

@router.post("/flight-plans", response_model=FlightPlanResponse, status_code=201)
async def create_flight_plan(fp: FlightPlanCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    plan_id = _gen_id("FP")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO flight_plans (plan_id, mission_id, route_description, waypoints, max_altitude_agl, estimated_duration_min, fuel_battery_plan, weather_minima, contingency_plan, status, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (plan_id, fp.mission_id, fp.route_description, fp.waypoints, fp.max_altitude_agl, fp.estimated_duration_min, fp.fuel_battery_plan, fp.weather_minima, fp.contingency_plan, "draft", now, now, actor, actor),
        )
        await db.execute("UPDATE missions SET flight_plan_id = ?, updated_at = ?, updated_by = ? WHERE mission_id = ?", (plan_id, now, actor, fp.mission_id))
        await db.commit()
    finally:
        await db.close()
    return FlightPlanResponse(plan_id=plan_id, mission_id=fp.mission_id, route_description=fp.route_description, waypoints=fp.waypoints, max_altitude_agl=fp.max_altitude_agl, estimated_duration_min=fp.estimated_duration_min, fuel_battery_plan=fp.fuel_battery_plan, weather_minima=fp.weather_minima, contingency_plan=fp.contingency_plan, status="draft", created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/flight-plans", response_model=List[FlightPlanResponse])
async def list_flight_plans(request: Request, mission_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if mission_id:
            cursor = await db.execute("SELECT * FROM flight_plans WHERE mission_id = ? ORDER BY created_at DESC", (mission_id,))
        else:
            cursor = await db.execute("SELECT * FROM flight_plans ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [FlightPlanResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/flight-plans/{plan_id}/approve")
async def approve_flight_plan(plan_id: str, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        await db.execute("UPDATE flight_plans SET status = 'approved', approved_by = ?, approved_at = ?, updated_at = ?, updated_by = ? WHERE plan_id = ?", (actor, now, now, actor, plan_id))
        await db.commit()
    finally:
        await db.close()
    return {"status": "approved"}


# ==================== FLIGHT RELEASES ====================

@router.post("/flight-releases", response_model=FlightReleaseResponse, status_code=201)
async def create_flight_release(fr: FlightReleaseCreate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    release_id = _gen_id("REL")
    now = now_iso()
    db = await get_db()
    try:
        if not fr.pre_flight_checklist:
            raise HTTPException(status_code=400, detail="Pre-flight checklist required")
        if not (fr.weather_confirmed and fr.crew_confirmed and fr.aircraft_confirmed):
            raise HTTPException(status_code=400, detail="All confirmations (weather, crew, aircraft) required")
        await db.execute(
            """INSERT INTO flight_releases (release_id, mission_id, plan_id, released_by, released_at, pre_flight_checklist, weather_confirmed, crew_confirmed, aircraft_confirmed, status, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (release_id, fr.mission_id, fr.plan_id, actor, now, fr.pre_flight_checklist, 1 if fr.weather_confirmed else 0, 1 if fr.crew_confirmed else 0, 1 if fr.aircraft_confirmed else 0, "released", fr.notes, now),
        )
        await db.execute("UPDATE missions SET status = 'released', release_id = ?, updated_at = ?, updated_by = ? WHERE mission_id = ?", (release_id, now, actor, fr.mission_id))
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("flight_release", release_id, "released", actor, {"mission_id": fr.mission_id})
    return FlightReleaseResponse(release_id=release_id, mission_id=fr.mission_id, plan_id=fr.plan_id, released_by=actor, released_at=now, pre_flight_checklist=fr.pre_flight_checklist, weather_confirmed=fr.weather_confirmed, crew_confirmed=fr.crew_confirmed, aircraft_confirmed=fr.aircraft_confirmed, status="released", notes=fr.notes, created_at=now)


@router.get("/flight-releases", response_model=List[FlightReleaseResponse])
async def list_flight_releases(request: Request, mission_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if mission_id:
            cursor = await db.execute("SELECT * FROM flight_releases WHERE mission_id = ? ORDER BY released_at DESC", (mission_id,))
        else:
            cursor = await db.execute("SELECT * FROM flight_releases ORDER BY released_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [FlightReleaseResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# ==================== POST-FLIGHT REPORTS ====================

@router.post("/post-flight-reports", response_model=PostFlightReportResponse, status_code=201)
async def create_post_flight_report(pfr: PostFlightReportCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    report_id = _gen_id("PFR")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO post_flight_reports (report_id, mission_id, actual_duration_min, actual_max_altitude, incidents, anomalies, battery_cycles, flight_hours, data_collected, submitted_by, submitted_at, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (report_id, pfr.mission_id, pfr.actual_duration_min, pfr.actual_max_altitude, pfr.incidents, pfr.anomalies, pfr.battery_cycles, pfr.flight_hours, pfr.data_collected, actor, now, "submitted", now, now),
        )
        await db.execute("UPDATE missions SET status = 'completed', post_flight_report_id = ?, updated_at = ?, updated_by = ? WHERE mission_id = ?", (report_id, now, actor, pfr.mission_id))
        await db.commit()
    finally:
        await db.close()
    return PostFlightReportResponse(report_id=report_id, mission_id=pfr.mission_id, actual_duration_min=pfr.actual_duration_min, actual_max_altitude=pfr.actual_max_altitude, incidents=pfr.incidents, anomalies=pfr.anomalies, battery_cycles=pfr.battery_cycles, flight_hours=pfr.flight_hours, data_collected=pfr.data_collected, submitted_by=actor, submitted_at=now, status="submitted", created_at=now, updated_at=now)


@router.get("/post-flight-reports", response_model=List[PostFlightReportResponse])
async def list_post_flight_reports(request: Request, mission_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if mission_id:
            cursor = await db.execute("SELECT * FROM post_flight_reports WHERE mission_id = ? ORDER BY submitted_at DESC", (mission_id,))
        else:
            cursor = await db.execute("SELECT * FROM post_flight_reports ORDER BY submitted_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [PostFlightReportResponse(**dict(r)) for r in rows]
    finally:
        await db.close()

# ==================== QUALITY AUDITS (P1 Phase 4) ====================

@router.post("/quality-audits", response_model=QualityAuditResponse, status_code=201)
async def create_quality_audit(audit: QualityAuditCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    audit_id = _gen_id("QA")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO quality_audits (audit_id, title, audit_type, scope, auditor_id, auditee_id, planned_date, status, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (audit_id, audit.title, audit.audit_type, audit.scope, audit.auditor_id, audit.auditee_id, audit.planned_date, "planned", now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return QualityAuditResponse(audit_id=audit_id, title=audit.title, audit_type=audit.audit_type, scope=audit.scope, auditor_id=audit.auditor_id, auditee_id=audit.auditee_id, planned_date=audit.planned_date, status="planned", created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/quality-audits", response_model=List[QualityAuditResponse])
async def list_quality_audits(request: Request, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM quality_audits WHERE status = ? ORDER BY planned_date DESC LIMIT ? OFFSET ?", (status, limit, offset))
        else:
            cursor = await db.execute("SELECT * FROM quality_audits ORDER BY planned_date DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [QualityAuditResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.get("/quality-audits/{audit_id}", response_model=QualityAuditResponse)
async def get_quality_audit(audit_id: str, request: Request):
    _check(request, "safety:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM quality_audits WHERE audit_id = ?", (audit_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Audit not found")
        return QualityAuditResponse(**dict(row))
    finally:
        await db.close()


@router.patch("/quality-audits/{audit_id}", response_model=QualityAuditResponse)
async def update_quality_audit(audit_id: str, update: QualityAuditUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM quality_audits WHERE audit_id = ?", (audit_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Audit not found")
        updates = []
        params = []
        field_map = {"title": update.title, "audit_type": update.audit_type, "scope": update.scope, "auditee_id": update.auditee_id, "planned_date": update.planned_date, "actual_date": update.actual_date, "status": update.status, "overall_result": update.overall_result, "report": update.report}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(audit_id)
            await db.execute(f"UPDATE quality_audits SET {', '.join(updates)} WHERE audit_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM quality_audits WHERE audit_id = ?", (audit_id,))
        row = await cursor.fetchone()
        return QualityAuditResponse(**dict(row))
    finally:
        await db.close()


# ==================== AUDIT FINDINGS ====================

@router.post("/audit-findings", response_model=AuditFindingResponse, status_code=201)
async def create_audit_finding(finding: AuditFindingCreate, request: Request):
    _check(request, "safety:create")
    finding_id = _gen_id("AF")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO audit_findings (finding_id, audit_id, finding_type, description, severity, root_cause, evidence, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (finding_id, finding.audit_id, finding.finding_type, finding.description, finding.severity, finding.root_cause, finding.evidence, "open", now, now),
        )
        # Update findings count
        await db.execute("UPDATE quality_audits SET findings_count = findings_count + 1, updated_at = ? WHERE audit_id = ?", (now, finding.audit_id))
        await db.commit()
    finally:
        await db.close()
    return AuditFindingResponse(finding_id=finding_id, audit_id=finding.audit_id, finding_type=finding.finding_type, description=finding.description, severity=finding.severity, root_cause=finding.root_cause, evidence=finding.evidence, status="open", created_at=now, updated_at=now)


@router.get("/audit-findings", response_model=List[AuditFindingResponse])
async def list_audit_findings(request: Request, audit_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if audit_id:
            cursor = await db.execute("SELECT * FROM audit_findings WHERE audit_id = ? ORDER BY created_at DESC", (audit_id,))
        else:
            cursor = await db.execute("SELECT * FROM audit_findings ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [AuditFindingResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# ==================== CORRECTIVE ACTION REQUESTS (CARs) ====================

@router.post("/corrective-actions", response_model=CorrectiveActionResponse, status_code=201)
async def create_corrective_action(car: CorrectiveActionCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    car_id = _gen_id("CAR")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO corrective_actions (car_id, finding_id, audit_id, title, description, root_cause, corrective_action, preventive_action, owner_id, due_date, status, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (car_id, car.finding_id, car.audit_id, car.title, car.description, car.root_cause, car.corrective_action, car.preventive_action, car.owner_id, car.due_date, "open", now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return CorrectiveActionResponse(car_id=car_id, finding_id=car.finding_id, audit_id=car.audit_id, title=car.title, description=car.description, root_cause=car.root_cause, corrective_action=car.corrective_action, preventive_action=car.preventive_action, owner_id=car.owner_id, due_date=car.due_date, status="open", created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/corrective-actions", response_model=List[CorrectiveActionResponse])
async def list_corrective_actions(request: Request, status: Optional[str] = None, owner_id: Optional[str] = None, audit_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if owner_id:
            conditions.append("owner_id = ?")
            params.append(owner_id)
        if audit_id:
            conditions.append("audit_id = ?")
            params.append(audit_id)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM corrective_actions WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [CorrectiveActionResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/corrective-actions/{car_id}", response_model=CorrectiveActionResponse)
async def update_corrective_action(car_id: str, update: CorrectiveActionUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM corrective_actions WHERE car_id = ?", (car_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="CAR not found")
        updates = []
        params = []
        field_map = {"title": update.title, "description": update.description, "root_cause": update.root_cause, "corrective_action": update.corrective_action, "preventive_action": update.preventive_action, "owner_id": update.owner_id, "due_date": update.due_date, "status": update.status, "verification": update.verification, "verified_by": update.verified_by, "verified_at": update.verified_at, "closed_at": update.closed_at}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(car_id)
            await db.execute(f"UPDATE corrective_actions SET {', '.join(updates)} WHERE car_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM corrective_actions WHERE car_id = ?", (car_id,))
        row = await cursor.fetchone()
        return CorrectiveActionResponse(**dict(row))
    finally:
        await db.close()


@router.post("/corrective-actions/{car_id}/verify")
async def verify_car(car_id: str, request: Request, verification: str = "", verified_by: str = ""):
    _check(request, "safety:update")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        await db.execute("UPDATE corrective_actions SET status = 'verified', verification = ?, verified_by = ?, verified_at = ?, updated_at = ?, updated_by = ? WHERE car_id = ?", (verification, actor, now, now, actor, car_id))
        await db.commit()
    finally:
        await db.close()
    return {"status": "verified"}

# ==================== DANGEROUS GOODS (P1 Phase 5) ====================

@router.post("/dg-shipments", response_model=DGShipmentResponse, status_code=201)
async def create_dg_shipment(shipment: DGShipmentCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    shipment_id = _gen_id("DG")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO dg_shipments (shipment_id, dg_class, un_number, proper_shipping_name, quantity, packaging_type, shipper, consignee, mission_id, aircraft_id, status, notes, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (shipment_id, shipment.dg_class, shipment.un_number, shipment.proper_shipping_name, shipment.quantity, shipment.packaging_type, shipment.shipper, shipment.consignee, shipment.mission_id, shipment.aircraft_id, "pending", shipment.notes, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return DGShipmentResponse(shipment_id=shipment_id, dg_class=shipment.dg_class, un_number=shipment.un_number, proper_shipping_name=shipment.proper_shipping_name, quantity=shipment.quantity, packaging_type=shipment.packaging_type, shipper=shipment.shipper, consignee=shipment.consignee, mission_id=shipment.mission_id, aircraft_id=shipment.aircraft_id, status="pending", notes=shipment.notes, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/dg-shipments", response_model=List[DGShipmentResponse])
async def list_dg_shipments(request: Request, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM dg_shipments WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (status, limit, offset))
        else:
            cursor = await db.execute("SELECT * FROM dg_shipments ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [DGShipmentResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/dg-shipments/{shipment_id}", response_model=DGShipmentResponse)
async def update_dg_shipment(shipment_id: str, update: DGShipmentUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM dg_shipments WHERE shipment_id = ?", (shipment_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Shipment not found")
        updates = []
        params = []
        field_map = {"dg_class": update.dg_class, "proper_shipping_name": update.proper_shipping_name, "un_number": update.un_number, "quantity": update.quantity, "packaging_type": update.packaging_type, "shipper": update.shipper, "consignee": update.consignee, "mission_id": update.mission_id, "aircraft_id": update.aircraft_id, "status": update.status, "notes": update.notes}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(shipment_id)
            await db.execute(f"UPDATE dg_shipments SET {', '.join(updates)} WHERE shipment_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM dg_shipments WHERE shipment_id = ?", (shipment_id,))
        row = await cursor.fetchone()
        return DGShipmentResponse(**dict(row))
    finally:
        await db.close()


@router.post("/dg-acceptance-checks", response_model=DGAcceptanceCheckResponse, status_code=201)
async def create_dg_acceptance_check(check: DGAcceptanceCheckCreate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    check_id = _gen_id("DAC")
    now = now_iso()
    result = "accepted" if all([check.packaging_ok, check.marking_ok, check.labeling_ok, check.documentation_ok, check.compatibility_ok]) else "rejected"
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO dg_acceptance_checks (check_id, shipment_id, checked_by, checked_at, packaging_ok, marking_ok, labeling_ok, documentation_ok, compatibility_ok, result, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (check_id, check.shipment_id, actor, now, 1 if check.packaging_ok else 0, 1 if check.marking_ok else 0, 1 if check.labeling_ok else 0, 1 if check.documentation_ok else 0, 1 if check.compatibility_ok else 0, result, check.notes, now),
        )
        await db.execute("UPDATE dg_shipments SET status = ?, acceptance_check_id = ?, updated_at = ?, updated_by = ? WHERE shipment_id = ?", (result, check_id, now, actor, check.shipment_id))
        await db.commit()
    finally:
        await db.close()
    return DGAcceptanceCheckResponse(check_id=check_id, shipment_id=check.shipment_id, checked_by=actor, checked_at=now, packaging_ok=check.packaging_ok, marking_ok=check.marking_ok, labeling_ok=check.labeling_ok, documentation_ok=check.documentation_ok, compatibility_ok=check.compatibility_ok, result=result, notes=check.notes, created_at=now)


@router.get("/dg-acceptance-checks", response_model=List[DGAcceptanceCheckResponse])
async def list_dg_acceptance_checks(request: Request, shipment_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if shipment_id:
            cursor = await db.execute("SELECT * FROM dg_acceptance_checks WHERE shipment_id = ? ORDER BY checked_at DESC", (shipment_id,))
        else:
            cursor = await db.execute("SELECT * FROM dg_acceptance_checks ORDER BY checked_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [DGAcceptanceCheckResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# ==================== DG TRAINING ====================

@router.post("/dg-training-records", response_model=DGTrainingRecordResponse, status_code=201)
async def create_dg_training_record(record: DGTrainingRecordCreate, request: Request):
    _check(request, "safety:create")
    record_id = _gen_id("DGT")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO dg_training_records (record_id, person_id, training_type, training_date, expiry_date, certificate_number, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (record_id, record.person_id, record.training_type, record.training_date, record.expiry_date, record.certificate_number, "valid", now, now),
        )
        await db.commit()
    finally:
        await db.close()
    return DGTrainingRecordResponse(record_id=record_id, person_id=record.person_id, training_type=record.training_type, training_date=record.training_date, expiry_date=record.expiry_date, certificate_number=record.certificate_number, status="valid", created_at=now, updated_at=now)


@router.get("/dg-training-records", response_model=List[DGTrainingRecordResponse])
async def list_dg_training_records(request: Request, person_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if person_id:
            cursor = await db.execute("SELECT * FROM dg_training_records WHERE person_id = ? ORDER BY training_date DESC", (person_id,))
        else:
            cursor = await db.execute("SELECT * FROM dg_training_records ORDER BY training_date DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [DGTrainingRecordResponse(**dict(r)) for r in rows]
    finally:
        await db.close()

# ==================== SECURITY MANAGEMENT (P1 Phase 6) ====================

@router.post("/security-incidents", response_model=SecurityIncidentResponse, status_code=201)
async def create_security_incident(incident: SecurityIncidentCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    incident_id = _gen_id("SEC")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO security_incidents (incident_id, title, description, incident_type, severity, location, reported_by, reported_at, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (incident_id, incident.title, incident.description, incident.incident_type, incident.severity, incident.location, actor, now, "reported", now, now),
        )
        await db.commit()
    finally:
        await db.close()
    return SecurityIncidentResponse(incident_id=incident_id, title=incident.title, description=incident.description, incident_type=incident.incident_type, severity=incident.severity, location=incident.location, reported_by=actor, reported_at=now, status="reported", created_at=now, updated_at=now)


@router.get("/security-incidents", response_model=List[SecurityIncidentResponse])
async def list_security_incidents(request: Request, status: Optional[str] = None, incident_type: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if incident_type:
            conditions.append("incident_type = ?")
            params.append(incident_type)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM security_incidents WHERE {where} ORDER BY reported_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [SecurityIncidentResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/security-incidents/{incident_id}", response_model=SecurityIncidentResponse)
async def update_security_incident(incident_id: str, update: SecurityIncidentUpdate, request: Request):
    _check(request, "safety:update")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM security_incidents WHERE incident_id = ?", (incident_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Incident not found")
        updates = []
        params = []
        field_map = {"title": update.title, "description": update.description, "incident_type": update.incident_type, "severity": update.severity, "location": update.location, "status": update.status, "investigation_notes": update.investigation_notes, "resolved_at": update.resolved_at, "resolved_by": update.resolved_by}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            params.append(incident_id)
            await db.execute(f"UPDATE security_incidents SET {', '.join(updates)} WHERE incident_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM security_incidents WHERE incident_id = ?", (incident_id,))
        row = await cursor.fetchone()
        return SecurityIncidentResponse(**dict(row))
    finally:
        await db.close()


@router.post("/security-assessments", response_model=SecurityAssessmentResponse, status_code=201)
async def create_security_assessment(sa: SecurityAssessmentCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    sa_id = _gen_id("SA")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO security_assessments (assessment_id, title, assessment_type, scope, assessor_id, risk_level, status, planned_date, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sa_id, sa.title, sa.assessment_type, sa.scope, sa.assessor_id, "medium", "planned", sa.planned_date, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return SecurityAssessmentResponse(assessment_id=sa_id, title=sa.title, assessment_type=sa.assessment_type, scope=sa.scope, assessor_id=sa.assessor_id, risk_level="medium", status="planned", planned_date=sa.planned_date, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/security-assessments", response_model=List[SecurityAssessmentResponse])
async def list_security_assessments(request: Request, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM security_assessments WHERE status = ? ORDER BY planned_date DESC LIMIT ? OFFSET ?", (status, limit, offset))
        else:
            cursor = await db.execute("SELECT * FROM security_assessments ORDER BY planned_date DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [SecurityAssessmentResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/security-assessments/{assessment_id}", response_model=SecurityAssessmentResponse)
async def update_security_assessment(assessment_id: str, update: SecurityAssessmentUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM security_assessments WHERE assessment_id = ?", (assessment_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Assessment not found")
        updates = []
        params = []
        field_map = {"title": update.title, "assessment_type": update.assessment_type, "scope": update.scope, "findings": update.findings, "risk_level": update.risk_level, "status": update.status, "planned_date": update.planned_date, "completed_date": update.completed_date, "report": update.report}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(assessment_id)
            await db.execute(f"UPDATE security_assessments SET {', '.join(updates)} WHERE assessment_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM security_assessments WHERE assessment_id = ?", (assessment_id,))
        row = await cursor.fetchone()
        return SecurityAssessmentResponse(**dict(row))
    finally:
        await db.close()


@router.post("/security-training", response_model=SecurityTrainingResponse, status_code=201)
async def create_security_training(record: SecurityTrainingCreate, request: Request):
    _check(request, "safety:create")
    record_id = _gen_id("ST")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO security_training (training_id, person_id, training_type, training_date, expiry_date, certificate_number, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (record_id, record.person_id, record.training_type, record.training_date, record.expiry_date, record.certificate_number, "valid", now, now),
        )
        await db.commit()
    finally:
        await db.close()
    return SecurityTrainingResponse(training_id=record_id, person_id=record.person_id, training_type=record.training_type, training_date=record.training_date, expiry_date=record.expiry_date, certificate_number=record.certificate_number, status="valid", created_at=now, updated_at=now)


@router.get("/security-training", response_model=List[SecurityTrainingResponse])
async def list_security_training(request: Request, person_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if person_id:
            cursor = await db.execute("SELECT * FROM security_training WHERE person_id = ? ORDER BY training_date DESC", (person_id,))
        else:
            cursor = await db.execute("SELECT * FROM security_training ORDER BY training_date DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [SecurityTrainingResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# ==================== TRAINING MANAGEMENT ====================

@router.post("/training-records", response_model=TrainingRecordResponse, status_code=201)
async def create_training_record(record: TrainingRecordCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    record_id = _gen_id("TRN")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO training_records (record_id, person_id, training_category, training_type, training_date, expiry_date, certificate_number, status, notes, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (record_id, record.person_id, record.training_category, record.training_type, record.training_date, record.expiry_date, record.certificate_number, "valid", record.notes, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return TrainingRecordResponse(record_id=record_id, person_id=record.person_id, training_category=record.training_category, training_type=record.training_type, training_date=record.training_date, expiry_date=record.expiry_date, certificate_number=record.certificate_number, status="valid", notes=record.notes, created_at=now, updated_at=now)


@router.get("/training-records", response_model=List[TrainingRecordResponse])
async def list_training_records(request: Request, category: Optional[str] = None, person_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if category:
            conditions.append("training_category = ?")
            params.append(category)
        if person_id:
            conditions.append("person_id = ?")
            params.append(person_id)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM training_records WHERE {where} ORDER BY training_date DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [TrainingRecordResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/training-records/{record_id}", response_model=TrainingRecordResponse)
async def update_training_record(record_id: str, payload: dict, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        allowed = {"training_category", "training_type", "training_date", "expiry_date", "certificate_number", "status", "notes"}
        updates = {k: payload[k] for k in payload if k in allowed}
        if not updates:
            raise HTTPException(status_code=400, detail="No updatable fields provided")
        updates["updated_at"] = now
        updates["updated_by"] = actor
        set_clause = ", ".join([f"{k} = ?" for k in updates])
        params = list(updates.values()) + [record_id]
        await db.execute(f"UPDATE training_records SET {set_clause} WHERE record_id = ?", params)
        await db.commit()
        cursor = await db.execute("SELECT * FROM training_records WHERE record_id = ?", (record_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Training record not found")
        return TrainingRecordResponse(**dict(row))
    finally:
        await db.close()


@router.delete("/training-records/{record_id}", status_code=204)
async def delete_training_record(record_id: str, request: Request):
    _check(request, "safety:create")
    db = await get_db()
    try:
        await db.execute("DELETE FROM training_records WHERE record_id = ?", (record_id,))
        await db.commit()
    finally:
        await db.close()
    return Response(status_code=204)


# ==================== MAINTENANCE MANAGEMENT ====================

@router.post("/maintenance-records", response_model=MaintenanceRecordResponse, status_code=201)
async def create_maintenance_record(record: MaintenanceRecordCreate, request: Request):
    _check(request, "aircraft:manage")
    actor = _actor(request)
    record_id = _gen_id("MAINT")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO maintenance_records (record_id, aircraft_registration, maintenance_type, description, performed_by, performed_at, next_due, status, notes, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (record_id, record.aircraft_registration, record.maintenance_type, record.description, record.performed_by, record.performed_at, record.next_due, "completed", record.notes, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return MaintenanceRecordResponse(record_id=record_id, aircraft_registration=record.aircraft_registration, maintenance_type=record.maintenance_type, description=record.description, performed_by=record.performed_by, performed_at=record.performed_at, next_due=record.next_due, status="completed", notes=record.notes, created_at=now, updated_at=now)


@router.get("/maintenance-records", response_model=List[MaintenanceRecordResponse])
async def list_maintenance_records(request: Request, aircraft_registration: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "aircraft:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if aircraft_registration:
            conditions.append("aircraft_registration = ?")
            params.append(aircraft_registration)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM maintenance_records WHERE {where} ORDER BY performed_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [MaintenanceRecordResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/maintenance-records/{record_id}", response_model=MaintenanceRecordResponse)
async def update_maintenance_record(record_id: str, payload: dict, request: Request):
    _check(request, "aircraft:manage")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        allowed = {"aircraft_registration", "maintenance_type", "description", "performed_by", "performed_at", "next_due", "status", "notes"}
        updates = {k: payload[k] for k in payload if k in allowed}
        if not updates:
            raise HTTPException(status_code=400, detail="No updatable fields provided")
        updates["updated_at"] = now
        updates["updated_by"] = actor
        set_clause = ", ".join([f"{k} = ?" for k in updates])
        params = list(updates.values()) + [record_id]
        await db.execute(f"UPDATE maintenance_records SET {set_clause} WHERE record_id = ?", params)
        await db.commit()
        cursor = await db.execute("SELECT * FROM maintenance_records WHERE record_id = ?", (record_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Maintenance record not found")
        return MaintenanceRecordResponse(**dict(row))
    finally:
        await db.close()


@router.delete("/maintenance-records/{record_id}", status_code=204)
async def delete_maintenance_record(record_id: str, request: Request):
    _check(request, "aircraft:manage")
    db = await get_db()
    try:
        await db.execute("DELETE FROM maintenance_records WHERE record_id = ?", (record_id,))
        await db.commit()
    finally:
        await db.close()
    return Response(status_code=204)


# ==================== APP SETTINGS ====================
@router.get("/app-settings/{key}")
async def get_app_setting(key: str, request: Request):
    _check(request, "settings:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Setting not found")
        return {"key": key, "value": row["value"]}
    finally:
        await db.close()


@router.put("/app-settings/{key}")
async def update_app_setting(key: str, payload: dict, request: Request):
    _check(request, "settings:manage")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        cursor = await db.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Setting not found")
        await db.execute(
            "UPDATE app_settings SET value = ?, updated_at = ? WHERE key = ?",
            (str(payload.get("value")), now, key),
        )
        await db.commit()
    finally:
        await db.close()
    return {"key": key, "value": payload.get("value")}


# ==================== CREW MANAGEMENT ====================
@router.post("/crew-members", response_model=CrewMemberResponse, status_code=201)
async def create_crew_member(crew: CrewMemberCreate, request: Request):
    _check(request, "personnel:manage")
    actor = _actor(request)
    crew_id = _gen_id("CREW")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO crew_members (crew_id, full_name, role, base, status, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?)",
            (crew_id, crew.full_name, crew.role, crew.base, crew.status, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return CrewMemberResponse(crew_id=crew_id, full_name=crew.full_name, role=crew.role, base=crew.base, status=crew.status, created_at=now, updated_at=now)


@router.get("/crew-members", response_model=List[CrewMemberResponse])
async def list_crew_members(request: Request, role: Optional[str] = None, status: Optional[str] = None):
    _check(request, "personnel:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if role:
            conditions.append("role = ?")
            params.append(role)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM crew_members WHERE {where} ORDER BY full_name", params)
        rows = await cursor.fetchall()
        return [CrewMemberResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/crew-members/{crew_id}", response_model=CrewMemberResponse)
async def update_crew_member(crew_id: str, payload: dict, request: Request):
    _check(request, "personnel:manage")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        allowed = {"full_name", "role", "base", "status"}
        updates = {k: payload[k] for k in payload if k in allowed}
        if not updates:
            raise HTTPException(status_code=400, detail="No updatable fields provided")
        updates["updated_at"] = now
        updates["updated_by"] = actor
        set_clause = ", ".join([f"{k} = ?" for k in updates])
        params = list(updates.values()) + [crew_id]
        await db.execute(f"UPDATE crew_members SET {set_clause} WHERE crew_id = ?", params)
        await db.commit()
        cursor = await db.execute("SELECT * FROM crew_members WHERE crew_id = ?", (crew_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Crew member not found")
        return CrewMemberResponse(**dict(row))
    finally:
        await db.close()


@router.delete("/crew-members/{crew_id}", status_code=204)
async def delete_crew_member(crew_id: str, request: Request):
    _check(request, "personnel:manage")
    db = await get_db()
    try:
        await db.execute("DELETE FROM crew_members WHERE crew_id = ?", (crew_id,))
        await db.commit()
    finally:
        await db.close()
    return Response(status_code=204)


# ==================== DUTY RECORDS ====================
@router.post("/duty-records", response_model=DutyRecordResponse, status_code=201)
async def create_duty_record(duty: DutyRecordCreate, request: Request):
    _check(request, "personnel:manage")
    actor = _actor(request)
    duty_id = _gen_id("DUTY")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO duty_records (duty_id, crew_id, duty_start, duty_end, aircraft_reg, role, location, block_hours, notes, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (duty_id, duty.crew_id, duty.duty_start, duty.duty_end, duty.aircraft_reg, duty.role, duty.location, duty.block_hours, duty.notes, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return DutyRecordResponse(duty_id=duty_id, crew_id=duty.crew_id, duty_start=duty.duty_start, duty_end=duty.duty_end, aircraft_reg=duty.aircraft_reg, role=duty.role, location=duty.location, block_hours=duty.block_hours, notes=duty.notes, created_at=now, updated_at=now)


@router.get("/duty-records", response_model=List[DutyRecordResponse])
async def list_duty_records(request: Request, crew_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "personnel:read")
    db = await get_db()
    try:
        where = "crew_id = ?" if crew_id else "1=1"
        params = [crew_id] if crew_id else []
        cursor = await db.execute(f"SELECT * FROM duty_records WHERE {where} ORDER BY duty_start DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [DutyRecordResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/duty-records/{duty_id}", response_model=DutyRecordResponse)
async def update_duty_record(duty_id: str, payload: dict, request: Request):
    _check(request, "personnel:manage")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        allowed = {"duty_start", "duty_end", "aircraft_reg", "role", "location", "block_hours", "notes"}
        updates = {k: payload[k] for k in payload if k in allowed}
        if not updates:
            raise HTTPException(status_code=400, detail="No updatable fields provided")
        updates["updated_at"] = now
        updates["updated_by"] = actor
        set_clause = ", ".join([f"{k} = ?" for k in updates])
        params = list(updates.values()) + [duty_id]
        await db.execute(f"UPDATE duty_records SET {set_clause} WHERE duty_id = ?", params)
        await db.commit()
        cursor = await db.execute("SELECT * FROM duty_records WHERE duty_id = ?", (duty_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Duty record not found")
        return DutyRecordResponse(**dict(row))
    finally:
        await db.close()


@router.delete("/duty-records/{duty_id}", status_code=204)
async def delete_duty_record(duty_id: str, request: Request):
    _check(request, "personnel:manage")
    db = await get_db()
    try:
        await db.execute("DELETE FROM duty_records WHERE duty_id = ?", (duty_id,))
        await db.commit()
    finally:
        await db.close()
    return Response(status_code=204)


@router.get("/duty-records/fdtl-validation")
async def validate_fdtl(request: Request, crew_id: Optional[str] = None):
    _check(request, "personnel:read")
    db = await get_db()
    try:
        settings_cursor = await db.execute("SELECT key, value FROM app_settings WHERE key IN ('fdtl_max_duty_hours','fdtl_max_block_hours','fdtl_min_rest_hours')")
        settings = {row["key"]: float(row["value"]) async for row in settings_cursor}
        max_duty = settings.get("fdtl_max_duty_hours", 14.0)
        max_block = settings.get("fdtl_max_block_hours", 12.0)
        min_rest = settings.get("fdtl_min_rest_hours", 10.0)

        where = "WHERE crew_id = ?" if crew_id else ""
        params = [crew_id] if crew_id else []
        cursor = await db.execute(f"SELECT * FROM duty_records {where} ORDER BY duty_start DESC LIMIT 50", params)
        rows = await cursor.fetchall()

        warnings = []
        for i, row in enumerate(rows):
            duty = dict(row)
            duty_start = datetime.fromisoformat(duty["duty_start"])
            duty_end = datetime.fromisoformat(duty["duty_end"])
            duration_hours = (duty_end - duty_start).total_seconds() / 3600.0
            if duration_hours > max_duty:
                warnings.append({
                    "duty_id": duty["duty_id"],
                    "type": "duty_exceeded",
                    "message": f"Duty duration {duration_hours:.1f}h exceeds max {max_duty}h",
                    "duration_hours": duration_hours,
                })
            block = duty.get("block_hours")
            if block is not None and block > max_block:
                warnings.append({
                    "duty_id": duty["duty_id"],
                    "type": "block_exceeded",
                    "message": f"Block hours {block:.1f}h exceeds max {max_block}h",
                    "block_hours": block,
                })
            if i + 1 < len(rows):
                next_duty = dict(rows[i + 1])
                next_end = datetime.fromisoformat(next_duty["duty_end"])
                rest_hours = (duty_start - next_end).total_seconds() / 3600.0
                if rest_hours < min_rest:
                    warnings.append({
                        "duty_id": duty["duty_id"],
                        "type": "rest_insufficient",
                        "message": f"Rest period {rest_hours:.1f}h below min {min_rest}h",
                        "rest_hours": rest_hours,
                    })
        return {"settings": settings, "warnings": warnings}
    finally:
        await db.close()


# ==================== CREW QUALIFICATIONS ====================
@router.post("/crew-qualifications", response_model=CrewQualificationResponse, status_code=201)
async def create_crew_qualification(qual: CrewQualificationCreate, request: Request):
    _check(request, "personnel:manage")
    actor = _actor(request)
    qual_id = _gen_id("QUAL")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO crew_qualifications (qual_id, crew_id, qual_type, rating, issue_date, expiry_date, status, notes, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (qual_id, qual.crew_id, qual.qual_type, qual.rating, qual.issue_date, qual.expiry_date, "valid", qual.notes, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()

    # Notify on near-expiry
    _notify_qualification_expiry(qual.crew_id, qual.qual_type, qual.expiry_date)

    return CrewQualificationResponse(qual_id=qual_id, crew_id=qual.crew_id, qual_type=qual.qual_type, rating=qual.rating, issue_date=qual.issue_date, expiry_date=qual.expiry_date, status="valid", notes=qual.notes, created_at=now, updated_at=now)


@router.get("/crew-qualifications", response_model=List[CrewQualificationResponse])
async def list_crew_qualifications(request: Request, crew_id: Optional[str] = None, status: Optional[str] = None):
    _check(request, "personnel:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if crew_id:
            conditions.append("crew_id = ?")
            params.append(crew_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM crew_qualifications WHERE {where} ORDER BY expiry_date ASC", params)
        rows = await cursor.fetchall()
        return [CrewQualificationResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/crew-qualifications/{qual_id}", response_model=CrewQualificationResponse)
async def update_crew_qualification(qual_id: str, payload: dict, request: Request):
    _check(request, "personnel:manage")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        allowed = {"qual_type", "rating", "issue_date", "expiry_date", "status", "notes"}
        updates = {k: payload[k] for k in payload if k in allowed}
        if not updates:
            raise HTTPException(status_code=400, detail="No updatable fields provided")
        updates["updated_at"] = now
        updates["updated_by"] = actor
        set_clause = ", ".join([f"{k} = ?" for k in updates])
        params = list(updates.values()) + [qual_id]
        await db.execute(f"UPDATE crew_qualifications SET {set_clause} WHERE qual_id = ?", params)
        await db.commit()
        cursor = await db.execute("SELECT * FROM crew_qualifications WHERE qual_id = ?", (qual_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Qualification not found")
        result = CrewQualificationResponse(**dict(row))
        if "expiry_date" in updates:
            _notify_qualification_expiry(result.crew_id, result.qual_type, result.expiry_date)
        return result
    finally:
        await db.close()


@router.delete("/crew-qualifications/{qual_id}", status_code=204)
async def delete_crew_qualification(qual_id: str, request: Request):
    _check(request, "personnel:manage")
    db = await get_db()
    try:
        await db.execute("DELETE FROM crew_qualifications WHERE qual_id = ?", (qual_id,))
        await db.commit()
    finally:
        await db.close()
    return Response(status_code=204)


@router.get("/crew-qualifications/currency-alerts")
async def crew_currency_alerts(request: Request, days: Optional[int] = None):
    _check(request, "personnel:read")
    db = await get_db()
    try:
        warning_days = days
        if warning_days is None:
            cursor = await db.execute("SELECT value FROM app_settings WHERE key = 'crew_currency_warning_days'")
            row = await cursor.fetchone()
            warning_days = int(row["value"]) if row else 30

        from datetime import datetime, timedelta
        cutoff = (datetime.now() + timedelta(days=warning_days)).isoformat()
        cursor = await db.execute(
            "SELECT * FROM crew_qualifications WHERE status = 'valid' AND expiry_date <= ? ORDER BY expiry_date ASC",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        alerts = []
        for row in rows:
            q = dict(row)
            expiry = datetime.fromisoformat(q["expiry_date"])
            days_left = (expiry - datetime.now()).days
            alerts.append({
                "qual_id": q["qual_id"],
                "crew_id": q["crew_id"],
                "qual_type": q["qual_type"],
                "rating": q["rating"],
                "expiry_date": q["expiry_date"],
                "days_left": days_left,
                "message": f"{q['qual_type']} expires in {days_left} day(s)",
            })
        return {"warning_days": warning_days, "alerts": alerts}
    finally:
        await db.close()

@router.post("/outsourced-functions", response_model=OutsourcedFunctionResponse, status_code=201)
async def create_outsourced_function(of: OutsourcedFunctionCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    fid = _gen_id("OF")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO outsourced_functions (function_id, provider_name, scope, contract_sla, applicable_requirements, assessment_date, audit_evidence, issues, actions, status, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, of.provider_name, of.scope, of.contract_sla, of.applicable_requirements, of.assessment_date, of.audit_evidence, of.issues, of.actions, "active", now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return OutsourcedFunctionResponse(function_id=fid, provider_name=of.provider_name, scope=of.scope, contract_sla=of.contract_sla, applicable_requirements=of.applicable_requirements, assessment_date=of.assessment_date, audit_evidence=of.audit_evidence, issues=of.issues, actions=of.actions, status="active", created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/outsourced-functions", response_model=List[OutsourcedFunctionResponse])
async def list_outsourced_functions(request: Request, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM outsourced_functions WHERE status = ? ORDER BY provider_name LIMIT ? OFFSET ?", (status, limit, offset))
        else:
            cursor = await db.execute("SELECT * FROM outsourced_functions ORDER BY provider_name LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [OutsourcedFunctionResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/outsourced-functions/{fid}", response_model=OutsourcedFunctionResponse)
async def update_outsourced_function(fid: str, update: OutsourcedFunctionUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM outsourced_functions WHERE function_id = ?", (fid,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Outsourced function not found")
        updates = []
        params = []
        field_map = {"provider_name": update.provider_name, "scope": update.scope, "contract_sla": update.contract_sla, "applicable_requirements": update.applicable_requirements, "assessment_date": update.assessment_date, "audit_evidence": update.audit_evidence, "issues": update.issues, "actions": update.actions, "status": update.status}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(fid)
            await db.execute(f"UPDATE outsourced_functions SET {', '.join(updates)} WHERE function_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM outsourced_functions WHERE function_id = ?", (fid,))
        row = await cursor.fetchone()
        return OutsourcedFunctionResponse(**dict(row))
    finally:
        await db.close()


# ==================== P2: SAFETY KPIs (SAF-08) ====================

@router.post("/safety-kpis", response_model=SafetyKPIResponse, status_code=201)
async def create_safety_kpi(kpi: SafetyKPICreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    kpi_id = _gen_id("KPI")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO safety_kpis (kpi_id, kpi_name, definition, target, period, current_value, evidence_source, trend, status, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (kpi_id, kpi.kpi_name, kpi.definition, kpi.target, kpi.period, kpi.current_value, kpi.evidence_source, kpi.trend, "active", now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return SafetyKPIResponse(kpi_id=kpi_id, kpi_name=kpi.kpi_name, definition=kpi.definition, target=kpi.target, period=kpi.period, current_value=kpi.current_value, evidence_source=kpi.evidence_source, trend=kpi.trend, status="active", created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/safety-kpis", response_model=List[SafetyKPIResponse])
async def list_safety_kpis(request: Request, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM safety_kpis WHERE status = ? ORDER BY kpi_name LIMIT ? OFFSET ?", (status, limit, offset))
        else:
            cursor = await db.execute("SELECT * FROM safety_kpis ORDER BY kpi_name LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [SafetyKPIResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/safety-kpis/{kpi_id}", response_model=SafetyKPIResponse)
async def update_safety_kpi(kpi_id: str, update: SafetyKPIUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM safety_kpis WHERE kpi_id = ?", (kpi_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Safety KPI not found")
        updates = []
        params = []
        field_map = {"kpi_name": update.kpi_name, "definition": update.definition, "target": update.target, "period": update.period, "current_value": update.current_value, "evidence_source": update.evidence_source, "trend": update.trend, "status": update.status}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(kpi_id)
            await db.execute(f"UPDATE safety_kpis SET {', '.join(updates)} WHERE kpi_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM safety_kpis WHERE kpi_id = ?", (kpi_id,))
        row = await cursor.fetchone()
        return SafetyKPIResponse(**dict(row))
    finally:
        await db.close()


# ==================== P2: SECURITY REVIEW MEETINGS / KPIs (SEC-06) ====================

@router.post("/security-reviews", response_model=SecurityReviewResponse, status_code=201)
async def create_security_review(sr: SecurityReviewCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    rid = _gen_id("SR")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO security_reviews (review_id, meeting_date, attendees, minutes, kpi_measures, audit_findings, inspection_results, corrective_actions, status, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, sr.meeting_date, sr.attendees, sr.minutes, sr.kpi_measures, sr.audit_findings, sr.inspection_results, sr.corrective_actions, "scheduled", now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return SecurityReviewResponse(review_id=rid, meeting_date=sr.meeting_date, attendees=sr.attendees, minutes=sr.minutes, kpi_measures=sr.kpi_measures, audit_findings=sr.audit_findings, inspection_results=sr.inspection_results, corrective_actions=sr.corrective_actions, status="scheduled", created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/security-reviews", response_model=List[SecurityReviewResponse])
async def list_security_reviews(request: Request, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM security_reviews WHERE status = ? ORDER BY meeting_date DESC LIMIT ? OFFSET ?", (status, limit, offset))
        else:
            cursor = await db.execute("SELECT * FROM security_reviews ORDER BY meeting_date DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = await cursor.fetchall()
        return [SecurityReviewResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/security-reviews/{rid}", response_model=SecurityReviewResponse)
async def update_security_review(rid: str, update: SecurityReviewUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM security_reviews WHERE review_id = ?", (rid,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Security review not found")
        updates = []
        params = []
        field_map = {"meeting_date": update.meeting_date, "attendees": update.attendees, "minutes": update.minutes, "kpi_measures": update.kpi_measures, "audit_findings": update.audit_findings, "inspection_results": update.inspection_results, "corrective_actions": update.corrective_actions, "status": update.status}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(rid)
            await db.execute(f"UPDATE security_reviews SET {', '.join(updates)} WHERE review_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM security_reviews WHERE review_id = ?", (rid,))
        row = await cursor.fetchone()
        return SecurityReviewResponse(**dict(row))
    finally:
        await db.close()


# ==================== P2: DG RESPONSIBILITY MATRIX (DG-12) ====================

@router.post("/dg-responsibility-matrix", response_model=DGResponsibilityMatrixResponse, status_code=201)
async def create_dg_matrix(dm: DGResponsibilityMatrixCreate, request: Request):
    _check(request, "safety:create")
    actor = _actor(request)
    mid = _gen_id("DM")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO dg_responsibility_matrix (matrix_id, project_or_route, operation_type, process_stage, responsible_role, escalation_contact, handover_point, status, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, dm.project_or_route, dm.operation_type, dm.process_stage, dm.responsible_role, dm.escalation_contact, dm.handover_point, "active", now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return DGResponsibilityMatrixResponse(matrix_id=mid, project_or_route=dm.project_or_route, operation_type=dm.operation_type, process_stage=dm.process_stage, responsible_role=dm.responsible_role, escalation_contact=dm.escalation_contact, handover_point=dm.handover_point, status="active", created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/dg-responsibility-matrix", response_model=List[DGResponsibilityMatrixResponse])
async def list_dg_matrix(request: Request, project_or_route: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "safety:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if project_or_route:
            conditions.append("project_or_route = ?")
            params.append(project_or_route)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM dg_responsibility_matrix WHERE {where} ORDER BY project_or_route, process_stage LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [DGResponsibilityMatrixResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.patch("/dg-responsibility-matrix/{mid}", response_model=DGResponsibilityMatrixResponse)
async def update_dg_matrix(mid: str, update: DGResponsibilityMatrixUpdate, request: Request):
    _check(request, "safety:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM dg_responsibility_matrix WHERE matrix_id = ?", (mid,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="DG matrix entry not found")
        updates = []
        params = []
        field_map = {"project_or_route": update.project_or_route, "operation_type": update.operation_type, "process_stage": update.process_stage, "responsible_role": update.responsible_role, "escalation_contact": update.escalation_contact, "handover_point": update.handover_point, "status": update.status}
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(mid)
            await db.execute(f"UPDATE dg_responsibility_matrix SET {', '.join(updates)} WHERE matrix_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM dg_responsibility_matrix WHERE matrix_id = ?", (mid,))
        row = await cursor.fetchone()
        return DGResponsibilityMatrixResponse(**dict(row))
    finally:
        await db.close()


# ==================== DEADLINE / ESCALATION ENGINE ====================

@router.get("/deadlines", response_model=dict)
async def get_deadlines(request: Request, days_ahead: int = 30):
    """Aggregate upcoming and overdue deadlines across all entities."""
    _check(request, "compliance:read")
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cutoff = (datetime.now() + timedelta(days=days_ahead)).isoformat()
        deadlines = []

        # 1. Document review due dates
        cursor = await db.execute(
            "SELECT document_id, title, review_due_date, kcaa_approval_required FROM documents WHERE review_due_date IS NOT NULL AND review_due_date <= ?", (cutoff,)
        )
        for row in await cursor.fetchall():
            r = dict(row)
            overdue = r["review_due_date"] < now[:10]
            deadlines.append({
                "entity_type": "document", "entity_id": r["document_id"],
                "title": f"Document review due: {r['title']}",
                "due_date": r["review_due_date"], "overdue": overdue,
                "priority": "high" if r["kcaa_approval_required"] else "medium",
            })

        # 2. Occurrence MOR deadlines
        cursor = await db.execute(
            "SELECT occurrence_id, serial_number, title, mor_deadline, mor_required, status FROM occurrences WHERE mor_required = 1 AND mor_deadline IS NOT NULL AND status != 'closed'"
        )
        for row in await cursor.fetchall():
            r = dict(row)
            overdue = r["mor_deadline"] < now
            deadlines.append({
                "entity_type": "occurrence", "entity_id": r["occurrence_id"],
                "title": f"MOR submission: {r['title']} ({r['serial_number']})",
                "due_date": r["mor_deadline"], "overdue": overdue, "priority": "critical",
            })

        # 3. Corrective action due dates
        cursor = await db.execute(
            "SELECT car_id, title, due_date, status FROM corrective_actions WHERE due_date IS NOT NULL AND status NOT IN ('closed', 'verified')"
        )
        for row in await cursor.fetchall():
            r = dict(row)
            overdue = r["due_date"] < now[:10]
            deadlines.append({
                "entity_type": "corrective_action", "entity_id": r["car_id"],
                "title": f"CAR due: {r['title']}", "due_date": r["due_date"],
                "overdue": overdue, "priority": "high",
            })

        # 4. Training expiry
        cursor = await db.execute(
            "SELECT record_id, person_id, training_type, expiry_date FROM dg_training_records WHERE expiry_date IS NOT NULL AND expiry_date <= ?", (cutoff,)
        )
        for row in await cursor.fetchall():
            r = dict(row)
            overdue = r["expiry_date"] < now[:10]
            deadlines.append({
                "entity_type": "dg_training", "entity_id": r["record_id"],
                "title": f"DG training expiry: {r['training_type']} - {r['person_id']}",
                "due_date": r["expiry_date"], "overdue": overdue, "priority": "medium",
            })

        # 5. ROC expiry (90-day notice)
        cursor = await db.execute("SELECT roc_id, roc_number, expiry_date FROM roc_register WHERE expiry_date IS NOT NULL")
        for row in await cursor.fetchall():
            r = dict(row)
            overdue = r["expiry_date"] < now[:10]
            notice_date = r["expiry_date"]
            deadlines.append({
                "entity_type": "roc", "entity_id": r["roc_id"],
                "title": f"ROC expiry: {r['roc_number']}", "due_date": r["expiry_date"],
                "overdue": overdue, "priority": "critical",
            })

        # 6. Distribution acknowledgements overdue
        cursor = await db.execute(
            "SELECT d.distribution_id, dv.document_id, d.recipient_id, d.acknowledged_at, d.sent_at FROM distributions d JOIN document_versions dv ON d.version_id = dv.version_id WHERE d.acknowledged_at IS NULL AND d.sent_at IS NOT NULL"
        )
        for row in await cursor.fetchall():
            r = dict(row)
            dist_date = r["sent_at"][:10]
            overdue = (datetime.now() - datetime.fromisoformat(dist_date)).days > 7
            deadlines.append({
                "entity_type": "distribution", "entity_id": r["distribution_id"],
                "title": f"Acknowledgement overdue: {r['document_id']} → {r['recipient_id']}",
                "due_date": dist_date, "overdue": overdue, "priority": "medium",
            })

        # 7. Personnel license expiry
        cursor = await db.execute(
            "SELECT license_id, person_id, license_type, expiry_date FROM personnel_licenses WHERE expiry_date IS NOT NULL AND expiry_date <= ?", (cutoff,)
        )
        for row in await cursor.fetchall():
            r = dict(row)
            overdue = r["expiry_date"] < now[:10]
            deadlines.append({
                "entity_type": "personnel_license", "entity_id": r["license_id"],
                "title": f"License expiry: {r['license_type']} - {r['person_id']}",
                "due_date": r["expiry_date"], "overdue": overdue, "priority": "high",
            })

        # 8. Aircraft insurance expiry
        cursor = await db.execute(
            "SELECT insurance_id, aircraft_id, insurance_type, expiry_date FROM aircraft_insurance WHERE expiry_date IS NOT NULL AND expiry_date <= ?", (cutoff,)
        )
        for row in await cursor.fetchall():
            r = dict(row)
            overdue = r["expiry_date"] < now[:10]
            deadlines.append({
                "entity_type": "aircraft_insurance", "entity_id": r["insurance_id"],
                "title": f"Insurance expiry: {r['insurance_type']} - {r['aircraft_id']}",
                "due_date": r["expiry_date"], "overdue": overdue, "priority": "critical",
            })

        # 9. Aircraft document expiry
        cursor = await db.execute(
            "SELECT doc_id, aircraft_id, document_type, expiry_date FROM aircraft_documents WHERE expiry_date IS NOT NULL AND expiry_date <= ?", (cutoff,)
        )
        for row in await cursor.fetchall():
            r = dict(row)
            overdue = r["expiry_date"] < now[:10]
            deadlines.append({
                "entity_type": "aircraft_document", "entity_id": r["doc_id"],
                "title": f"Aircraft doc expiry: {r['document_type']} - {r['aircraft_id']}",
                "due_date": r["expiry_date"], "overdue": overdue, "priority": "high",
            })

        overdue_count = sum(1 for d in deadlines if d["overdue"])
        upcoming = [d for d in deadlines if not d["overdue"]]
        overdue = [d for d in deadlines if d["overdue"]]

        return {
            "total": len(deadlines),
            "overdue_count": overdue_count,
            "upcoming_count": len(upcoming),
            "overdue": sorted(overdue, key=lambda x: x["due_date"]),
            "upcoming": sorted(upcoming, key=lambda x: x["due_date"]),
        }
    finally:
        await db.close()


# ==================== NOTIFICATION ENDPOINTS ====================

@router.get("/notifications/status")
async def notification_status(request: Request):
    """Get notification system status."""
    _check(request, "compliance:read")
    return {
        "enabled": NOTIFICATION_ENABLED,
        "smtp_configured": bool(SMTP_HOST),
        "smtp_host": SMTP_HOST or "not configured",
    }


@router.get("/notifications")
async def list_notifications(request: Request, recipient: str = None, status: str = None, limit: int = 50):
    """List notifications from DB."""
    _check(request, "compliance:read")
    notifs = await get_notifications(recipient, status, limit)
    return {"notifications": notifs, "total": len(notifs)}


@router.get("/notifications/unread-count")
async def unread_notification_count(request: Request):
    """Get count of unread notifications."""
    _check(request, "compliance:read")
    notifs = await get_notifications(status="pending", limit=1000)
    # Also count 'logged' and 'sent' as unread (not yet read)
    unread = [n for n in notifs if n.get("read_at") is None]
    return {"unread_count": len(unread)}


@router.patch("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, request: Request):
    """Mark a notification as read."""
    _check(request, "compliance:read")
    await mark_notification_read(notification_id)
    return {"status": "read", "notification_id": notification_id}


@router.post("/notifications/check")
async def trigger_notification_check(request: Request):
    """Manually trigger a deadline notification check."""
    _check(request, "compliance:manage")
    db = await get_db()
    try:
        count = await check_and_notify(db)
        return {"notifications_sent": count, "status": "completed"}
    finally:
        await db.close()


@router.post("/notifications/send")
async def send_notification(request: Request, to: str, subject: str, body: str):
    """Send a manual notification."""
    _check(request, "compliance:manage")
    success = send_email(to, subject, body)
    return {"success": success, "to": to, "subject": subject}


# ==================== NOTIFICATION PREFERENCES ====================

@router.get("/notification-preferences")
async def get_notification_preferences(request: Request):
    """Get notification preferences for the current user."""
    _check(request, "compliance:read")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM notification_preferences WHERE user_id = ?", (actor,))
        row = await cursor.fetchone()
        if not row:
            # Return defaults
            return {
                "user_id": actor,
                "email_enabled": True,
                "document_review_hours": 48,
                "mor_deadline_hours": 24,
                "car_due_days": 3,
                "roc_expiry_days": 90,
                "distribution_ack_days": 7,
            }
        return dict(row)
    finally:
        await db.close()


@router.put("/notification-preferences")
async def update_notification_preferences(request: Request, email_enabled: bool = True, document_review_hours: int = 48, mor_deadline_hours: int = 24, car_due_days: int = 3, roc_expiry_days: int = 90, distribution_ack_days: int = 7):
    """Update notification preferences for the current user."""
    _check(request, "compliance:read")
    actor = _actor(request)
    db = await get_db()
    try:
        now = now_iso()
        import uuid
        pref_id = f"NP-{uuid.uuid4().hex[:8].upper()}"
        cursor = await db.execute("SELECT preference_id FROM notification_preferences WHERE user_id = ?", (actor,))
        existing = await cursor.fetchone()
        if existing:
            await db.execute(
                """UPDATE notification_preferences SET email_enabled = ?, document_review_hours = ?, mor_deadline_hours = ?, car_due_days = ?, roc_expiry_days = ?, distribution_ack_days = ?, updated_at = ? WHERE user_id = ?""",
                (1 if email_enabled else 0, document_review_hours, mor_deadline_hours, car_due_days, roc_expiry_days, distribution_ack_days, now, actor),
            )
        else:
            await db.execute(
                """INSERT INTO notification_preferences (preference_id, user_id, email_enabled, document_review_hours, mor_deadline_hours, car_due_days, roc_expiry_days, distribution_ack_days, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (pref_id, actor, 1 if email_enabled else 0, document_review_hours, mor_deadline_hours, car_due_days, roc_expiry_days, distribution_ack_days, now, now),
            )
        await db.commit()
        return {"status": "updated", "user_id": actor}
    finally:
        await db.close()
