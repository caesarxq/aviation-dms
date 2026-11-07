"""P3 API routes for external audit reports and their findings."""

import hashlib
import hmac
import json
import os
import stat
import tempfile
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader

from .database import DB_PATH, get_db
from .rbac import has_permission

router = APIRouter()
AUDIT_REPORT_EVIDENCE_DIR = Path(
    os.getenv("AUDIT_REPORT_EVIDENCE_DIR", str(Path(DB_PATH).parent / "attachments"))
)


def _validated_audit_report_evidence_path(evidence_file: Optional[str]) -> Optional[Path]:
    """Resolve only a named file path inside the audit attachments directory."""
    if not evidence_file or "\\" in evidence_file or "\x00" in evidence_file:
        return None
    parts = evidence_file.split("/")
    if len(parts) != 2 or parts[0] != "attachments" or parts[1] in {"", ".", ".."}:
        return None

    root = AUDIT_REPORT_EVIDENCE_DIR.resolve()
    try:
        path = (root / parts[1]).resolve(strict=True)
        if path.parent != root or not path.is_file():
            return None
    except (OSError, RuntimeError):
        return None
    return path


class InvalidAuditEvidence(Exception):
    """Evidence path resolved but the opened file is not a valid PDF file."""


class AuditEvidenceIntegrityError(Exception):
    """The evidence snapshot does not match the report's recorded digest."""


def _open_directory_without_symlinks(path: Path) -> int:
    """Open every directory component without following symlinks."""
    if not path.is_absolute():
        raise OSError("Evidence directory must be absolute")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(os.path.sep, directory_flags)
    try:
        for component in path.parts[1:]:
            next_descriptor = os.open(component, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _snapshot_audit_evidence(path: Path, expected_sha256: Optional[str] = None):
    """Copy, hash, and optionally verify evidence bytes from one opened file descriptor."""
    snapshot = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    digest = hashlib.sha256()
    directory_descriptor = None
    descriptor = None
    try:
        directory_descriptor = _open_directory_without_symlinks(path.parent)
        descriptor = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        os.close(directory_descriptor)
        directory_descriptor = None
        with os.fdopen(descriptor, "rb") as source:
            descriptor = None
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise InvalidAuditEvidence("Audit evidence is not a regular file")
            header = source.read(5)
            if header != b"%PDF-":
                raise InvalidAuditEvidence("Audit evidence is not a PDF")
            snapshot.write(header)
            digest.update(header)
            while chunk := source.read(1024 * 1024):
                snapshot.write(chunk)
                digest.update(chunk)

        size = snapshot.tell()
        snapshot.seek(0)
        try:
            reader = PdfReader(snapshot, strict=True)
            if not reader.is_encrypted and len(reader.pages) == 0:
                raise InvalidAuditEvidence("Audit evidence PDF has no pages")
        except Exception as exc:
            raise InvalidAuditEvidence("Audit evidence PDF structure is invalid") from exc
        finally:
            snapshot.seek(0)

        actual_sha256 = digest.hexdigest()
        if expected_sha256 and not hmac.compare_digest(actual_sha256, expected_sha256):
            raise AuditEvidenceIntegrityError("Audit evidence digest mismatch")
        snapshot.seek(0)
        return snapshot, actual_sha256, size
    except Exception:
        snapshot.close()
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory_descriptor is not None:
            os.close(directory_descriptor)


def _stream_audit_snapshot(snapshot):
    try:
        while chunk := snapshot.read(1024 * 1024):
            yield chunk
    finally:
        snapshot.close()


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
    evidence_path = None
    evidence_sha256 = None
    if payload.evidence_file is not None:
        evidence_path = _validated_audit_report_evidence_path(payload.evidence_file)
        if evidence_path is None:
            raise HTTPException(status_code=422, detail="evidence_file must reference an existing PDF under attachments/")
        try:
            snapshot, evidence_sha256, _ = _snapshot_audit_evidence(evidence_path)
            snapshot.close()
        except (OSError, InvalidAuditEvidence) as exc:
            raise HTTPException(status_code=422, detail="evidence_file must reference a readable PDF under attachments/") from exc
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
                status, evidence_file, evidence_sha256, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                audit_id, audit_number, audit_date, auditor_id, auditee_id, payload.scope,
                payload.regulatory_basis, payload.status.value, payload.evidence_file, evidence_sha256, now, now,
            ),
        )
        await _write_event(db, "audit_report", audit_id, "created", actor, {
            "audit_number": audit_number,
            "evidence_sha256": evidence_sha256,
        })
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
    return {
        "audit_id": audit_id,
        "audit_number": audit_number,
        "status": payload.status.value,
        "evidence_sha256": evidence_sha256,
        "created_at": now,
    }


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


@router.get("/audit-reports/{audit_id}/evidence")
async def download_audit_report_evidence(audit_id: str, request: Request):
    _check(request, "audit_report:read")
    db = await get_db()
    try:
        report = await (await db.execute(
            "SELECT evidence_file, evidence_sha256 FROM audit_reports WHERE audit_id = ?", (audit_id,)
        )).fetchone()
    finally:
        await db.close()
    if not report:
        raise HTTPException(status_code=404, detail="Audit report not found")

    path = _validated_audit_report_evidence_path(report["evidence_file"])
    if not path:
        raise HTTPException(status_code=404, detail="Audit evidence file not found")
    expected_sha256 = report["evidence_sha256"]
    if not expected_sha256:
        raise HTTPException(status_code=409, detail="Audit evidence integrity metadata is missing; controlled revalidation is required")
    try:
        snapshot, _, size = _snapshot_audit_evidence(path, expected_sha256)
    except AuditEvidenceIntegrityError as exc:
        raise HTTPException(status_code=409, detail="Audit evidence integrity check failed")
    except (OSError, InvalidAuditEvidence) as exc:
        raise HTTPException(status_code=409, detail="Audit evidence integrity check failed") from exc
    ascii_filename = "".join(
        character if character.isascii() and (character.isalnum() or character in "._-") else "_"
        for character in path.name
    ) or "audit-evidence.pdf"
    return StreamingResponse(
        _stream_audit_snapshot(snapshot),
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(size),
            "Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{quote(path.name, safe="")}',
        },
    )


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
