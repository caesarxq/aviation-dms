"""P3 API routes for external audit reports and their findings."""

import asyncio
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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .database import DB_PATH, get_db
from .p0_auth import same_principal
from .p1_models import (
    CorrectiveActionCreate,
    CorrectiveActionUpdate,
    CorrectiveActionResponse,
)
from .rbac import has_permission
from .upload_safety import (
    UploadMalwareDetected,
    UploadSafeguardConfigurationError,
    UploadScannerUnavailable,
    load_upload_safety_policy,
    scan_upload_bytes,
    upload_request_limit,
)
from .upload_validation import (
    UploadContentInvalid,
    UploadValidationUnavailable,
    validate_upload_content,
)

router = APIRouter()
AUDIT_REPORT_EVIDENCE_DIR = Path(
    os.getenv("AUDIT_REPORT_EVIDENCE_DIR", str(Path(DB_PATH).parent / "attachments"))
)

# Each department's findings are closed by that department's head. Unknown
# department names fail closed rather than skipping the closure gate.
DEPARTMENT_HEAD_ROLES = {
    "quality": "head_quality",
    "safety": "head_safety",
    "security": "head_security",
    "operations": "head_operations",
    "maintenance": "head_maintenance",
    "training": "head_training",
}


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


class AuditEvidenceTooLarge(InvalidAuditEvidence):
    """Evidence exceeds the explicitly configured per-file byte limit."""


class AuditEvidenceSafeguardsUnavailable(RuntimeError):
    """Evidence scanning, size policy, or isolated parsing is unavailable."""


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


def _audit_evidence_max_bytes() -> int:
    value = os.getenv("DMS_AUDIT_EVIDENCE_MAX_BYTES", "").strip()
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise AuditEvidenceSafeguardsUnavailable(
            "Audit evidence size limit is not configured"
        ) from exc
    if limit <= 0:
        raise AuditEvidenceSafeguardsUnavailable("Audit evidence size limit is not configured")
    return limit


def _copy_audit_evidence_snapshot(
    path: Path,
    max_bytes: int,
    expected_sha256: Optional[str] = None,
):
    """Copy and hash a bounded evidence snapshot without parsing its contents."""
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
            source_stat = os.fstat(source.fileno())
            if not stat.S_ISREG(source_stat.st_mode):
                raise InvalidAuditEvidence("Audit evidence is not a regular file")
            if source_stat.st_size > max_bytes:
                raise AuditEvidenceTooLarge("Audit evidence exceeds the configured size limit")
            header = source.read(5)
            if header != b"%PDF-":
                raise InvalidAuditEvidence("Audit evidence is not a PDF")
            snapshot.write(header)
            digest.update(header)
            size = len(header)
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise AuditEvidenceTooLarge("Audit evidence exceeds the configured size limit")
                snapshot.write(chunk)
                digest.update(chunk)

        if size != source_stat.st_size:
            raise InvalidAuditEvidence("Audit evidence changed during snapshot")
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


_AUDIT_EVIDENCE_IO_SLOTS = asyncio.Semaphore(2)


async def _run_bounded_evidence_io(function, *args, cleanup_on_cancel=None):
    async with _AUDIT_EVIDENCE_IO_SLOTS:
        worker = asyncio.create_task(asyncio.to_thread(function, *args))
        cancelled = False
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                cancelled = True
            except Exception:
                break
        if cancelled:
            try:
                result = worker.result()
                if cleanup_on_cancel is not None:
                    cleanup_on_cancel(result)
            except BaseException:
                pass
            raise asyncio.CancelledError
        return await worker


async def _snapshot_audit_evidence(path: Path, expected_sha256: Optional[str] = None):
    """Create a bounded, hash-verified, scanned and isolated-parsed evidence snapshot."""
    max_bytes = _audit_evidence_max_bytes()
    snapshot, actual_sha256, size = await _run_bounded_evidence_io(
        _copy_audit_evidence_snapshot,
        path,
        max_bytes,
        expected_sha256,
        cleanup_on_cancel=lambda result: result[0].close(),
    )
    try:
        policy = load_upload_safety_policy()
        payload = await _run_bounded_evidence_io(snapshot.read)
        snapshot.seek(0)
        await scan_upload_bytes(payload, policy)
        await validate_upload_content(payload, ".pdf", max_bytes)
        snapshot.seek(0)
        return snapshot, actual_sha256, size
    except UploadMalwareDetected as exc:
        snapshot.close()
        raise InvalidAuditEvidence("Audit evidence was rejected by malware screening") from exc
    except (
        UploadSafeguardConfigurationError,
        UploadScannerUnavailable,
        UploadValidationUnavailable,
    ) as exc:
        snapshot.close()
        raise AuditEvidenceSafeguardsUnavailable(
            "Audit evidence safeguards are unavailable"
        ) from exc
    except UploadContentInvalid as exc:
        snapshot.close()
        raise InvalidAuditEvidence("Audit evidence PDF structure is invalid") from exc
    except Exception:
        snapshot.close()
        raise


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


class AuditReportImportStatus(str, Enum):
    pending_verification = "pending_verification"
    imported = "imported"
    rejected = "rejected"


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
    audit_type: str = Field(default="internal", max_length=50)
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
    department: str = Field(min_length=1, max_length=50)
    due_date: Optional[date] = None


class AuditReportImportFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_number: str = Field(min_length=1, max_length=50)
    area: str = Field(min_length=1, max_length=200)
    level: int = Field(ge=1, le=4)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=10000)
    regulatory_reference: Optional[str] = Field(default=None, max_length=2000)
    due_date: Optional[date] = None


class AuditReportImportContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_number: str = Field(min_length=1, max_length=100)
    audit_date: date
    source_auditor_id: str = Field(min_length=1, max_length=100)
    source_auditor_name: str = Field(min_length=1, max_length=200)
    auditee_id: str = Field(min_length=1, max_length=100)
    scope: Optional[str] = Field(default=None, max_length=2000)
    regulatory_basis: Optional[str] = Field(default=None, max_length=2000)
    evidence_file: str = Field(min_length=1, max_length=1000)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    findings: list[AuditReportImportFinding] = Field(min_length=1, max_length=500)


class AuditReportImportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_number: str = Field(min_length=1, max_length=100)
    audit_date: date
    source_auditor_id: str = Field(min_length=1, max_length=100)
    source_auditor_name: str = Field(min_length=1, max_length=200)
    auditee_id: str = Field(min_length=1, max_length=100)
    scope: Optional[str] = Field(default=None, max_length=2000)
    regulatory_basis: Optional[str] = Field(default=None, max_length=2000)
    evidence_file: str = Field(min_length=1, max_length=1000)
    expected_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    findings: list[AuditReportImportFinding] = Field(min_length=1, max_length=500)


class AuditReportImportReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_checksum_confirmed: bool
    findings_reconciled: bool
    verification_notes: str = Field(min_length=20, max_length=5000)


class AuditReportImportRejection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=5000)


class AuditFindingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    area: Optional[str] = Field(default=None, min_length=1, max_length=200)
    level: Optional[int] = Field(default=None, ge=1, le=4)
    regulatory_reference: Optional[str] = Field(default=None, max_length=2000)
    department: Optional[str] = Field(default=None, min_length=1, max_length=50)
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


async def _canonical_import_user_id(db, user_id: str) -> str:
    alias = await (await db.execute(
        "SELECT canonical_user_id FROM user_id_aliases WHERE legacy_user_id = ?", (user_id,)
    )).fetchone()
    return alias["canonical_user_id"] if alias else user_id


def _canonical_payload_hash(payload: dict) -> tuple[str, str]:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _audit_report_import_content(payload: AuditReportImportCreate, evidence_sha256: str) -> dict:
    return {
        "audit_number": payload.audit_number,
        "audit_date": _date(payload.audit_date),
        "source_auditor_id": payload.source_auditor_id,
        "source_auditor_name": payload.source_auditor_name,
        "auditee_id": payload.auditee_id,
        "scope": payload.scope,
        "regulatory_basis": payload.regulatory_basis,
        "evidence_file": payload.evidence_file,
        "evidence_sha256": evidence_sha256,
        "findings": [finding.model_dump(mode="json") for finding in payload.findings],
    }


def _serialize_audit_report_import(row, *, include_findings: bool = True) -> dict:
    payload = json.loads(row["payload_json"])
    result = {
        "import_id": row["import_id"],
        "audit_number": row["audit_number"],
        "audit_date": row["audit_date"],
        "source_auditor_id": row["source_auditor_id"],
        "source_auditor_name": row["source_auditor_name"],
        "auditee_id": row["auditee_id"],
        "scope": payload["scope"],
        "regulatory_basis": payload["regulatory_basis"],
        "evidence_sha256": row["evidence_sha256"],
        "payload_sha256": row["payload_sha256"],
        "evidence_download_url": f"/api/p3/audit-report-imports/{quote(row['import_id'], safe='')}/evidence",
        "imported_by": row["imported_by"],
        "created_at": row["created_at"],
        "status": row["status"],
        "verified_by": row["verified_by"],
        "verified_at": row["verified_at"],
        "verification_notes": row["verification_notes"],
        "audit_id": row["audit_id"],
    }
    if include_findings:
        result["findings"] = payload["findings"]
    return result


def _check_audit_report_import_read(request: Request) -> None:
    role = _role(request)
    if role not in {"system_admin", "independent_auditor"} or not (
        has_permission(role, "audit_report:import")
        or has_permission(role, "audit_report:provenance_verify")
    ):
        raise HTTPException(status_code=403, detail="Permission denied: audit report import review")


@router.post(
    "/audit-reports",
    status_code=201,
)
async def create_audit_report(payload: AuditReportCreate, request: Request):
    _check(request, "audit_report:create")
    actor = _actor(request)
    audit_id = _gen_id("AUD")
    now = _now()
    today_utc = datetime.fromisoformat(now).date()
    if payload.audit_date is not None and payload.audit_date < today_utc:
        raise HTTPException(
            status_code=422,
            detail="Backdated audit reports must use the provenance import workflow",
        )
    audit_number = payload.audit_number or f"AUD-{uuid.uuid4().hex[:6].upper()}"
    audit_date = _date(payload.audit_date) or today_utc.isoformat()
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
            snapshot, evidence_sha256, _ = await _snapshot_audit_evidence(evidence_path)
            snapshot.close()
        except AuditEvidenceSafeguardsUnavailable as exc:
            raise HTTPException(status_code=503, detail="Audit evidence safeguards are not configured") from exc
        except AuditEvidenceTooLarge as exc:
            raise HTTPException(status_code=413, detail="Audit evidence exceeds the configured size limit") from exc
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
                audit_type, status, evidence_file, evidence_sha256, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                audit_id, audit_number, audit_date, auditor_id, auditee_id, payload.scope,
                payload.regulatory_basis, payload.audit_type, payload.status.value, payload.evidence_file, evidence_sha256, now, now,
            ),
        )
        await _write_event(db, "audit_report", audit_id, "created", actor, {
            "audit_number": audit_number,
            "audit_type": payload.audit_type,
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
        "audit_type": payload.audit_type,
        "status": payload.status.value,
        "evidence_sha256": evidence_sha256,
        "created_at": now,
    }


@router.get("/audit-reports")
async def list_audit_reports(
    request: Request,
    status: Optional[ReportStatus] = None,
    search: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
):
    _check(request, "audit_report:read")
    search_text = (search or "").strip().lower()
    escaped_search = search_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    search_pattern = f"%{escaped_search}%"
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM audit_reports
               WHERE (? IS NULL OR status = ?)
                 AND (? = '' OR LOWER(audit_number) LIKE ? ESCAPE '\\'
                      OR LOWER(COALESCE(scope, '')) LIKE ? ESCAPE '\\'
                      OR LOWER(COALESCE(regulatory_basis, '')) LIKE ? ESCAPE '\\')
               ORDER BY audit_date DESC, audit_id ASC LIMIT ? OFFSET ?""",
            (
                status.value if status else None,
                status.value if status else None,
                search_text,
                search_pattern,
                search_pattern,
                search_pattern,
                limit,
                offset,
            ),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


@router.get(
    "/audit-reports/{audit_id}/evidence",
    dependencies=[Depends(upload_request_limit)],
)
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
        snapshot, _, size = await _snapshot_audit_evidence(path, expected_sha256)
    except AuditEvidenceIntegrityError as exc:
        raise HTTPException(status_code=409, detail="Audit evidence integrity check failed")
    except AuditEvidenceSafeguardsUnavailable as exc:
        raise HTTPException(status_code=503, detail="Audit evidence safeguards are not configured") from exc
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


@router.post(
    "/audit-report-imports",
    status_code=201,
)
async def create_audit_report_import(payload: AuditReportImportCreate, request: Request):
    _check(request, "audit_report:import")
    if _role(request) != "system_admin":
        raise HTTPException(status_code=403, detail="Only a system administrator may stage a historical audit import")
    actor = _actor(request)
    source_auditor_id = payload.source_auditor_id
    auditee_id = payload.auditee_id
    if payload.audit_number != payload.audit_number.strip():
        raise HTTPException(status_code=422, detail="audit_number must not contain surrounding whitespace")
    finding_numbers = [finding.finding_number for finding in payload.findings]
    if len(finding_numbers) != len(set(finding_numbers)):
        raise HTTPException(status_code=422, detail="Finding numbers must be unique within an imported report")
    if any(value != value.strip() for value in (source_auditor_id, payload.source_auditor_name, auditee_id)):
        raise HTTPException(status_code=422, detail="Source identity fields must not contain surrounding whitespace")
    if not payload.source_auditor_name.strip():
        raise HTTPException(status_code=422, detail="Source auditor name is required")
    if same_principal(request, source_auditor_id) or same_principal(request, auditee_id):
        raise HTTPException(status_code=403, detail="The import operator must be distinct from source participants")

    source_path = _validated_audit_report_evidence_path(payload.evidence_file)
    if source_path is None:
        raise HTTPException(status_code=422, detail="evidence_file must reference an existing PDF under attachments/")
    try:
        snapshot, evidence_sha256, _ = await _snapshot_audit_evidence(
            source_path, payload.expected_evidence_sha256
        )
        snapshot.close()
    except AuditEvidenceIntegrityError as exc:
        raise HTTPException(status_code=409, detail="Audit source PDF digest does not match the supplied checksum") from exc
    except AuditEvidenceSafeguardsUnavailable as exc:
        raise HTTPException(status_code=503, detail="Audit evidence safeguards are not configured") from exc
    except AuditEvidenceTooLarge as exc:
        raise HTTPException(status_code=413, detail="Audit evidence exceeds the configured size limit") from exc
    except (OSError, InvalidAuditEvidence) as exc:
        raise HTTPException(status_code=422, detail="evidence_file must reference a readable PDF under attachments/") from exc

    content = _audit_report_import_content(payload, evidence_sha256)
    payload_json, payload_sha256 = _canonical_payload_hash(content)
    import_id = _gen_id("AIMP")
    now = _now()
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        source_user = await (await db.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (source_auditor_id,)
        )).fetchone()
        auditee = await (await db.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (auditee_id,)
        )).fetchone()
        if not source_user or not auditee:
            raise HTTPException(status_code=422, detail="Source auditor and auditee must reference existing canonical users")
        canonical_source = await _canonical_import_user_id(db, source_auditor_id)
        canonical_auditee = await _canonical_import_user_id(db, auditee_id)
        if canonical_source == canonical_auditee:
            raise HTTPException(status_code=422, detail="Source auditor and auditee must be different people")
        existing_report = await (await db.execute(
            "SELECT 1 FROM audit_reports WHERE audit_number = ?", (payload.audit_number,)
        )).fetchone()
        existing_import = await (await db.execute(
            "SELECT 1 FROM audit_report_imports WHERE audit_number = ? AND status IN ('pending_verification', 'imported')",
            (payload.audit_number,),
        )).fetchone()
        if existing_report or existing_import:
            raise HTTPException(status_code=409, detail="An audit report or active import with this audit number already exists")
        await db.execute(
            """INSERT INTO audit_report_imports
               (import_id, audit_number, audit_date, source_auditor_id, source_auditor_name, auditee_id,
                scope, regulatory_basis, evidence_file, evidence_sha256, payload_json, payload_sha256,
                imported_by, created_at, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pending_verification')""",
            (
                import_id, payload.audit_number, _date(payload.audit_date), source_auditor_id,
                payload.source_auditor_name, auditee_id, payload.scope, payload.regulatory_basis,
                payload.evidence_file, evidence_sha256, payload_json, payload_sha256, actor, now,
            ),
        )
        await _write_event(db, "audit_report_import", import_id, "created", actor, {
            "audit_number": payload.audit_number,
            "source_auditor_id": source_auditor_id,
            "evidence_sha256": evidence_sha256,
            "payload_sha256": payload_sha256,
            "finding_count": len(payload.findings),
        })
        await db.commit()
        row = await (await db.execute(
            "SELECT * FROM audit_report_imports WHERE import_id = ?", (import_id,)
        )).fetchone()
        return _serialize_audit_report_import(row)
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


@router.get("/audit-report-imports")
async def list_audit_report_imports(
    request: Request,
    status: Optional[AuditReportImportStatus] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
):
    _check_audit_report_import_read(request)
    db = await get_db()
    try:
        if status:
            cursor = await db.execute(
                """SELECT * FROM audit_report_imports WHERE status = ?
                   ORDER BY created_at DESC, import_id ASC LIMIT ? OFFSET ?""",
                (status.value, limit, offset),
            )
        else:
            cursor = await db.execute(
                """SELECT * FROM audit_report_imports
                   ORDER BY created_at DESC, import_id ASC LIMIT ? OFFSET ?""",
                (limit, offset),
            )
        return [_serialize_audit_report_import(row, include_findings=False) for row in await cursor.fetchall()]
    finally:
        await db.close()


@router.get("/audit-report-imports/{import_id}")
async def get_audit_report_import(import_id: str, request: Request):
    _check_audit_report_import_read(request)
    db = await get_db()
    try:
        row = await (await db.execute(
            "SELECT * FROM audit_report_imports WHERE import_id = ?", (import_id,)
        )).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Audit report import not found")
        return _serialize_audit_report_import(row)
    finally:
        await db.close()


@router.get(
    "/audit-report-imports/{import_id}/evidence",
    dependencies=[Depends(upload_request_limit)],
)
async def download_audit_report_import_evidence(import_id: str, request: Request):
    _check_audit_report_import_read(request)
    db = await get_db()
    try:
        row = await (await db.execute(
            "SELECT evidence_file, evidence_sha256 FROM audit_report_imports WHERE import_id = ?",
            (import_id,),
        )).fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit report import not found")
    path = _validated_audit_report_evidence_path(row["evidence_file"])
    if path is None:
        raise HTTPException(status_code=409, detail="Audit import source evidence is missing or invalid")
    try:
        snapshot, _, size = await _snapshot_audit_evidence(path, row["evidence_sha256"])
    except AuditEvidenceIntegrityError as exc:
        raise HTTPException(status_code=409, detail="Audit import source evidence integrity check failed") from exc
    except AuditEvidenceSafeguardsUnavailable as exc:
        raise HTTPException(status_code=503, detail="Audit evidence safeguards are not configured") from exc
    except (OSError, InvalidAuditEvidence) as exc:
        raise HTTPException(status_code=409, detail="Audit import source evidence integrity check failed") from exc
    ascii_filename = "".join(
        character if character.isascii() and (character.isalnum() or character in "._-") else "_"
        for character in path.name
    ) or "audit-source.pdf"
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


@router.post(
    "/audit-report-imports/{import_id}/verify",
)
async def verify_audit_report_import(
    import_id: str, payload: AuditReportImportReview, request: Request
):
    _check(request, "audit_report:provenance_verify")
    if _role(request) != "independent_auditor":
        raise HTTPException(status_code=403, detail="Only an independent auditor may verify source provenance")
    if not payload.source_checksum_confirmed or not payload.findings_reconciled:
        raise HTTPException(status_code=422, detail="Source checksum and findings reconciliation must both be confirmed")
    notes = payload.verification_notes.strip()
    if len(notes) < 20:
        raise HTTPException(status_code=422, detail="Verification notes must include the review basis")
    actor = _actor(request)
    db = await get_db()
    snapshot = None
    try:
        row = await (await db.execute(
            "SELECT * FROM audit_report_imports WHERE import_id = ?", (import_id,)
        )).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Audit report import not found")
        candidate = dict(row)
        if candidate["status"] != "pending_verification":
            raise HTTPException(status_code=409, detail="Only pending imports can be provenance-verified")
        if (
            same_principal(request, candidate["imported_by"])
            or same_principal(request, candidate["source_auditor_id"])
            or same_principal(request, candidate["auditee_id"])
        ):
            raise HTTPException(status_code=403, detail="Verifier must be independent of source auditor, auditee, and import operator")
        verifier = await (await db.execute(
            """SELECT u.user_id FROM users u JOIN user_roles ur ON ur.user_id = u.user_id
               WHERE u.user_id = ? AND u.is_active = 1 AND ur.role = 'independent_auditor'""",
            (actor,),
        )).fetchone()
        if verifier is None:
            raise HTTPException(status_code=403, detail="Verifier must be an active independent_auditor account")

        try:
            content = AuditReportImportContent.model_validate_json(candidate["payload_json"])
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Stored audit import payload is invalid") from exc
        canonical_payload = content.model_dump(mode="json")
        payload_json, payload_sha256 = _canonical_payload_hash(canonical_payload)
        if payload_json != candidate["payload_json"] or payload_sha256 != candidate["payload_sha256"]:
            raise HTTPException(status_code=409, detail="Stored audit import payload integrity check failed")
        if (
            content.audit_number != candidate["audit_number"]
            or _date(content.audit_date) != candidate["audit_date"]
            or content.source_auditor_id != candidate["source_auditor_id"]
            or content.source_auditor_name != candidate["source_auditor_name"]
            or content.auditee_id != candidate["auditee_id"]
            or content.scope != candidate["scope"]
            or content.regulatory_basis != candidate["regulatory_basis"]
            or content.evidence_file != candidate["evidence_file"]
            or content.evidence_sha256 != candidate["evidence_sha256"]
        ):
            raise HTTPException(status_code=409, detail="Stored audit import metadata does not match the reviewed payload")
        evidence_path = _validated_audit_report_evidence_path(candidate["evidence_file"])
        if evidence_path is None:
            raise HTTPException(status_code=409, detail="Audit import source evidence is missing or invalid")
        try:
            snapshot, actual_sha256, _ = await _snapshot_audit_evidence(
                evidence_path, candidate["evidence_sha256"]
            )
        except AuditEvidenceIntegrityError as exc:
            raise HTTPException(status_code=409, detail="Audit import source evidence integrity check failed") from exc
        except AuditEvidenceSafeguardsUnavailable as exc:
            raise HTTPException(status_code=503, detail="Audit evidence safeguards are not configured") from exc
        except (OSError, InvalidAuditEvidence) as exc:
            raise HTTPException(status_code=409, detail="Audit import source evidence integrity check failed") from exc
        if actual_sha256 != candidate["evidence_sha256"]:
            raise HTTPException(status_code=409, detail="Audit import source evidence integrity check failed")

        await db.execute("BEGIN IMMEDIATE")
        current_row = await (await db.execute(
            "SELECT * FROM audit_report_imports WHERE import_id = ?", (import_id,)
        )).fetchone()
        if current_row is None:
            raise HTTPException(status_code=409, detail="Audit import changed during provenance validation")
        current_candidate = dict(current_row)
        if current_candidate["status"] != "pending_verification":
            raise HTTPException(status_code=409, detail="Only pending imports can be provenance-verified")
        unchanged_fields = (
            "audit_number", "audit_date", "source_auditor_id", "source_auditor_name", "auditee_id",
            "scope", "regulatory_basis", "evidence_file", "evidence_sha256", "payload_json",
            "payload_sha256", "imported_by",
        )
        if any(current_candidate[field] != candidate[field] for field in unchanged_fields):
            raise HTTPException(status_code=409, detail="Audit import changed during provenance validation")
        if (
            same_principal(request, current_candidate["imported_by"])
            or same_principal(request, current_candidate["source_auditor_id"])
            or same_principal(request, current_candidate["auditee_id"])
        ):
            raise HTTPException(status_code=403, detail="Verifier must be independent of source auditor, auditee, and import operator")
        verifier = await (await db.execute(
            """SELECT u.user_id FROM users u JOIN user_roles ur ON ur.user_id = u.user_id
               WHERE u.user_id = ? AND u.is_active = 1 AND ur.role = 'independent_auditor'""",
            (actor,),
        )).fetchone()
        if verifier is None:
            raise HTTPException(status_code=403, detail="Verifier must be an active independent_auditor account")
        candidate = current_candidate
        now = _now()

        duplicate = await (await db.execute(
            "SELECT 1 FROM audit_reports WHERE audit_number = ?", (candidate["audit_number"],)
        )).fetchone()
        if duplicate:
            raise HTTPException(status_code=409, detail="An audit report with this audit number already exists")

        audit_id = _gen_id("AUD")
        await db.execute(
            """INSERT INTO audit_reports
               (audit_id, audit_number, audit_date, auditor_id, auditee_id, scope, regulatory_basis,
                status, evidence_file, evidence_sha256, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                audit_id, content.audit_number, _date(content.audit_date), content.source_auditor_id,
                content.auditee_id, content.scope, content.regulatory_basis, ReportStatus.open.value,
                content.evidence_file, content.evidence_sha256, now, now,
            ),
        )
        for finding in content.findings:
            finding_id = _gen_id("AF")
            await db.execute(
                """INSERT INTO audit_findings
                   (finding_id, audit_id, finding_number, area, level, title, description,
                    regulatory_reference, status, due_date, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    finding_id, audit_id, finding.finding_number, finding.area, finding.level,
                    finding.title, finding.description, finding.regulatory_reference,
                    FindingStatus.open.value, _date(finding.due_date), now, now,
                ),
            )
            await _write_event(db, "audit_finding", finding_id, "imported", actor, {
                "audit_id": audit_id,
                "import_id": import_id,
                "finding_number": finding.finding_number,
            })
        update = await db.execute(
            """UPDATE audit_report_imports
               SET status = 'imported', verified_by = ?, verified_at = ?, verification_notes = ?, audit_id = ?
               WHERE import_id = ? AND status = 'pending_verification'""",
            (actor, now, notes, audit_id, import_id),
        )
        if update.rowcount != 1:
            raise HTTPException(status_code=409, detail="Audit report import is no longer pending")
        await _write_event(db, "audit_report_import", import_id, "provenance_verified", actor, {
            "audit_id": audit_id,
            "imported_by": candidate["imported_by"],
            "source_auditor_id": candidate["source_auditor_id"],
            "source_sha256": candidate["evidence_sha256"],
            "payload_sha256": candidate["payload_sha256"],
            "finding_count": len(content.findings),
            "verification_notes": notes,
        })
        await _write_event(db, "audit_report", audit_id, "imported", actor, {
            "import_id": import_id,
            "imported_by": candidate["imported_by"],
            "source_auditor_id": candidate["source_auditor_id"],
        })
        await db.commit()
        return {
            "import_id": import_id,
            "audit_id": audit_id,
            "audit_number": candidate["audit_number"],
            "source_auditor_id": candidate["source_auditor_id"],
            "source_auditor_name": candidate["source_auditor_name"],
            "imported_by": candidate["imported_by"],
            "verified_by": actor,
            "verified_at": now,
            "status": "imported",
        }
    except Exception:
        await db.rollback()
        raise
    finally:
        if snapshot is not None:
            snapshot.close()
        await db.close()


@router.post("/audit-report-imports/{import_id}/reject")
async def reject_audit_report_import(
    import_id: str, payload: AuditReportImportRejection, request: Request
):
    _check(request, "audit_report:provenance_verify")
    if _role(request) != "independent_auditor":
        raise HTTPException(status_code=403, detail="Only an independent auditor may reject source provenance")
    reason = payload.reason.strip()
    if len(reason) < 10:
        raise HTTPException(status_code=422, detail="A meaningful rejection reason is required")
    actor = _actor(request)
    now = _now()
    db = await get_db()
    try:
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute(
            "SELECT * FROM audit_report_imports WHERE import_id = ?", (import_id,)
        )).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Audit report import not found")
        candidate = dict(row)
        if candidate["status"] != "pending_verification":
            raise HTTPException(status_code=409, detail="Only pending imports can be rejected")
        if (
            same_principal(request, candidate["imported_by"])
            or same_principal(request, candidate["source_auditor_id"])
            or same_principal(request, candidate["auditee_id"])
        ):
            raise HTTPException(status_code=403, detail="Verifier must be independent of source auditor, auditee, and import operator")
        verifier = await (await db.execute(
            """SELECT u.user_id FROM users u JOIN user_roles ur ON ur.user_id = u.user_id
               WHERE u.user_id = ? AND u.is_active = 1 AND ur.role = 'independent_auditor'""",
            (actor,),
        )).fetchone()
        if verifier is None:
            raise HTTPException(status_code=403, detail="Verifier must be an active independent_auditor account")
        update = await db.execute(
            """UPDATE audit_report_imports
               SET status = 'rejected', verification_notes = ?
               WHERE import_id = ? AND status = 'pending_verification'""",
            (reason, import_id),
        )
        if update.rowcount != 1:
            raise HTTPException(status_code=409, detail="Audit report import is no longer pending")
        await _write_event(db, "audit_report_import", import_id, "provenance_rejected", actor, {
            "imported_by": candidate["imported_by"],
            "source_auditor_id": candidate["source_auditor_id"],
            "reason": reason,
        })
        await db.commit()
        return {"import_id": import_id, "status": "rejected", "rejected_by": actor, "rejected_at": now}
    except Exception:
        await db.rollback()
        raise
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
                regulatory_reference, department, status, due_date, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                finding_id, payload.audit_id, payload.finding_number, payload.area, payload.level,
                payload.title, payload.description, payload.regulatory_reference,
                payload.department, FindingStatus.open.value,
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
    department: Optional[str] = Query(default=None, min_length=1, max_length=50),
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
    if department:
        conditions.append("department = ?")
        params.append(department)
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
        # Department-head closure gate: a finding tagged to a department can only
        # be closed by the head of that department. Leading a department's
        # objectives includes owning the closure of its audit findings.
        actor_role = _role(request)
        db = await get_db()
        try:
            row = await (await db.execute("SELECT status, department, corrective_action_id FROM audit_findings WHERE finding_id = ?", (finding_id,))).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Audit finding not found")
            # Transition validity comes first, so an illegal close is reported as
            # such rather than masked by an authority error.
            if row["status"] != "in_progress":
                raise HTTPException(
                    status_code=409,
                    detail=f"Invalid finding status transition: {row['status']} -> closed",
                )
            dept = (row["department"] or "").strip().lower()
            if not dept:
                # Fail closed: an untagged finding has no accountable head, so
                # closure would bypass the departmental gate entirely.
                raise HTTPException(
                    status_code=409,
                    detail="Assign a department to this finding before it can be closed.",
                )
            if dept:
                dept_head_role = DEPARTMENT_HEAD_ROLES.get(dept)
                if not dept_head_role:
                    # Fail closed. An unmapped department used to skip the gate
                    # entirely, which let any role holding audit_finding:close
                    # close another department's finding.
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Department '{dept}' has no mapped head role; "
                            "configure DEPARTMENT_HEAD_ROLES before closing this finding."
                        ),
                    )
                # system_admin keeps break-glass access, as elsewhere in the system.
                if actor_role not in (dept_head_role, "system_admin"):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Closing a {dept} department finding requires the {dept_head_role} role.",
                    )
            linked_car = row["corrective_action_id"]
            if linked_car:
                car = await (await db.execute(
                    "SELECT status FROM corrective_actions WHERE car_id = ?", (linked_car,)
                )).fetchone()
                if car is None or car["status"] != "closed":
                    raise HTTPException(
                        status_code=409,
                        detail="The linked corrective action must be closed before the finding can be closed.",
                    )
        finally:
            await db.close()
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
        for field in ("title", "description", "area", "level", "regulatory_reference", "department", "due_date", "corrective_action_id"):
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
async def audit_findings_summary(request: Request, department: Optional[str] = Query(default=None, min_length=1, max_length=50)):
    _check(request, "audit_finding:read")
    db = await get_db()
    try:
        conditions = []
        params = []
        if department:
            conditions.append("department = ?")
            params.append(department)
        where = " AND ".join(conditions) if conditions else "1=1"
        by_level_rows = await (await db.execute(f"SELECT level, COUNT(*) AS count FROM audit_findings WHERE {where} GROUP BY level", params)).fetchall()
        by_status_rows = await (await db.execute(f"SELECT status, COUNT(*) AS count FROM audit_findings WHERE {where} GROUP BY status", params)).fetchall()
        by_area_rows = await (await db.execute(f"SELECT area, COUNT(*) AS count FROM audit_findings WHERE {where} GROUP BY area", params)).fetchall()
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


# ==================== PDF RENDERING (Phase 3) ====================

from fastapi.responses import Response
from .pdf_render import render_risk_assessment_pdf, render_mission_sheet_pdf


@router.get("/risk-assessments/{assessment_id}/pdf")
async def download_risk_assessment_pdf(assessment_id: str, request: Request):
    """Download a KFL Drone Risk Assessment PDF for a given assessment."""
    _check(request, "risk_assessment:read")
    db = await get_db()
    try:
        row = await (await db.execute(
            "SELECT * FROM risk_assessments WHERE assessment_id = ?", (assessment_id,)
        )).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Risk assessment not found")
        ra = dict(row)

        # Build hazards list from the assessment's linked hazards
        hazards = []
        hazard_rows = await (await db.execute(
            """
            SELECT h.* FROM hazards h
            JOIN risk_assessment_hazards rah ON rah.hazard_id = h.hazard_id
            WHERE rah.assessment_id = ?
            """,
            (assessment_id,)
        )).fetchall()
        for h in hazard_rows:
            h = dict(h)
            # Build risk score from likelihood and severity
            likelihood_map = {"rare": 1, "unlikely": 2, "possible": 3, "likely": 4, "almost_certain": 5}
            severity_map = {"negligible": 1, "minor": 2, "moderate": 3, "major": 4, "catastrophic": 5}
            l_val = likelihood_map.get(h.get("likelihood", "").lower(), 3)
            s_val = severity_map.get(h.get("severity", "").lower(), 3)
            score = l_val * s_val
            risk_labels = {(1,1): "1 Low", (1,2): "2 Low", (1,3): "3 Low", (1,4): "4 Medium", (1,5): "5 Medium",
                           (2,1): "2 Low", (2,2): "4 Medium", (2,3): "6 Medium", (2,4): "8 High", (2,5): "10 High",
                           (3,1): "3 Low", (3,2): "6 Medium", (3,3): "9 High", (3,4): "12 High", (3,5): "15 High",
                           (4,1): "4 Medium", (4,2): "8 High", (4,3): "12 High", (4,4): "16 High", (4,5): "20 High",
                           (5,1): "5 Medium", (5,2): "10 High", (5,3): "15 High", (5,4): "20 High", (5,5): "25 High"}
            risk_label = risk_labels.get((l_val, s_val), f"{score}")
            ls = f"L{l_val} × S{s_val}"
            hazards.append({
                "hazard": h.get("title", ""),
                "risk": h.get("description", ""),
                "mitigation": h.get("mitigation", ""),
                "score": risk_label,
            })

        # If no linked hazards, fall back to template defaults (for backward compatibility)
        if not hazards:
            hazard_fields = [
                ("Trees", "Collision with canopy or branches.", "Survey canopy height and maintain clearance along the route.", "6 Medium", "L2 × S3"),
                ("Buildings", "Collision with structures or roof obstacles.", "Survey the route and set a buffer from structures.", "6 Medium", "L2 × S3"),
                ("Human traffic", "Injury to people in the flight area.", "Control access. Pause or land if people enter the flight area.", "4 Low", "L1 × S4"),
                ("Wildlife", "Animal disturbance or bird strike.", "Maintain separation. Stop if wildlife approaches or shows distress.", "3 Low", "L1 × S3"),
                ("Manned aircraft", "Mid-air collision.", "Check airspace, scan for traffic and yield immediately to crewed aircraft.", "5 Medium", "L1 × S5"),
                ("Strong winds", "Loss of control or inability to return.", "Check gusts and return margin. Hold if wind exceeds operating limits.", "6 Medium", "L2 × S3"),
                ("Communication towers", "Collision with towers or guy wires.", "Locate towers and guy wires. Keep the flight path clear of both.", "4 Low", "L1 × S4"),
                ("Electric poles / power lines", "Wire strike or electrical contact.", "Identify poles and spans. Set a safe stand-off distance.", "4 Low", "L1 × S4"),
            ]
            for name, risk, mitigation, score, ls in hazard_fields:
                hazards.append({
                    "hazard": name,
                    "risk": risk,
                    "mitigation": mitigation,
                    "score": score,
                })

        pdf_bytes = render_risk_assessment_pdf({
            "location": ra.get("location_coordinates", ra.get("location", "")),
            "date": ra.get("assessed_at", ""),
            "project_type": ra.get("project_type", "Drone Operations"),
            "drone_type": ra.get("drone_type_model", ra.get("exposure", "")),
            "pic": ra.get("pic_full_name", ra.get("assessor_id", "")),
            "hazards": hazards,
            "scoring_note": "Scores assume the controls are in place. Reassess if site conditions warrant a different score.",
            "overall_risk_score": ra.get("risk_score", "—"),
            "overall_risk_level": ra.get("risk_level", "—"),
            "flight_decision": ra.get("flight_decision", "Proceed" if not ra.get("flight_cancelled") else "Hold"),
            "conditions": ra.get("conditions_notes", ra.get("residual_risk", "")),
            "filed_by": ra.get("pic_full_name", ra.get("assessor_id", "")),
            "pic_full_name": ra.get("pic_full_name", ra.get("assessor_id", "")),
            "date_filed": ra.get("assessed_at", ""),
            "approved_by": ra.get("reviewed_by", "Head of Safety"),
            "head_signature": "",
            "approval_date": ra.get("reviewed_at", ""),
        })

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="risk-assessment-{assessment_id}.pdf"'},
        )
    finally:
        await db.close()


@router.get("/missions/{mission_id}/pdf")
async def download_mission_sheet_pdf(mission_id: str, request: Request):
    """Download a KFL Drone Mission Sheet PDF for a given mission."""
    _check(request, "safety:read")
    db = await get_db()
    try:
        row = await (await db.execute(
            "SELECT * FROM missions WHERE mission_id = ?", (mission_id,)
        )).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        m = dict(row)

        # Try to get post-flight report for flight log data
        flights = []
        if m.get("post_flight_report_id"):
            pfr = await (await db.execute(
                "SELECT * FROM post_flight_reports WHERE report_id = ?", (m["post_flight_report_id"],)
            )).fetchone()
            if pfr:
                flights = [{
                    "start": "",
                    "end": "",
                    "total_run": "",
                    "battery": "",
                    "charge_cycles": pfr.get("battery_cycles", ""),
                }]

        pdf_bytes = render_mission_sheet_pdf({
            "location": m.get("location", ""),
            "date": m.get("planned_date", ""),
            "pic_name": m.get("pic_name", ""),
            "operation_type": m.get("mission_type", ""),
            "kcaa_oa": m.get("kcaa_oa_reference", ""),
            "drone_type": m.get("drone_type_model", ""),
            "flights": flights,
            "filed_by": m.get("created_by", ""),
            "pic_full_name": m.get("pic_name", m.get("created_by", "")),
            "date_filed": m.get("created_at", ""),
        })

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="mission-sheet-{mission_id}.pdf"'},
        )
    finally:
        await db.close()
