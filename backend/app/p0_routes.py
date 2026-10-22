"""P0 API routes."""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional, List
from datetime import datetime
import uuid
import json

from .database import get_db
from .audit import log_audit_event
from .rbac import has_permission, check_sod
from .p0_models import *
from .p0_auth import P0AuthMiddleware

router = APIRouter()


def _actor(request: Request) -> str:
    return getattr(request.state, "actor", "admin")


def _role(request: Request) -> str:
    return getattr(request.state, "role", "system_admin")


def _check(request: Request, perm: str):
    if not has_permission(_role(request), perm):
        raise HTTPException(status_code=403, detail=f"Permission denied: {perm}")


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def now_iso() -> str:
    return datetime.now().isoformat()


# --- Documents ---
@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(request: Request, status: Optional[str] = None, doc_class: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "document:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if doc_class:
            conditions.append("doc_class = ?")
            params.append(doc_class)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM documents WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [DocumentResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def create_document(doc: DocumentCreate, request: Request):
    _check(request, "document:create")
    actor = _actor(request)
    doc_id = _gen_id("DOC")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO documents (document_id, title, doc_class, classification, status, owner_id, description, tags, created_at, updated_at, created_by, updated_by, kcaa_approval_required, review_due_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, doc.title, doc.doc_class, doc.classification, "draft", doc.owner_id, doc.description, doc.tags, now, now, actor, actor, 1 if doc.kcaa_approval_required else 0, doc.review_due_date),
        )
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("document", doc_id, "created", actor, {"title": doc.title, "kcaa_required": doc.kcaa_approval_required})
    return DocumentResponse(document_id=doc_id, title=doc.title, doc_class=doc.doc_class, classification=doc.classification, status="draft", owner_id=doc.owner_id, description=doc.description, tags=doc.tags, current_version_id=None, kcaa_approval_required=doc.kcaa_approval_required, review_due_date=doc.review_due_date, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, request: Request):
    _check(request, "document:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM documents WHERE document_id = ?", (doc_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentResponse(**dict(row))
    finally:
        await db.close()


@router.patch("/documents/{doc_id}", response_model=DocumentResponse)
async def update_document(doc_id: str, update: DocumentUpdate, request: Request):
    _check(request, "document:update")
    actor = _actor(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM documents WHERE document_id = ?", (doc_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Document not found")
        updates = []
        params = []
        for col, val in {"title": update.title, "doc_class": update.doc_class, "classification": update.classification, "description": update.description, "tags": update.tags, "owner_id": update.owner_id}.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val)
        if updates:
            updates.append("updated_at = ?")
            params.append(now_iso())
            updates.append("updated_by = ?")
            params.append(actor)
            params.append(doc_id)
            await db.execute(f"UPDATE documents SET {', '.join(updates)} WHERE document_id = ?", params)
            await db.commit()
        cursor = await db.execute("SELECT * FROM documents WHERE document_id = ?", (doc_id,))
        row = await cursor.fetchone()
        return DocumentResponse(**dict(row))
    finally:
        await db.close()


# --- Versions ---
@router.get("/documents/{doc_id}/versions", response_model=List[DocumentVersionResponse])
async def list_versions(doc_id: str, request: Request):
    _check(request, "document:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM document_versions WHERE document_id = ? ORDER BY created_at DESC", (doc_id,))
        rows = await cursor.fetchall()
        return [DocumentVersionResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/versions", response_model=DocumentVersionResponse, status_code=201)
async def create_version(ver: DocumentVersionCreate, request: Request):
    _check(request, "document:create")
    actor = _actor(request)
    ver_id = _gen_id("VER")
    now = now_iso()
    db = await get_db()
    try:
        # Check if parent document exists
        cursor = await db.execute("SELECT kcaa_approval_required FROM documents WHERE document_id = ?", (ver.document_id,))
        doc_row = await cursor.fetchone()
        if not doc_row:
            raise HTTPException(status_code=404, detail="Document not found")
        kcaa_required = doc_row["kcaa_approval_required"]
        
        await db.execute(
            "INSERT INTO document_versions (version_id, document_id, version_number, state, content, change_summary, kcaa_approved, kcaa_approved_by, kcaa_approved_at, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ver_id, ver.document_id, ver.version_number, "draft", ver.content, ver.change_summary, 0, None, None, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return DocumentVersionResponse(version_id=ver_id, document_id=ver.document_id, version_number=ver.version_number, state="draft", content=ver.content, change_summary=ver.change_summary, approved_by=None, approved_at=None, kcaa_approved=0, kcaa_approved_by=None, kcaa_approved_at=None, published_at=None, kcaa_reference=None, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.patch("/versions/{version_id}/state", response_model=DocumentVersionResponse)
async def transition_version_state(version_id: str, request: Request, state: str = None):
    _check(request, "document:read")
    actor = _actor(request)
    role = _role(request)
    # Permission checks based on target state
    if state in ("approved", "kcaa_approved"):
        if not has_permission(role, "document:approve"):
            raise HTTPException(status_code=403, detail="Approve permission required")
    if state == "published":
        if not has_permission(role, "document:publish"):
            raise HTTPException(status_code=403, detail="Publish permission required")
    if state in ("draft", "in_review"):
        if not has_permission(role, "document:update"):
            raise HTTPException(status_code=403, detail="Update permission required")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM document_versions WHERE version_id = ?", (version_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Version not found")
        row = dict(row)
        # Check if parent document requires KCAA approval
        cursor = await db.execute("SELECT kcaa_approval_required FROM documents WHERE document_id = ?", (row["document_id"],))
        doc_row = await cursor.fetchone()
        kcaa_required = doc_row["kcaa_approval_required"] if doc_row else 0
        # Permission checks for state transitions
        if state in ("approved", "kcaa_approved", "published"):
            if not has_permission(role, "document:approve"):
                raise HTTPException(status_code=403, detail="Approve permission required")
        if state == "published":
            if not has_permission(role, "document:publish"):
                raise HTTPException(status_code=403, detail="Publish permission required")
            # SoD check
            if not check_sod("version", "publish", actor, row["created_by"]):
                raise HTTPException(status_code=403, detail="Cannot publish own version (SoD)")
            # KCAA gate: if document requires KCAA approval, version must be kcaa_approved first
            if kcaa_required and row["kcaa_approved"] != 1:
                raise HTTPException(status_code=403, detail="KCAA approval required before publishing")
        updates = ["state = ?", "updated_at = ?", "updated_by = ?"]
        params = [state, now_iso(), actor]
        if state == "approved":
            updates.append("approved_by = ?")
            params.append(actor)
            updates.append("approved_at = ?")
            params.append(now_iso())
        if state == "kcaa_approved":
            updates.append("kcaa_approved = 1")
            updates.append("kcaa_approved_by = ?")
            params.append(actor)
            updates.append("kcaa_approved_at = ?")
            params.append(now_iso())
        if state == "published":
            updates.append("published_at = ?")
            params.append(now_iso())
        params.append(version_id)
        await db.execute(f"UPDATE document_versions SET {', '.join(updates)} WHERE version_id = ?", params)
        await db.commit()
        cursor = await db.execute("SELECT * FROM document_versions WHERE version_id = ?", (version_id,))
        row = await cursor.fetchone()
        return DocumentVersionResponse(**dict(row))
    finally:
        await db.close()


# --- Document Content ---
@router.get("/documents/{doc_id}/content", response_model=DocumentContentResponse)
async def get_document_content(doc_id: str, request: Request):
    """Get the latest version content of a document."""
    _check(request, "document:read")
    db = await get_db()
    try:
        # Get latest version by created_at
        cursor = await db.execute(
            "SELECT * FROM document_versions WHERE document_id = ? ORDER BY created_at DESC LIMIT 1",
            (doc_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document version not found")
        row = dict(row)
        return DocumentContentResponse(
            document_id=row["document_id"],
            version_id=row["version_id"],
            version_number=row["version_number"],
            state=row["state"],
            content=row["content"],
            change_summary=row["change_summary"],
            kcaa_approved=row["kcaa_approved"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    finally:
        await db.close()


@router.put("/documents/{doc_id}/content", response_model=DocumentContentResponse)
async def update_document_content(doc_id: str, update: DocumentContentUpdate, request: Request):
    """Update document content by creating a new draft version."""
    _check(request, "document:update")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        # Verify document exists
        cursor = await db.execute("SELECT document_id, kcaa_approval_required FROM documents WHERE document_id = ?", (doc_id,))
        doc_row = await cursor.fetchone()
        if not doc_row:
            raise HTTPException(status_code=404, detail="Document not found")
        kcaa_required = doc_row["kcaa_approval_required"]

        # Get latest version number to increment
        cursor = await db.execute(
            "SELECT version_number FROM document_versions WHERE document_id = ? ORDER BY created_at DESC LIMIT 1",
            (doc_id,),
        )
        ver_row = await cursor.fetchone()
        current_ver = ver_row["version_number"] if ver_row else "00.00.00"

        # Parse and increment patch version
        try:
            parts = current_ver.split(".")
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2]) + 1
            new_ver = f"{major:02d}.{minor:02d}.{patch:02d}"
        except Exception:
            new_ver = update.version_number or "00.01.01"

        ver_id = _gen_id("VER")
        kcaa_required_bool = kcaa_required == 1

        await db.execute(
            """INSERT INTO document_versions
               (version_id, document_id, version_number, state, content, change_summary,
                kcaa_approved, kcaa_approved_by, kcaa_approved_at, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ver_id, doc_id, new_ver, "draft", update.content, update.change_summary,
                1 if kcaa_required_bool else 0,
                actor if kcaa_required_bool else None,
                now if kcaa_required_bool else None,
                now, now, actor, actor,
            ),
        )
        await db.commit()

        return DocumentContentResponse(
            document_id=doc_id,
            version_id=ver_id,
            version_number=new_ver,
            state="draft",
            content=update.content,
            change_summary=update.change_summary,
            kcaa_approved=1 if kcaa_required_bool else 0,
            created_at=now,
            updated_at=now,
        )
    finally:
        await db.close()


# --- Change Requests ---
@router.get("/change-requests", response_model=List[ChangeRequestResponse])
async def list_change_requests(request: Request, status: Optional[str] = None, document_id: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "document:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if document_id:
            conditions.append("document_id = ?")
            params.append(document_id)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM change_requests WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [ChangeRequestResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/change-requests", response_model=ChangeRequestResponse, status_code=201)
async def create_change_request(cr: ChangeRequestCreate, request: Request):
    _check(request, "change_request:create")
    actor = _actor(request)
    cr_id = _gen_id("CR")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO change_requests (cr_id, document_id, version_id, title, description, change_type, status, requester_id, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (cr_id, cr.document_id, cr.version_id, cr.title, cr.description, cr.change_type, "open", actor, now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    await log_audit_event("change_request", cr_id, "created", actor, {"title": cr.title})
    return ChangeRequestResponse(cr_id=cr_id, document_id=cr.document_id, version_id=cr.version_id, title=cr.title, description=cr.description, change_type=cr.change_type, status="open", requester_id=actor, created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.patch("/change-requests/{cr_id}", response_model=ChangeRequestResponse)
async def update_change_request(cr_id: str, request: Request, status: Optional[str] = None, reviewer_id: Optional[str] = None, approver_id: Optional[str] = None):
    _check(request, "change_request:review")
    actor = _actor(request)
    role = _role(request)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM change_requests WHERE cr_id = ?", (cr_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Change request not found")
        row = dict(row)
        updates = []
        params = []
        if status:
            if status == "approved":
                if not has_permission(role, "change_request:approve"):
                    raise HTTPException(status_code=403, detail="Approve permission required")
                if not check_sod("change_request", "approve", actor, row["requester_id"]):
                    raise HTTPException(status_code=403, detail="Cannot approve own change request (SoD)")
                updates.append("approved_at = ?")
                params.append(now_iso())
                updates.append("approver_id = ?")
                params.append(actor)
            if status == "rejected":
                if not has_permission(role, "change_request:approve"):
                    raise HTTPException(status_code=403, detail="Approve permission required")
                if not check_sod("change_request", "reject", actor, row["requester_id"]):
                    raise HTTPException(status_code=403, detail="Cannot reject own change request (SoD)")
                updates.append("rejected_at = ?")
                params.append(now_iso())
            if status == "in_review":
                updates.append("reviewed_at = ?")
                params.append(now_iso())
                updates.append("reviewer_id = ?")
                params.append(actor)
            updates.append("status = ?")
            params.append(status)
        updates.append("updated_at = ?")
        params.append(now_iso())
        updates.append("updated_by = ?")
        params.append(actor)
        params.append(cr_id)
        await db.execute(f"UPDATE change_requests SET {', '.join(updates)} WHERE cr_id = ?", params)
        await db.commit()
        cursor = await db.execute("SELECT * FROM change_requests WHERE cr_id = ?", (cr_id,))
        row = await cursor.fetchone()
        return ChangeRequestResponse(**dict(row))
    finally:
        await db.close()


# --- Distributions ---
@router.get("/distributions", response_model=List[DistributionResponse])
async def list_distributions(request: Request, version_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0):
    _check(request, "document:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if version_id:
            conditions.append("version_id = ?")
            params.append(version_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = await db.execute(f"SELECT * FROM distributions WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = await cursor.fetchall()
        return [DistributionResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/distributions", response_model=DistributionResponse, status_code=201)
async def create_distribution(dist: DistributionCreate, request: Request):
    _check(request, "distribution:manage")
    actor = _actor(request)
    dist_id = _gen_id("DIST")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO distributions (distribution_id, version_id, recipient_id, channel, status, created_at, updated_at, created_by, updated_by) VALUES (?,?,?,?,?,?,?,?,?)",
            (dist_id, dist.version_id, dist.recipient_id, dist.channel, "pending", now, now, actor, actor),
        )
        await db.commit()
    finally:
        await db.close()
    return DistributionResponse(distribution_id=dist_id, version_id=dist.version_id, recipient_id=dist.recipient_id, channel=dist.channel, status="pending", created_at=now, updated_at=now, created_by=actor, updated_by=actor)


@router.post("/distributions/{dist_id}/acknowledge")
async def acknowledge_distribution(dist_id: str, request: Request):
    _check(request, "document:read")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        await db.execute("UPDATE distributions SET status = 'acknowledged', acknowledged_at = ?, acknowledged_by = ?, updated_at = ?, updated_by = ? WHERE distribution_id = ?", (now, actor, now, actor, dist_id))
        await db.commit()
    finally:
        await db.close()
    return {"status": "acknowledged"}


# --- Retention Rules ---
@router.get("/retention-rules", response_model=List[RetentionRuleResponse])
async def list_retention_rules(request: Request):
    _check(request, "document:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM retention_rules ORDER BY rule_id")
        rows = await cursor.fetchall()
        return [RetentionRuleResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# --- Legal Holds ---
@router.get("/legal-holds", response_model=List[LegalHoldResponse])
async def list_legal_holds(request: Request, status: Optional[str] = None):
    _check(request, "document:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM legal_holds WHERE status = ? ORDER BY imposed_at DESC", (status,))
        else:
            cursor = await db.execute("SELECT * FROM legal_holds ORDER BY imposed_at DESC")
        rows = await cursor.fetchall()
        return [LegalHoldResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/legal-holds", response_model=LegalHoldResponse, status_code=201)
async def create_legal_hold(hold: LegalHoldCreate, request: Request):
    _check(request, "legal_hold:manage")
    actor = _actor(request)
    hold_id = _gen_id("HOLD")
    now = now_iso()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO legal_holds (hold_id, entity_type, entity_id, reason, imposed_by, imposed_at, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?, ?,?)",
            (hold_id, hold.entity_type, hold.entity_id, hold.reason, actor, now, "active", now, now),
        )
        await db.commit()
    finally:
        await db.close()
    return LegalHoldResponse(hold_id=hold_id, entity_type=hold.entity_type, entity_id=hold.entity_id, reason=hold.reason, imposed_by=actor, imposed_at=now, status="active", created_at=now, updated_at=now)


@router.patch("/legal-holds/{hold_id}/release")
async def release_legal_hold(hold_id: str, request: Request):
    _check(request, "legal_hold:manage")
    actor = _actor(request)
    now = now_iso()
    db = await get_db()
    try:
        await db.execute("UPDATE legal_holds SET status = 'released', released_by = ?, released_at = ?, updated_at = ? WHERE hold_id = ?", (actor, now, now, hold_id))
        await db.commit()
    finally:
        await db.close()
    return {"status": "released"}


# --- Compliance Obligations ---
@router.get("/compliance-obligations", response_model=List[ComplianceObligationResponse])
async def list_compliance_obligations(request: Request, status: Optional[str] = None):
    _check(request, "compliance:read")
    db = await get_db()
    try:
        if status:
            cursor = await db.execute("SELECT * FROM compliance_obligations WHERE status = ? ORDER BY due_date", (status,))
        else:
            cursor = await db.execute("SELECT * FROM compliance_obligations ORDER BY due_date")
        rows = await cursor.fetchall()
        return [ComplianceObligationResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# --- Regulatory References ---
@router.get("/regulatory-references", response_model=List[RegulatoryReferenceResponse])
async def list_regulatory_references(request: Request):
    _check(request, "compliance:read")
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM regulatory_references ORDER BY ref_id")
        rows = await cursor.fetchall()
        return [RegulatoryReferenceResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


# --- Audit Events ---
@router.get("/audit-events", response_model=List[AuditEventResponse])
async def list_audit_events(request: Request, entity_type: Optional[str] = None, entity_id: Optional[str] = None, limit: int = 100, offset: int = 0):
    _check(request, "audit:read")
    from .audit import query_audit_events
    events = await query_audit_events(entity_type=entity_type, entity_id=entity_id, limit=limit, offset=offset)
    return [AuditEventResponse(**e) for e in events]


# --- Evidence Pack ---
@router.post("/evidence-pack")
async def generate_evidence_pack(request: Request, entity_type: str = None, entity_id: str = None):
    _check(request, "compliance:read")
    from .audit import get_entity_audit_trail
    import hashlib, json
    events = await get_entity_audit_trail(entity_type or "document", entity_id or "")
    payload = json.dumps({"entity_type": entity_type, "entity_id": entity_id, "events": events}, sort_keys=True, default=str)
    checksum = "sha256-" + hashlib.sha256(payload.encode()).hexdigest()
    return {"entity_type": entity_type, "entity_id": entity_id, "events": events, "checksum": checksum}
