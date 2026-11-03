"""P2 API routes - Document Proposals/Annotations, Personnel Licenses, Aircraft Insurance."""
from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import json
import os
from pathlib import Path
import hashlib

from .database import get_db
from .audit import log_audit_event
from .rbac import has_permission, check_sod
from .p0_auth import same_principal
from .proposal_engine import detect_proposals

router = APIRouter()

# Upload storage directory
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
        lic_id = _gen_id("LIC")
        now = now_iso()
        actor = _actor(request)
        await db.execute(
            """INSERT INTO personnel_licenses
               (license_id, person_id, license_type, license_number, issuing_authority, issued_date,
                expiry_date, status, document_ref, aircraft_type, notes, verified_by, verified_at,
                created_at, updated_at, created_by, updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (lic_id, body["person_id"], body["license_type"], body.get("license_number"),
             body.get("issuing_authority"), body.get("issued_date"), body["expiry_date"],
             body.get("status", "valid"), body.get("document_ref"), body.get("aircraft_type"),
             body.get("notes"), body.get("verified_by"), body.get("verified_at", now if body.get("verified_by") else None),
             now, now, actor, actor),
        )
        await log_audit_event(
            "personnel_license", lic_id, "created", actor,
            {"person_id": body["person_id"], "license_type": body["license_type"]}, db=db,
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


async def _active_person(db, person_id: str) -> bool:
    async with db.execute(
        "SELECT user_id FROM users WHERE user_id = ? AND is_active = 1", (person_id,)
    ) as cur:
        return await cur.fetchone() is not None


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

        requested_person = (raw_person_id or actor).strip()
        if not requested_person or requested_person.startswith(("/", "\\")) or "/" in requested_person or "\\" in requested_person or ".." in requested_person:
            raise HTTPException(status_code=422, detail="Invalid person identifier")
        if requested_person != actor and not has_permission(_role(request), "personnel:manage"):
            raise HTTPException(status_code=403, detail="Cannot upload for another person")

        display_name, extension = _safe_upload_name(file.filename)
        expected_content_type, signature = _UPLOAD_TYPES[extension]
        if file.content_type != expected_content_type:
            raise HTTPException(status_code=415, detail="File type does not match the supported credential format")

        db = await get_db()
        saved_path: Optional[Path] = None
        row_committed = False
        try:
            person_is_active = await _active_person(db, requested_person)
            if requested_person == actor and not person_is_active:
                raise HTTPException(status_code=403, detail="No verified personnel mapping for this principal")
            if not person_is_active:
                raise HTTPException(status_code=422, detail="Personnel record is not available")
            # personnel_uploads.person_id references users.user_id directly. This is
            # the only verified session-to-person mapping in the current schema.

            upload_id = _gen_id("UPL")
            root = UPLOAD_DIR.resolve()
            root.mkdir(parents=True, exist_ok=True)
            saved_path = _contained_upload_path(root, f"{upload_id}{extension}")
            file_size = 0
            signature_bytes = bytearray()
            try:
                with saved_path.open("xb") as target:
                    while True:
                        chunk = await file.read(64 * 1024)
                        if not chunk:
                            break
                        file_size += len(chunk)
                        if file_size > MAX_PERSONNEL_UPLOAD_BYTES:
                            raise HTTPException(status_code=413, detail="Upload exceeds the 10 MiB limit")
                        if len(signature_bytes) < len(signature):
                            signature_bytes.extend(chunk[: len(signature) - len(signature_bytes)])
                        target.write(chunk)
                if not bytes(signature_bytes).startswith(signature):
                    raise HTTPException(status_code=415, detail="File content does not match the declared file type")
            except Exception:
                if saved_path.exists():
                    saved_path.unlink()
                raise

            now = now_iso()
            await db.execute(
                """INSERT INTO personnel_uploads
                   (upload_id, person_id, license_type, document_type, file_name,
                    file_path, file_size, content_type, verification_status,
                    created_at, updated_at, created_by, updated_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    upload_id, requested_person, license_type, document_type,
                    display_name, str(saved_path), file_size,
                    expected_content_type, "pending", now, now, actor, actor,
                ),
            )
            await log_audit_event("personnel_upload", upload_id, "uploaded", actor, {
                "person_id": requested_person,
                "license_type": license_type,
                "file_name": display_name,
            }, db=db)
            await db.commit()
            row_committed = True
            async with db.execute("SELECT * FROM personnel_uploads WHERE upload_id = ?", (upload_id,)) as cur:
                row = await cur.fetchone()
            return dict(row) if row else {"upload_id": upload_id}
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


@router.get("/personnel/uploads/{person_id}")
async def list_personnel_uploads(person_id: str, request: Request):
    """List the authenticated person's uploads, or staff-visible personnel uploads."""
    actor = _actor(request)
    is_self = bool(actor and person_id == actor)
    if is_self:
        _check(request, "personnel:view")
    elif not (has_permission(_role(request), "personnel:read") or has_permission(_role(request), "personnel:manage")):
        raise HTTPException(status_code=403, detail="Permission denied: personnel:read")

    db = await get_db()
    try:
        if is_self and not await _active_person(db, actor):
            raise HTTPException(status_code=403, detail="No verified personnel mapping for this principal")
        async with db.execute(
            "SELECT * FROM personnel_uploads WHERE person_id = ? ORDER BY created_at DESC",
            (person_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.patch("/personnel/uploads/{upload_id}/verify")
async def verify_personnel_upload(upload_id: str, request: Request):
    """Verify or reject a crew upload (requires personnel:manage)."""
    _check(request, "personnel:manage")
    body = await request.json()
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM personnel_uploads WHERE upload_id = ?", (upload_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Upload not found")
        actor = _actor(request)
        now = now_iso()
        status = body.get("verification_status", "verified")
        if status not in ("verified", "rejected"):
            raise HTTPException(status_code=400, detail="Invalid verification status")
        updates = ["verification_status = ?", "updated_at = ?", "updated_by = ?"]
        params = [status, now, actor]
        if status == "verified":
            updates.extend(["verified_by = ?", "verified_at = ?"])
            params.extend([actor, now])
        if status == "rejected" and body.get("rejection_reason"):
            updates.append("rejection_reason = ?")
            params.append(body["rejection_reason"])
        params.append(upload_id)
        await db.execute(
            f"UPDATE personnel_uploads SET {', '.join(updates)} WHERE upload_id = ?",
            params,
        )
        await log_audit_event("personnel_upload", upload_id, status, actor, {
            "rejection_reason": body.get("rejection_reason"),
        }, db=db)
        await db.commit()
        async with db.execute("SELECT * FROM personnel_uploads WHERE upload_id = ?", (upload_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else {"upload_id": upload_id}
    except Exception:
        await _rollback_safely(db)
        raise
    finally:
        await db.close()
