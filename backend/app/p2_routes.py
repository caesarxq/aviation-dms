"""P2 API routes - Document Proposals/Annotations, Personnel Licenses, Aircraft Insurance."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from starlette.datastructures import UploadFile
from typing import Optional, List, Literal
from datetime import datetime, timedelta
import uuid
import json
import os
import stat
from io import BytesIO
from pathlib import Path
import hashlib
from urllib.parse import quote
from PIL import Image
from pypdf import PdfReader

from .database import DB_PATH, get_db
from .audit import log_audit_event
from .rbac import has_permission, check_sod
from .p0_auth import same_principal
from .proposal_engine import detect_proposals

router = APIRouter()

# Upload storage directory is colocated with the database by default so the
# persistent /app/data volume contains both records and file bytes.
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(Path(DB_PATH).parent / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(UPLOAD_DIR, 0o700)
PERSONNEL_UPLOAD_LICENSE_TYPES = frozenset({
    "pilot_license", "medical", "type_rating", "proficiency_check", "dg_training", "security_training",
    "sms_awareness", "crm", "indoctrination", "background_check", "english_proficiency", "avsec",
})
PERSONNEL_UPLOAD_DOCUMENT_TYPES = frozenset({
    "license_copy", "certificate", "medical_cert", "training_record", "other",
})


def _actor(request: Request) -> str:
    return getattr(request.state, "actor", "")


def _role(request: Request) -> str:
    return getattr(request.state, "role", "")


def _check(request: Request, perm: str):
    if not has_permission(_role(request), perm):
        raise HTTPException(status_code=403, detail=f"Permission denied: {perm}")


def _check_proposal_editor(request: Request):
    _check(request, "document:propose")


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def now_iso() -> str:
    return datetime.now().isoformat()


async def _rollback_safely(db):
    """Best-effort rollback while preserving the original mutation/audit error."""
    try:
        await db.rollback()
    except Exception:
        pass


async def _get_latest_version(db, doc_id: str):
    async with db.execute(
        "SELECT * FROM document_versions WHERE document_id = ? ORDER BY created_at DESC LIMIT 1",
        (doc_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document version not found")
    return row


async def _get_proposal_source_version(db, doc_id: str):
    """Prefer the effective published version; preserve draft-only legacy workflows."""
    async with db.execute(
        """SELECT v.* FROM documents d
           JOIN document_versions v ON v.version_id = d.current_version_id
           WHERE d.document_id = ? AND v.state = 'published'""",
        (doc_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        async with db.execute(
            "SELECT * FROM document_versions WHERE document_id = ? AND state = 'published' ORDER BY created_at DESC LIMIT 1",
            (doc_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Effective published document version not found")
    return row


@router.post("/documents/{doc_id}/proposals/preview")
async def preview_proposals(doc_id: str, request: Request):
    """Detect atomic changes without persisting proposal records."""
    _check_proposal_editor(request)
    body = await request.json()
    proposed_content = body.get("proposed_content")
    if not isinstance(proposed_content, str):
        raise HTTPException(status_code=422, detail="proposed_content is required")
    db = await get_db()
    try:
        version = await _get_proposal_source_version(db, doc_id)
        changes = detect_proposals(version["content"] or "", proposed_content, base_version_id=version["version_id"])
        return {"document_id": doc_id, "base_version_id": version["version_id"], "changes": changes, "change_count": len(changes)}
    finally:
        await db.close()


@router.post("/documents/{doc_id}/proposals/batch")
async def create_proposal_batch(doc_id: str, request: Request):
    """Create one independently reviewable proposal for each detected change."""
    _check_proposal_editor(request)
    body = await request.json()
    proposed_content = body.get("proposed_content")
    if not isinstance(proposed_content, str):
        raise HTTPException(status_code=422, detail="proposed_content is required")
    db = await get_db()
    try:
        version = await _get_proposal_source_version(db, doc_id)
        requested_base = body.get("base_version_id")
        if requested_base and requested_base != version["version_id"]:
            raise HTTPException(status_code=409, detail="Document changed while the proposal was being prepared")
        changes = detect_proposals(version["content"] or "", proposed_content, base_version_id=version["version_id"])
        selected = body.get("selected_change_sequences")
        if selected is not None:
            selected_set = {int(item) for item in selected}
            changes = [change for change in changes if change["change_sequence"] in selected_set]
        if not changes:
            raise HTTPException(status_code=422, detail="No changes were detected for submission")

        actor = _actor(request)
        change_set_id = _gen_id("SET")
        now = now_iso()
        created = []
        audit_events = []
        for change in changes:
            fingerprint_payload = "|".join([
                doc_id,
                version["version_id"],
                change["target_ref"],
                change["original_text"],
                change["proposed_text"],
                change["anchor_id"],
            ])
            fingerprint = hashlib.sha256(fingerprint_payload.encode()).hexdigest()
            async with db.execute(
                "SELECT proposal_id FROM document_proposals WHERE document_id = ? AND version_id = ? AND change_fingerprint = ? AND status NOT IN ('rejected', 'applied')",
                (doc_id, version["version_id"], fingerprint),
            ) as cur:
                existing = await cur.fetchone()
            if existing:
                continue
            proposal_id = _gen_id("PROP")
            await db.execute(
                """INSERT INTO document_proposals
                   (proposal_id, document_id, version_id, change_request_id, change_set_id, proposal_type,
                    target_ref, section_number, section_heading, block_type, block_index, anchor_id,
                    context_before, context_after, original_text, proposed_text, original_excerpt_html,
                    proposed_excerpt_html, change_fingerprint, change_sequence, changed_token_count, change_density,
                    grouping_reason, rationale, severity, status,
                    proposer_id, created_at, updated_at, created_by, updated_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    proposal_id, doc_id, version["version_id"], None, change_set_id, change["proposal_type"],
                    change["target_ref"], change["section_number"], change["section_heading"], change["block_type"],
                    change["block_index"], change["anchor_id"], change["context_before"], change["context_after"],
                    change["original_text"], change["proposed_text"], change["original_excerpt_html"],
                    change["proposed_excerpt_html"], fingerprint, change["change_sequence"], change.get("changed_token_count"),
                    change.get("change_density"), change.get("grouping_reason"), body.get("rationale") or "",
                    body.get("severity", "minor"), "draft", actor, now, now, actor, actor,
                ),
            )
            created.append({"proposal_id": proposal_id, **change, "change_fingerprint": fingerprint, "change_set_id": change_set_id, "status": "draft", "proposer_id": actor})
            audit_events.append((proposal_id, change["target_ref"]))
        for proposal_id, target_ref in audit_events:
            await log_audit_event(
                "document_proposal", proposal_id, "created", actor,
                {"doc_id": doc_id, "change_set_id": change_set_id, "target_ref": target_ref}, db=db,
            )
        await db.commit()
        return {"document_id": doc_id, "base_version_id": version["version_id"], "change_set_id": change_set_id, "proposals": created, "created_count": len(created)}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


# ==================== DOCUMENT PROPOSALS ====================

@router.post("/documents/{doc_id}/proposals")
async def create_proposal(doc_id: str, request: Request):
    _check_proposal_editor(request)
    body = await request.json()
    db = await get_db()
    try:
        version = await _get_proposal_source_version(db, doc_id)
        if not version:
            raise HTTPException(status_code=404, detail="Document not found")
        version_id = version["version_id"]

        proposal_id = _gen_id("PROP")
        now = now_iso()
        actor = _actor(request)
        await db.execute(
            """INSERT INTO document_proposals
               (proposal_id, document_id, version_id, change_request_id, proposal_type, target_ref,
                original_text, proposed_text, rationale, severity, status, proposer_id,
                created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                proposal_id, doc_id, version_id, body.get("change_request_id"),
                body.get("proposal_type", "section"), body["target_ref"],
                body.get("original_text"), body.get("proposed_text"),
                body.get("rationale") or "", body.get("severity", "minor"), "draft",
                actor, now, now, actor, actor,
            ),
        )
        await log_audit_event("document_proposal", proposal_id, "created", actor, {"doc_id": doc_id}, db=db)
        await db.commit()
        # Return full proposal
        async with db.execute(
            "SELECT * FROM document_proposals WHERE proposal_id = ?", (proposal_id,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else {"proposal_id": proposal_id, "status": "draft"}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.get("/documents/{doc_id}/proposals")
async def list_proposals(doc_id: str, request: Request, status: Optional[str] = None):
    role = _role(request)
    if not (has_permission(role, "document:read") or has_permission(role, "document:propose")):
        raise HTTPException(status_code=403, detail="Permission denied: document:read or document:propose")
    db = await get_db()
    try:
        query = "SELECT * FROM document_proposals WHERE document_id = ?"
        params = [doc_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.patch("/proposals/{proposal_id}")
async def update_proposal(proposal_id: str, request: Request):
    body = await request.json()
    role = _role(request)
    status = body.get("status")
    valid_statuses = {"submitted", "under_review", "approved", "rejected", "deferred"}
    if "status" in body and status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Invalid proposal status")
    if "reviewer_id" in body:
        raise HTTPException(status_code=403, detail="reviewer_id is assigned by the system")

    review_status = status in {"under_review", "approved", "rejected", "deferred"}
    has_content_edits = bool({"proposed_text", "rationale", "severity"} & set(body))
    has_review_metadata = "disposition" in body
    if has_review_metadata and not review_status:
        raise HTTPException(status_code=400, detail="Review disposition requires a review status")
    if has_content_edits and review_status:
        raise HTTPException(status_code=400, detail="Proposal content cannot be edited during review")
    if review_status or has_review_metadata:
        if not (has_permission(role, "document:update") or has_permission(role, "document:approve")):
            raise HTTPException(status_code=403, detail="Permission denied: document:update or document:approve")
    if has_content_edits or status == "submitted":
        _check_proposal_editor(request)
    if not ("status" in body or has_content_edits or has_review_metadata):
        raise HTTPException(status_code=400, detail="No fields to update")
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM document_proposals WHERE proposal_id = ?", (proposal_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if has_content_edits and row["status"] != "draft":
            raise HTTPException(status_code=400, detail="Only draft proposals can be edited")
        if status == "submitted" and row["status"] != "draft":
            raise HTTPException(status_code=409, detail="Only draft proposals can be submitted")
        if review_status and row["status"] not in ("submitted", "under_review"):
            raise HTTPException(status_code=409, detail="Proposal is not awaiting review")

        actor = _actor(request)
        # SoD: proposer cannot claim review or make a final decision on their own proposal.
        if status in ("under_review", "approved", "rejected", "deferred"):
            if same_principal(request, dict(row)["proposer_id"]):
                raise HTTPException(status_code=403, detail="SoD: proposer cannot review own proposal")
        now = now_iso()
        updates = []
        params = []
        for field in ["status", "proposed_text", "rationale", "severity", "disposition"]:
            if field in body:
                updates.append(f"{field} = ?")
                params.append(body[field])
        if review_status:
            updates.append("reviewed_at = ?")
            params.append(now)
            updates.append("reviewer_id = ?")
            params.append(actor)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        updates.append("updated_at = ?")
        params.append(now)
        updates.append("updated_by = ?")
        params.append(actor)
        params.append(proposal_id)
        await db.execute(
            f"UPDATE document_proposals SET {', '.join(updates)} WHERE proposal_id = ?", params
        )
        await log_audit_event("document_proposal", proposal_id, "updated", actor, body, db=db)
        await db.commit()
        return {"proposal_id": proposal_id, "status": body.get("status", row["status"])}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.delete("/proposals/{proposal_id}")
async def delete_proposal(proposal_id: str, request: Request):
    _check_proposal_editor(request)
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM document_proposals WHERE proposal_id = ?", (proposal_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if row["status"] not in ("draft",):
            raise HTTPException(status_code=400, detail="Only draft proposals can be deleted")
        await db.execute("DELETE FROM document_proposals WHERE proposal_id = ?", (proposal_id,))
        await log_audit_event("document_proposal", proposal_id, "deleted", _actor(request), {}, db=db)
        await db.commit()
        return {"deleted": True}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.post("/proposals/{proposal_id}/apply")
async def apply_proposal(proposal_id: str, request: Request):
    """Apply an approved proposal to create a new draft version."""
    _check(request, "document:publish")
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM document_proposals WHERE proposal_id = ?", (proposal_id,)
        ) as cur:
            prop = await cur.fetchone()
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if prop["status"] != "approved":
            raise HTTPException(status_code=400, detail="Proposal must be approved before applying")

        actor = _actor(request)
        now = now_iso()
        doc_id = prop["document_id"]

        # SoD: proposer cannot apply their own proposal, even if its base is stale.
        if not check_sod("proposal", "apply", actor, prop["proposer_id"], getattr(request.state, "actor_aliases", None)):
            raise HTTPException(status_code=403, detail="Cannot apply own proposal (SoD)")

        # Get current version content and reject stale proposals rather than applying to the wrong text.
        ver = await _get_latest_version(db, doc_id)
        if prop["version_id"] != ver["version_id"]:
            raise HTTPException(status_code=409, detail="Proposal is based on an older document version and must be re-reviewed")

        new_version_id = _gen_id("VER")
        new_version_number = ver["version_number"].rsplit(".", 1)[0] + "." + str(int(ver["version_number"].rsplit(".", 1)[-1]) + 1)
        content = ver["content"] or ""
        original_text = prop["original_text"] or ""
        proposed_text = prop["proposed_text"] or ""
        if original_text:
            occurrences = content.count(original_text)
            if occurrences != 1:
                raise HTTPException(status_code=409, detail="Proposal target is ambiguous or no longer present; manual re-review required")
            content = content.replace(original_text, proposed_text, 1)
        else:
            anchor = prop["context_after"] or ""
            if not anchor:
                # Legacy manually-created proposals had no anchor; preserve compatibility
                # by appending the proposed fragment rather than pretending a location exists.
                content = content + proposed_text
            elif content.count(anchor) != 1:
                raise HTTPException(status_code=409, detail="Proposal insertion anchor is ambiguous or no longer present")
            else:
                content = content.replace(anchor, proposed_text + anchor, 1)

        await db.execute(
            """INSERT INTO document_versions
               (version_id, document_id, version_number, state, content, change_summary,
                kcaa_approved, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (new_version_id, doc_id, new_version_number, "draft", content,
             f"Applied proposal {proposal_id}: {(prop['rationale'] or '')[:100]}",
             0, now, now, actor, actor),
        )
        await db.execute(
            "UPDATE document_proposals SET status = 'applied', applied_at = ?, applied_version_id = ? WHERE proposal_id = ?",
            (now, new_version_id, proposal_id),
        )
        await log_audit_event("document_proposal", proposal_id, "applied", actor, {"new_version_id": new_version_id}, db=db)
        await db.commit()
        return {"proposal_id": proposal_id, "new_version_id": new_version_id, "status": "applied"}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


# ==================== DOCUMENT ANNOTATIONS ====================

@router.post("/documents/{doc_id}/annotations")
async def create_annotation(doc_id: str, request: Request):
    _check(request, "document:annotate")
    body = await request.json()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT version_id FROM document_versions WHERE document_id = ? ORDER BY created_at DESC LIMIT 1",
            (doc_id,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        version_id = row["version_id"]

        ann_id = _gen_id("ANN")
        now = now_iso()
        actor = _actor(request)
        await db.execute(
            """INSERT INTO document_annotations
               (annotation_id, document_id, version_id, annotation_type, target_ref, selected_text,
                content, author_id, status, created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ann_id, doc_id, version_id, body.get("annotation_type", "comment"),
             body["target_ref"], body.get("selected_text"), body["content"],
             actor, "open", now, now, actor, actor),
        )
        await log_audit_event("document_annotation", ann_id, "created", actor, {"document_id": doc_id}, db=db)
        await db.commit()
        async with db.execute("SELECT * FROM document_annotations WHERE annotation_id = ?", (ann_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else {"annotation_id": ann_id, "status": "open"}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.get("/documents/{doc_id}/annotations")
async def list_annotations(doc_id: str, request: Request, status: Optional[str] = None):
    _check(request, "document:annotate")
    db = await get_db()
    try:
        query = "SELECT * FROM document_annotations WHERE document_id = ?"
        params = [doc_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.patch("/annotations/{annotation_id}")
async def update_annotation(annotation_id: str, request: Request):
    _check(request, "document:annotate")
    body = await request.json()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM document_annotations WHERE annotation_id = ?", (annotation_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Annotation not found")

        actor = _actor(request)
        now = now_iso()
        updates = []
        params = []
        for field in ["status", "content", "resolved_by", "resolved_at"]:
            if field in body:
                updates.append(f"{field} = ?")
                params.append(body[field])
        if "status" in body and body["status"] == "resolved":
            updates.append("resolved_by = ?")
            params.append(actor)
            updates.append("resolved_at = ?")
            params.append(now)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        updates.append("updated_at = ?")
        params.append(now)
        updates.append("updated_by = ?")
        params.append(actor)
        params.append(annotation_id)
        await db.execute(
            f"UPDATE document_annotations SET {', '.join(updates)} WHERE annotation_id = ?", params
        )
        await log_audit_event("document_annotation", annotation_id, "updated", actor, body, db=db)
        await db.commit()
        return {"annotation_id": annotation_id, "status": body.get("status", row["status"])}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


# ==================== PERSONNEL LICENSES ====================

@router.post("/personnel/licenses")
async def create_license(request: Request):
    _check(request, "personnel:manage")
    body = await request.json()
    db = await get_db()
    try:
        raw_person_id = body.get("person_id")
        if not isinstance(raw_person_id, str) or not raw_person_id.strip():
            raise HTTPException(status_code=422, detail="A person identifier is required")
        person_id = await _canonical_person_id(db, raw_person_id.strip())
        lic_id = _gen_id("LIC")
        now = now_iso()
        actor = _actor(request)
        await db.execute(
            """INSERT INTO personnel_licenses
               (license_id, person_id, license_type, license_number, issuing_authority, issued_date,
                expiry_date, status, document_ref, aircraft_type, notes, verified_by, verified_at,
                created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (lic_id, person_id, body["license_type"], body.get("license_number"),
             body.get("issuing_authority"), body.get("issued_date"), body["expiry_date"],
             body.get("status", "valid"), body.get("document_ref"), body.get("aircraft_type"),
             body.get("notes"), body.get("verified_by"), body.get("verified_at", now if body.get("verified_by") else None),
             now, now, actor, actor),
        )
        await log_audit_event(
            "personnel_license", lic_id, "created", actor,
            {"person_id": person_id, "license_type": body["license_type"]}, db=db,
        )
        await db.commit()
        async with db.execute("SELECT * FROM personnel_licenses WHERE license_id = ?", (lic_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else {"license_id": lic_id, "status": "valid"}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.get("/personnel/licenses")
async def list_licenses(request: Request, person_id: Optional[str] = None, status: Optional[str] = None,
                        license_type: Optional[str] = None, expiring_within_days: Optional[int] = None):
    _check(request, "personnel:view")
    db = await get_db()
    try:
        query = "SELECT * FROM personnel_licenses WHERE 1=1"
        params = []
        if person_id:
            person_id = await _canonical_person_id(db, person_id)
            query += " AND person_id = ?"
            params.append(person_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if license_type:
            query += " AND license_type = ?"
            params.append(license_type)
        if expiring_within_days is not None:
            cutoff = (datetime.now() + timedelta(days=expiring_within_days)).isoformat()
            query += " AND expiry_date <= ?"
            params.append(cutoff)
        query += " ORDER BY expiry_date ASC"
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/personnel/licenses/{license_id}")
async def get_license(license_id: str, request: Request):
    _check(request, "personnel:view")
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM personnel_licenses WHERE license_id = ?", (license_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="License not found")
        return dict(row)
    finally:
        await db.close()


@router.patch("/personnel/licenses/{license_id}")
async def update_license(license_id: str, request: Request):
    _check(request, "personnel:manage")
    body = await request.json()
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM personnel_licenses WHERE license_id = ?", (license_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="License not found")

        actor = _actor(request)
        now = now_iso()
        updates = []
        params = []
        for field in ["license_type", "license_number", "issuing_authority", "issued_date", "expiry_date",
                      "status", "document_ref", "aircraft_type", "notes", "verified_by"]:
            if field in body:
                updates.append(f"{field} = ?")
                params.append(body[field])
        if "verified_by" in body and body["verified_by"]:
            updates.append("verified_at = ?")
            params.append(now)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        updates.append("updated_at = ?")
        params.append(now)
        updates.append("updated_by = ?")
        params.append(actor)
        params.append(license_id)
        await db.execute(f"UPDATE personnel_licenses SET {', '.join(updates)} WHERE license_id = ?", params)

        # Record renewal if expiry changed
        if "expiry_date" in body and body["expiry_date"] != row["expiry_date"]:
            renewal_id = _gen_id("REN")
            await db.execute(
                """INSERT INTO license_renewal_history (renewal_id, license_id, previous_expiry, new_expiry, renewal_date, evidence_ref, renewed_by, notes, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (renewal_id, license_id, row["expiry_date"], body["expiry_date"], now, body.get("document_ref"), actor, body.get("notes"), now),
            )

        await log_audit_event("personnel_license", license_id, "updated", actor, body, db=db)
        await db.commit()
        async with db.execute("SELECT * FROM personnel_licenses WHERE license_id = ?", (license_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else {"license_id": license_id}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.delete("/personnel/licenses/{license_id}")
async def delete_license(license_id: str, request: Request):
    _check(request, "personnel:manage")
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM personnel_licenses WHERE license_id = ?", (license_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="License not found")
        await db.execute("DELETE FROM personnel_licenses WHERE license_id = ?", (license_id,))
        await log_audit_event("personnel_license", license_id, "deleted", _actor(request), {}, db=db)
        await db.commit()
        return {"deleted": True}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.get("/personnel/expiring-licenses")
async def expiring_licenses(request: Request, days: int = 30):
    """Get licenses expiring within the specified number of days."""
    _check(request, "personnel:view")
    db = await get_db()
    try:
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()
        async with db.execute(
            """SELECT pl.*, u.full_name as person_name
               FROM personnel_licenses pl
               LEFT JOIN users u ON pl.person_id = u.user_id
               WHERE pl.expiry_date <= ? AND pl.status IN ('valid', 'expiring_soon')
               ORDER BY pl.expiry_date ASC""",
            (cutoff,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ==================== AIRCRAFT INSURANCE ====================

@router.post("/aircraft/{aircraft_id}/insurance")
async def create_insurance(aircraft_id: str, request: Request):
    _check(request, "aircraft:manage")
    body = await request.json()
    db = await get_db()
    try:
        async with db.execute("SELECT aircraft_id FROM aircraft WHERE aircraft_id = ?", (aircraft_id,)) as cur:
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Aircraft not found")

        ins_id = _gen_id("INS")
        now = now_iso()
        actor = _actor(request)
        await db.execute(
            """INSERT INTO aircraft_insurance
               (insurance_id, aircraft_id, insurance_type, policy_number, insurer, broker,
                coverage_amount, currency, premium_amount, premium_currency, start_date, expiry_date,
                status, document_ref, renewal_status, renewal_notes, verified_by, verified_at,
                created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ins_id, aircraft_id, body["insurance_type"], body.get("policy_number"),
             body["insurer"], body.get("broker"), body.get("coverage_amount"),
             body.get("currency", "USD"), body.get("premium_amount"), body.get("premium_currency", "USD"),
             body.get("start_date"), body["expiry_date"], body.get("status", "active"),
             body.get("document_ref"), body.get("renewal_status", "not_started"),
             body.get("renewal_notes"), body.get("verified_by"),
             now if body.get("verified_by") else None, now, now, actor, actor),
        )
        await log_audit_event(
            "aircraft_insurance", ins_id, "created", actor,
            {"aircraft_id": aircraft_id, "insurance_type": body["insurance_type"]}, db=db,
        )
        await db.commit()
        async with db.execute("SELECT * FROM aircraft_insurance WHERE insurance_id = ?", (ins_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else {"insurance_id": ins_id, "status": "active"}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.get("/aircraft/{aircraft_id}/insurance")
async def list_aircraft_insurance(aircraft_id: str, request: Request):
    _check(request, "aircraft:read")
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM aircraft_insurance WHERE aircraft_id = ? ORDER BY expiry_date ASC",
            (aircraft_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.patch("/insurance/{insurance_id}")
async def update_insurance(insurance_id: str, request: Request):
    _check(request, "aircraft:manage")
    body = await request.json()
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM aircraft_insurance WHERE insurance_id = ?", (insurance_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Insurance policy not found")

        actor = _actor(request)
        now = now_iso()
        updates = []
        params = []
        for field in ["insurance_type", "policy_number", "insurer", "broker", "coverage_amount",
                      "currency", "premium_amount", "premium_currency", "start_date", "expiry_date",
                      "status", "document_ref", "renewal_status", "renewal_notes", "verified_by"]:
            if field in body:
                updates.append(f"{field} = ?")
                params.append(body[field])
        if "verified_by" in body and body["verified_by"]:
            updates.append("verified_at = ?")
            params.append(now)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        updates.append("updated_at = ?")
        params.append(now)
        updates.append("updated_by = ?")
        params.append(actor)
        params.append(insurance_id)
        await db.execute(f"UPDATE aircraft_insurance SET {', '.join(updates)} WHERE insurance_id = ?", params)

        if "expiry_date" in body and body["expiry_date"] != row["expiry_date"]:
            renewal_id = _gen_id("REN")
            await db.execute(
                """INSERT INTO insurance_renewal_history (renewal_id, insurance_id, previous_expiry, new_expiry, renewal_date, evidence_ref, renewed_by, notes, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (renewal_id, insurance_id, row["expiry_date"], body["expiry_date"], now, body.get("document_ref"), actor, body.get("renewal_notes"), now),
            )

        await log_audit_event("aircraft_insurance", insurance_id, "updated", actor, body, db=db)
        await db.commit()
        return {"insurance_id": insurance_id, "status": body.get("status", row["status"])}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.get("/insurance/expiring")
async def expiring_insurance(request: Request, days: int = 30):
    """Get insurance policies expiring within the specified number of days."""
    _check(request, "aircraft:read")
    db = await get_db()
    try:
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()
        async with db.execute(
            """SELECT ai.*, a.registration, a.model
               FROM aircraft_insurance ai
               LEFT JOIN aircraft a ON ai.aircraft_id = a.aircraft_id
               WHERE ai.expiry_date <= ? AND ai.status IN ('active', 'expiring_soon')
               ORDER BY ai.expiry_date ASC""",
            (cutoff,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ==================== AIRCRAFT DOCUMENTS ====================

@router.post("/aircraft/{aircraft_id}/documents")
async def create_aircraft_document(aircraft_id: str, request: Request):
    _check(request, "aircraft:manage")
    body = await request.json()
    db = await get_db()
    try:
        async with db.execute("SELECT aircraft_id FROM aircraft WHERE aircraft_id = ?", (aircraft_id,)) as cur:
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Aircraft not found")

        doc_id = _gen_id("ADOC")
        now = now_iso()
        actor = _actor(request)
        await db.execute(
            """INSERT INTO aircraft_documents
               (doc_id, aircraft_id, document_type, document_number, issuing_authority, issue_date,
                expiry_date, status, document_ref, notes, verified_by, verified_at,
                created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (doc_id, aircraft_id, body["document_type"], body.get("document_number"),
             body.get("issuing_authority"), body.get("issue_date"), body.get("expiry_date"),
             body.get("status", "valid"), body.get("document_ref"), body.get("notes"),
             body.get("verified_by"), now if body.get("verified_by") else None,
             now, now, actor, actor),
        )
        await log_audit_event(
            "aircraft_document", doc_id, "created", actor,
            {"aircraft_id": aircraft_id, "document_type": body["document_type"]}, db=db,
        )
        await db.commit()
        async with db.execute("SELECT * FROM aircraft_documents WHERE doc_id = ?", (doc_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else {"doc_id": doc_id, "status": "valid"}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.get("/aircraft/{aircraft_id}/documents")
async def list_aircraft_documents(aircraft_id: str, request: Request, document_type: Optional[str] = None):
    _check(request, "aircraft:read")
    db = await get_db()
    try:
        query = "SELECT * FROM aircraft_documents WHERE aircraft_id = ?"
        params = [aircraft_id]
        if document_type:
            query += " AND document_type = ?"
            params.append(document_type)
        query += " ORDER BY expiry_date ASC"
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.patch("/aircraft-documents/{doc_id}")
async def update_aircraft_document(doc_id: str, request: Request):
    _check(request, "aircraft:manage")
    body = await request.json()
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM aircraft_documents WHERE doc_id = ?", (doc_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Aircraft document not found")

        actor = _actor(request)
        now = now_iso()
        updates = []
        params = []
        for field in ["document_type", "document_number", "issuing_authority", "issue_date",
                      "expiry_date", "status", "document_ref", "notes", "verified_by"]:
            if field in body:
                updates.append(f"{field} = ?")
                params.append(body[field])
        if "verified_by" in body and body["verified_by"]:
            updates.append("verified_at = ?")
            params.append(now)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        updates.append("updated_at = ?")
        params.append(now)
        updates.append("updated_by = ?")
        params.append(actor)
        params.append(doc_id)
        await db.execute(f"UPDATE aircraft_documents SET {', '.join(updates)} WHERE doc_id = ?", params)
        await log_audit_event("aircraft_document", doc_id, "updated", actor, body, db=db)
        await db.commit()
        return {"doc_id": doc_id, "status": body.get("status", row["status"])}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


@router.get("/aircraft-documents/expiring")
async def expiring_aircraft_documents(request: Request, days: int = 30):
    """Get aircraft documents expiring within the specified number of days."""
    _check(request, "aircraft:read")
    db = await get_db()
    try:
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()
        async with db.execute(
            """SELECT ad.*, a.registration, a.model
               FROM aircraft_documents ad
               LEFT JOIN aircraft a ON ad.aircraft_id = a.aircraft_id
               WHERE ad.expiry_date <= ? AND ad.status IN ('valid', 'expiring_soon')
               ORDER BY ad.expiry_date ASC""",
            (cutoff,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(annotation_id: str, request: Request):
    _check(request, "document:update")
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM document_annotations WHERE annotation_id = ?", (annotation_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Annotation not found")
        await db.execute("DELETE FROM document_annotations WHERE annotation_id = ?", (annotation_id,))
        await log_audit_event("document_annotation", annotation_id, "deleted", _actor(request), {}, db=db)
        await db.commit()
        return {"deleted": True}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()


# ==================== PERSONNEL SELF-SERVICE UPLOADS ====================

MAX_PERSONNEL_UPLOAD_BYTES = 10 * 1024 * 1024
_UPLOAD_TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}
_UPLOAD_IMAGE_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}
MAX_PERSONNEL_IMAGE_PIXELS = 40_000_000


def _safe_upload_name(filename: str | None) -> tuple[str, str]:
    """Return a basename-only display name and validated extension."""
    normalized = (filename or "").replace("\\", "/")
    display_name = normalized.rsplit("/", 1)[-1].strip()
    if not display_name or display_name in (".", ".."):
        raise HTTPException(status_code=422, detail="A valid file name is required")
    if any(ord(char) < 32 or ord(char) == 127 for char in display_name):
        raise HTTPException(status_code=422, detail="Invalid file name")
    display_name = display_name[:128]
    extension = Path(display_name).suffix.lower()
    if extension not in _UPLOAD_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF, PNG, and JPEG files are accepted")
    return display_name, extension


def _contained_upload_path(root: Path, filename: str) -> Path:
    root_resolved = root.resolve()
    target = (root_resolved / filename).resolve()
    if not target.is_relative_to(root_resolved):
        raise HTTPException(status_code=400, detail="Invalid upload storage path")
    return target


def _validate_personnel_upload_content(content: bytes, extension: str) -> None:
    """Require format-aware parsing in addition to MIME and signature checks."""
    file_type = _UPLOAD_TYPES.get(extension)
    if file_type is None or not content.startswith(file_type[1]):
        raise ValueError("File signature does not match its declared type")
    try:
        if extension == ".pdf":
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted or len(reader.pages) < 1:
                raise ValueError("PDF is encrypted or contains no pages")
            return

        expected_format = _UPLOAD_IMAGE_FORMATS[extension]
        with Image.open(BytesIO(content)) as image:
            if image.format != expected_format:
                raise ValueError("Image format does not match its extension")
            if image.width < 1 or image.height < 1 or image.width * image.height > MAX_PERSONNEL_IMAGE_PIXELS:
                raise ValueError("Image dimensions exceed the allowed limit")
            image.verify()
        with Image.open(BytesIO(content)) as decoded_image:
            if decoded_image.format != expected_format:
                raise ValueError("Image format does not match its extension")
            decoded_image.load()
    except Exception as exc:
        raise ValueError("File is not a structurally valid supported credential") from exc


def _open_personnel_upload_directory(path: Path) -> int:
    """Open each storage directory component without following symlinks."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    if not absolute.is_absolute():
        raise OSError("Personnel upload storage path must be absolute")
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise OSError("Secure no-follow upload storage access is unavailable on this platform")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(os.path.sep, flags)
    try:
        for component in absolute.parts[1:]:
            if component in ("", ".", ".."):
                raise OSError("Personnel upload storage path has an invalid component")
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


class PersonnelUploadVerification(BaseModel):
    verification_status: Literal["verified", "rejected"]
    rejection_reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


def _personnel_upload_response(row) -> dict:
    data = dict(row)
    data.pop("file_path", None)
    data["download_url"] = f"/api/p2/personnel/uploads/{quote(data['upload_id'], safe='')}/file"
    return data


def _has_recorded_review_identities(upload: dict) -> bool:
    return all(
        isinstance(upload.get(field), str) and bool(upload[field].strip())
        for field in ("created_by", "person_id")
    )


def _resolve_personnel_upload_file(row: dict) -> bytes:
    root = Path(UPLOAD_DIR).resolve()
    upload_id = str(row.get("upload_id") or "")
    filename = str(row.get("file_name") or "")
    extension = Path(filename).suffix.lower()
    file_type = _UPLOAD_TYPES.get(extension)
    if not upload_id or not filename or file_type is None:
        raise HTTPException(status_code=409, detail="Stored upload metadata is invalid")
    expected_type, _ = file_type
    if row.get("content_type") != expected_type:
        raise HTTPException(status_code=409, detail="Stored upload content type is invalid")
    if not row.get("file_sha256"):
        raise HTTPException(status_code=409, detail="Stored upload checksum is missing; file requires controlled revalidation")

    candidate = Path(str(row.get("file_path") or ""))
    expected_filename = f"{upload_id}{extension}"
    expected_path = root / expected_filename
    if candidate != expected_path:
        raise HTTPException(status_code=409, detail="Stored upload filename does not match its record")

    hasher = hashlib.sha256()
    directory_descriptor = None
    descriptor = None
    content = bytearray()
    try:
        directory_descriptor = _open_personnel_upload_directory(root)
        directory_stat = os.fstat(directory_descriptor)
        if not stat.S_ISDIR(directory_stat.st_mode) or stat.S_IMODE(directory_stat.st_mode) & 0o077:
            raise OSError("Personnel upload directory is not private")
        descriptor = os.open(
            expected_filename,
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=directory_descriptor,
        )
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size < 0 or file_stat.st_size > MAX_PERSONNEL_UPLOAD_BYTES:
            raise OSError("Personnel upload is not a regular file within the size limit")
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_PERSONNEL_UPLOAD_BYTES:
                raise OSError("Personnel upload exceeds the size limit")
            hasher.update(chunk)
    except OSError as exc:
        raise HTTPException(status_code=409, detail="Stored upload file is missing or invalid") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory_descriptor is not None:
            os.close(directory_descriptor)

    snapshot = bytes(content)
    if row.get("file_size") is not None and len(snapshot) != row["file_size"]:
        raise HTTPException(status_code=409, detail="Stored upload size does not match its record")
    if hasher.hexdigest() != row["file_sha256"]:
        raise HTTPException(status_code=409, detail="Stored upload checksum does not match its record")
    try:
        _validate_personnel_upload_content(snapshot, extension)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Stored upload is not a structurally valid credential file") from exc
    return snapshot


async def _active_person(db, person_id: str) -> bool:
    async with db.execute(
        "SELECT user_id FROM users WHERE user_id = ? AND is_active = 1", (person_id,)
    ) as cur:
        return await cur.fetchone() is not None


async def _canonical_person_id(db, person_id: str) -> str:
    async with db.execute(
        "SELECT canonical_user_id FROM user_id_aliases WHERE legacy_user_id = ?",
        (person_id,),
    ) as cur:
        alias = await cur.fetchone()
    return alias["canonical_user_id"] if alias else person_id


@router.post("/personnel/uploads/file")
async def create_personnel_upload_file(request: Request):
    """Upload a credential for the authenticated person, or for staff-managed personnel."""
    _check(request, "personnel:view")
    actor = _actor(request)
    if not actor:
        raise HTTPException(status_code=401, detail="Authenticated principal required")

    body_limit = MAX_PERSONNEL_UPLOAD_BYTES + 64 * 1024
    raw_length = request.headers.get("content-length")
    if raw_length:
        try:
            if int(raw_length) > body_limit:
                raise HTTPException(status_code=413, detail="Upload request exceeds the allowed size")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid content length") from exc

    original_receive = request._receive
    received_bytes = 0

    async def limited_receive():
        nonlocal received_bytes
        message = await original_receive()
        if message.get("type") == "http.request":
            received_bytes += len(message.get("body", b""))
            if received_bytes > body_limit:
                raise HTTPException(status_code=413, detail="Upload request exceeds the allowed size")
        return message

    request._receive = limited_receive
    try:
        form = await request.form(max_files=1, max_fields=3, max_part_size=16 * 1024)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid multipart upload") from exc

    file = form.get("file")
    if not isinstance(file, UploadFile):
        await form.close()
        raise HTTPException(status_code=422, detail="A credential file is required")

    try:
        raw_person_id = form.get("person_id")
        if raw_person_id is not None and not isinstance(raw_person_id, str):
            raise HTTPException(status_code=422, detail="Invalid person identifier")
        raw_license_type = form.get("license_type", "pilot_license")
        raw_document_type = form.get("document_type", "license_copy")
        if not isinstance(raw_license_type, str) or not isinstance(raw_document_type, str):
            raise HTTPException(status_code=422, detail="Invalid credential metadata")
        license_type = raw_license_type.strip()
        document_type = raw_document_type.strip()
        if not license_type or len(license_type) > 80 or not document_type or len(document_type) > 80:
            raise HTTPException(status_code=422, detail="Invalid credential metadata")
        if license_type not in PERSONNEL_UPLOAD_LICENSE_TYPES or document_type not in PERSONNEL_UPLOAD_DOCUMENT_TYPES:
            raise HTTPException(status_code=422, detail="Unsupported credential type or document type")

        requested_person = (raw_person_id or actor).strip()
        if not requested_person or requested_person.startswith(("/", "\\")) or "\\" in requested_person or ".." in requested_person:
            raise HTTPException(status_code=422, detail="Invalid person identifier")

        display_name, extension = _safe_upload_name(file.filename)
        expected_content_type, _ = _UPLOAD_TYPES[extension]
        if file.content_type != expected_content_type:
            raise HTTPException(status_code=415, detail="File type does not match the supported credential format")

        db = await get_db()
        saved_path: Optional[Path] = None
        row_committed = False
        try:
            requested_person = await _canonical_person_id(db, requested_person)
            if requested_person != actor and not has_permission(_role(request), "personnel:manage"):
                raise HTTPException(status_code=403, detail="Cannot upload for another person")
            person_is_active = await _active_person(db, requested_person)
            if requested_person == actor and not person_is_active:
                raise HTTPException(status_code=403, detail="No verified personnel mapping for this principal")
            if not person_is_active:
                raise HTTPException(status_code=422, detail="Personnel record is not available")
            # personnel_uploads.person_id references users.user_id directly. This is
            # the only verified session-to-person mapping in the current schema.

            upload_id = _gen_id("UPL")
            root = UPLOAD_DIR.resolve()
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(root, 0o700)
            saved_path = _contained_upload_path(root, f"{upload_id}{extension}")
            file_size = 0
            file_content = bytearray()
            file_hasher = hashlib.sha256()
            try:
                descriptor = os.open(saved_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as target:
                    while True:
                        chunk = await file.read(64 * 1024)
                        if not chunk:
                            break
                        file_size += len(chunk)
                        if file_size > MAX_PERSONNEL_UPLOAD_BYTES:
                            raise HTTPException(status_code=413, detail="Upload exceeds the 10 MiB limit")
                        file_content.extend(chunk)
                        file_hasher.update(chunk)
                        target.write(chunk)
                    target.flush()
                    os.fsync(target.fileno())
                try:
                    _validate_personnel_upload_content(bytes(file_content), extension)
                except ValueError as exc:
                    raise HTTPException(status_code=415, detail="File content is not a structurally valid supported credential") from exc
            except Exception:
                if saved_path.exists():
                    saved_path.unlink()
                raise

            now = now_iso()
            await db.execute(
                """INSERT INTO personnel_uploads
                   (upload_id, person_id, license_type, document_type, file_name,
                    file_path, file_size, file_sha256, content_type, verification_status,
                    created_at, updated_at, created_by, updated_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    upload_id, requested_person, license_type, document_type,
                    display_name, str(saved_path), file_size, file_hasher.hexdigest(),
                    expected_content_type, "pending", now, now, actor, actor,
                ),
            )
            await log_audit_event("personnel_upload", upload_id, "uploaded", actor, {
                "person_id": requested_person,
                "license_type": license_type,
                "file_name": display_name,
                "file_size": file_size,
                "file_sha256": file_hasher.hexdigest(),
            }, db=db)
            await db.commit()
            row_committed = True
            async with db.execute("SELECT * FROM personnel_uploads WHERE upload_id = ?", (upload_id,)) as cur:
                row = await cur.fetchone()
            return _personnel_upload_response(row) if row else {"upload_id": upload_id}
        except Exception:
            if not row_committed:
                await _rollback_safely(db)
            if not row_committed and saved_path and saved_path.exists():
                saved_path.unlink()
            raise
        finally:
            await db.close()
    finally:
        await file.close()
        await form.close()



@router.post("/personnel/uploads")
async def create_personnel_upload(request: Request):
    """Reject metadata-only uploads: files must be stored by the bounded upload route."""
    _check(request, "personnel:view")
    raise HTTPException(status_code=415, detail="Upload a file using multipart form data")


@router.get("/personnel/uploads")
async def list_personnel_upload_queue(
    request: Request,
    status: Optional[str] = "pending",
    limit: int = 50,
    offset: int = 0,
):
    """List uploads for the authorized personnel verification queue."""
    role = _role(request)
    if not (has_permission(role, "personnel:read") or has_permission(role, "personnel:manage")):
        raise HTTPException(status_code=403, detail="Permission denied: personnel:read")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    if offset < 0 or offset > 1_000_000:
        raise HTTPException(status_code=422, detail="offset must be between 0 and 1000000")
    if status is not None and status not in {"pending", "verified", "rejected"}:
        raise HTTPException(status_code=422, detail="Unknown personnel upload status")

    db = await get_db()
    try:
        if status is None:
            query = "SELECT * FROM personnel_uploads ORDER BY created_at DESC, upload_id ASC LIMIT ? OFFSET ?"
            params = (limit, offset)
        else:
            query = "SELECT * FROM personnel_uploads WHERE verification_status = ? ORDER BY created_at DESC, upload_id ASC LIMIT ? OFFSET ?"
            params = (status, limit, offset)
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
        uploads = []
        for row in rows:
            upload = _personnel_upload_response(row)
            upload["can_review"] = (
                upload.get("verification_status") == "pending"
                and has_permission(role, "personnel:manage")
                and _has_recorded_review_identities(upload)
                and not same_principal(request, upload.get("created_by"))
                and not same_principal(request, upload.get("person_id"))
            )
            uploads.append(upload)
        return uploads
    finally:
        await db.close()


@router.get("/personnel/uploads/{upload_id}/file")
async def download_personnel_upload(upload_id: str, request: Request):
    role = _role(request)
    if not any(has_permission(role, permission) for permission in ("personnel:view", "personnel:read", "personnel:manage")):
        raise HTTPException(status_code=403, detail="Permission denied: personnel:view")
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM personnel_uploads WHERE upload_id = ?", (upload_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Upload not found")
        upload = dict(row)
        is_self = same_principal(request, upload.get("person_id"))
        if is_self:
            _check(request, "personnel:view")
            if not await _active_person(db, _actor(request)):
                raise HTTPException(status_code=403, detail="No verified personnel mapping for this principal")
        elif not (has_permission(role, "personnel:read") or has_permission(role, "personnel:manage")):
            raise HTTPException(status_code=403, detail="Permission denied: personnel:read")
        content = _resolve_personnel_upload_file(upload)
        return Response(
            content=content,
            media_type=upload["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(upload['file_name'], safe='')}",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        await db.close()


@router.get("/personnel/uploads/{person_id:path}")
async def list_personnel_uploads(
    person_id: str,
    request: Request,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List the authenticated person's uploads, or staff-visible personnel uploads."""
    actor = _actor(request)
    is_self = bool(actor and same_principal(request, person_id))
    if is_self:
        _check(request, "personnel:view")
    elif not (has_permission(_role(request), "personnel:read") or has_permission(_role(request), "personnel:manage")):
        raise HTTPException(status_code=403, detail="Permission denied: personnel:read")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    if offset < 0 or offset > 1_000_000:
        raise HTTPException(status_code=422, detail="offset must be between 0 and 1000000")
    if status is not None and status not in {"pending", "verified", "rejected"}:
        raise HTTPException(status_code=422, detail="Unknown personnel upload status")

    db = await get_db()
    try:
        canonical_person_id = await _canonical_person_id(db, person_id)
        if is_self and not await _active_person(db, actor):
            raise HTTPException(status_code=403, detail="No verified personnel mapping for this principal")
        person_ids = {person_id, canonical_person_id}
        if is_self:
            aliases = getattr(request.state, "actor_aliases", ())
            if isinstance(aliases, (set, tuple, list)):
                person_ids.update(str(alias) for alias in aliases if alias)
            if actor:
                person_ids.add(actor)
        sorted_person_ids = sorted(person_ids)
        placeholders = ",".join("?" for _ in sorted_person_ids)
        query = f"SELECT * FROM personnel_uploads WHERE person_id IN ({placeholders})"
        params: list[object] = list(sorted_person_ids)
        if status is not None:
            query += " AND verification_status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC, upload_id ASC LIMIT ? OFFSET ?"
        params.extend((limit, offset))
        async with db.execute(query, tuple(params)) as cur:
            rows = await cur.fetchall()
        return [_personnel_upload_response(row) for row in rows]
    finally:
        await db.close()


@router.patch("/personnel/uploads/{upload_id}/verify")
async def verify_personnel_upload(upload_id: str, body: PersonnelUploadVerification, request: Request):
    """Verify or reject a crew upload with an independent, auditable review."""
    _check(request, "personnel:manage")
    actor = _actor(request)
    status = body.verification_status
    rejection_reason = (body.rejection_reason or "").strip()
    if status == "rejected" and not rejection_reason:
        raise HTTPException(status_code=422, detail="A rejection reason is required")
    if len(rejection_reason) > 1000:
        raise HTTPException(status_code=422, detail="Rejection reason must be 1000 characters or fewer")

    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM personnel_uploads WHERE upload_id = ?", (upload_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Upload not found")
        upload = dict(row)
        if upload.get("verification_status") != "pending":
            raise HTTPException(status_code=409, detail="Only pending uploads can be reviewed")
        if not _has_recorded_review_identities(upload):
            raise HTTPException(status_code=409, detail="Upload lacks a recorded uploader or credential subject identity; review is blocked")
        if same_principal(request, upload.get("created_by")) or same_principal(request, upload.get("person_id")):
            raise HTTPException(status_code=403, detail="The uploader or credential subject cannot verify or reject their own upload")
        _resolve_personnel_upload_file(upload)

        now = now_iso()
        verified_by = actor if status == "verified" else None
        verified_at = now if status == "verified" else None
        rejection_note = rejection_reason if status == "rejected" else None
        cursor = await db.execute(
            """UPDATE personnel_uploads
               SET verification_status = ?, verified_by = ?, verified_at = ?, rejection_reason = ?,
                   updated_at = ?, updated_by = ?
               WHERE upload_id = ? AND verification_status = 'pending'""",
            (status, verified_by, verified_at, rejection_note, now, actor, upload_id),
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="Upload review state changed; reload and retry")
        await log_audit_event("personnel_upload", upload_id, status, actor, {
            "rejection_reason": rejection_reason or None,
            "file_sha256": upload.get("file_sha256"),
        }, db=db)
        await db.commit()
        async with db.execute("SELECT * FROM personnel_uploads WHERE upload_id = ?", (upload_id,)) as cur:
            result = await cur.fetchone()
        return _personnel_upload_response(result) if result else {"upload_id": upload_id}
    except Exception:
        if db.in_transaction:
            await _rollback_safely(db)
        raise
    finally:
        await db.close()
