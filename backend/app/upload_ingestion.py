"""Document ingestion pipeline: PDF text extraction + auto-routing.

Uploaded credential/certificate PDFs are text-extracted, classified by
document type, and auto-routed to the correct business table with extracted
fields pre-populated. All extracted records require human verification
(verification_status = 'pending') before becoming authoritative.

Historical audits, CARs and findings reports are classified separately and
route to audit_report_imports (quarantine). They are NEVER written directly
to audit_reports / audit_findings / corrective_actions and require
independent provenance verification before import.
"""

import io
import re
import logging
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional
from pypdf import PdfReader

logger = logging.getLogger(__name__)


class IngestionResult:
    """Result of ingesting a single PDF document."""

    def __init__(
        self,
        document_type: str,
        confidence: float,
        extracted_fields: dict[str, Any],
        target_table: str,
        raw_text: str,
    ):
        self.document_type = document_type
        self.confidence = confidence
        self.extracted_fields = extracted_fields
        self.target_table = target_table
        self.raw_text = raw_text


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from a PDF file using pypdf."""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                logger.warning("Failed to extract text from a PDF page", exc_info=True)
        return "\n".join(parts)
    except Exception as exc:
        logger.exception("PDF text extraction failed: %s", exc)
        return ""


def _find_pattern(text: str, pattern: str, flags: int = re.IGNORECASE) -> Optional[str]:
    """Return the first regex match group, or None."""
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _find_all_patterns(text: str, pattern: str, flags: int = re.IGNORECASE, limit: int = 10) -> list[str]:
    """Return up to `limit` distinct stripped match groups for a pattern."""
    seen: list[str] = []
    for match in re.finditer(pattern, text, flags):
        value = match.group(1).strip() if match.lastindex else match.group(0).strip()
        if value and value not in seen:
            seen.append(value)
        if len(seen) >= limit:
            break
    return seen


def _find_date(text: str) -> Optional[str]:
    """Find a date in common formats (YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, etc.)."""
    patterns = [
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{2}/\d{2}/\d{4})",
        r"(\d{2}-\d{2}-\d{4})",
        r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _parse_date(raw: Optional[str]) -> Optional[str]:
    """Normalize a date string to ISO format (YYYY-MM-DD)."""
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def _compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA256 hash of file bytes for duplicate detection."""
    return hashlib.sha256(file_bytes).hexdigest()


def _get_target_directory(document_type: str) -> str:
    """Get the target directory for a document type."""
    mapping = {
        "insurance_policy": "insurance",
        "aircraft_registration": "registration",
        "personnel_license": "licenses",
        "operations_authorization": "authorizations",
    }
    return mapping.get(document_type, "unknown")


def ensure_target_directory(document_type: str, storage_root: Path) -> Path:
    """Auto-populate the classified storage directory for a document type.

    Creates ``storage_root / <target_directory>`` (e.g.
    ``storage_root / "insurance"`` for an ``insurance_policy``) so that
    classified uploads always have a populated destination directory.
    """
    directory = storage_root / _get_target_directory(document_type)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _extract_findings(text: str) -> list[dict]:
    """Extract audit/CAR finding candidates from a historical report."""
    findings: list[dict] = []
    for number in _find_all_patterns(
        text, r"(?:FINDING|CAR)[-:\s#]+([A-Z0-9][A-Z0-9\-/]{1,20})", limit=20
    ):
        findings.append(
            {
                "finding_number": number,
                "area": None,
                "level": None,
                "title": None,
                "description": None,
                "regulatory_reference": None,
                "due_date": _parse_date(_find_date(text)),
            }
        )
    return findings


def _classify_historical_audit_or_car(upper: str, text: str) -> Optional[IngestionResult]:
    """Classify historical audit reports and CAR / findings reports.

    These are NEVER applied directly to audit_reports / audit_findings /
    corrective_actions. They route to audit_report_imports (quarantine) and
    require independent provenance verification before import.
    """
    audit_indicators = ["AUDIT REPORT", "AUDIT NUMBER", "AUDITEE", "AUDITOR", "SCOPE", "REGULATORY BASIS"]
    car_indicators = ["CORRECTIVE ACTION REQUEST", "CORRECTIVE ACTION", "CAR-", "AUDIT FINDING"]

    audit_score = sum(1 for kw in audit_indicators if kw in upper)
    car_score = sum(1 for kw in car_indicators if kw in upper)
    if "FINDING NUMBER" in upper or "FINDINGS" in upper:
        audit_score += 1
        car_score += 1

    is_audit = audit_score >= 3 or "AUDIT REPORT" in upper
    is_car = car_score >= 2 or "CORRECTIVE ACTION REQUEST" in upper

    if not (is_audit or is_car):
        return None

    document_type = "car_findings_report" if is_car and not is_audit else "audit_report"
    confidence = 0.78 if (is_audit and is_car) else 0.72

    audit_number = (
        _find_pattern(text, r"AUDIT (?:NUMBER|NO|#)[:.\s]+([A-Z0-9][A-Z0-9\-/]{1,20})")
        or _find_pattern(text, r"AUDIT[-:\s]+([A-Z0-9][A-Z0-9\-/]{1,20})")
    )

    extracted_fields: dict[str, Any] = {
        "document_type": document_type,
        "audit_number": audit_number,
        "audit_date": _parse_date(_find_date(text)),
        "scope": _find_pattern(text, r"SCOPE[:.\s]+([^\n]{5,160})"),
        "regulatory_basis": _find_pattern(text, r"REGULATORY BASIS[:.\s]+([^\n]{5,160})"),
        "source_issued_date": _parse_date(_find_date(text)),
        "findings": _extract_findings(text),
    }

    return IngestionResult(
        document_type=document_type,
        confidence=confidence,
        extracted_fields=extracted_fields,
        target_table="audit_report_import",
        raw_text=text,
    )


def _classify_kcaa_correspondence(upper: str, text: str) -> Optional[IngestionResult]:
    keywords = ["KCAA", "CORRESPONDENCE", "DIRECTIVE", "ADVISORY CIRCULAR", "LETTER", "NOTICE"]
    score = sum(1 for kw in keywords if kw in upper)
    if score >= 3 or ("KCAA" in upper and ("CORRESPONDENCE" in upper or "DIRECTIVE" in upper)):
        return IngestionResult(
            document_type="kcaa_correspondence",
            confidence=0.75,
            extracted_fields={
                "doc_class": "policy",
                "title": "KCAA Correspondence",
                "description": _find_pattern(text, r"(?:REFERENCE|SUBJECT|RE:)[:.\s]+([^\n]{5,160})")
                or "Historical KCAA correspondence",
                "source_issue_revision": _find_pattern(text, r"(?:ISSUE|REV)[:.\s]+([0-9.]+)"),
                "source_issued_date": _parse_date(_find_date(text)),
                "issuing_authority": "KCAA",
            },
            target_table="documents",
            raw_text=text,
        )
    return None


def _classify_mission_sheet(upper: str, text: str) -> Optional[IngestionResult]:
    keywords = ["MISSION SHEET", "FLIGHT MISSION", "PIC NAME", "MISSION DATE", "DRONE TYPE", "KCAA OA"]
    score = sum(1 for kw in keywords if kw in upper)
    if score >= 3:
        return IngestionResult(
            document_type="mission_sheet",
            confidence=0.78,
            extracted_fields={
                "doc_class": "record",
                "title": "Mission Sheet",
                "description": "Historical mission sheet",
                "source_issued_date": _parse_date(_find_date(text)),
                "issuing_authority": "KCAA",
                "pic_name": _find_pattern(text, r"PIC (?:NAME|-)[:.\s]+([^\n]{3,60})"),
                "kcaa_oa": _find_pattern(text, r"KCAA OA[:.\s]+([A-Z0-9][A-Z0-9\-/]{1,20})"),
                "drone_type": _find_pattern(text, r"DRONE TYPE[:.\s]+([^\n]{3,40})"),
            },
            target_table="documents",
            raw_text=text,
        )
    return None


def _classify_flight_log(upper: str, text: str) -> Optional[IngestionResult]:
    keywords = ["FLIGHT LOG", "FLIGHT TIME", "TAKEOFF", "LANDING", "BLOCK TIME", "AIRCRAFT REGISTRATION"]
    score = sum(1 for kw in keywords if kw in upper)
    if score >= 3:
        return IngestionResult(
            document_type="flight_log",
            confidence=0.76,
            extracted_fields={
                "doc_class": "record",
                "title": "Flight Log",
                "description": "Historical flight log",
                "source_issued_date": _parse_date(_find_date(text)),
                "aircraft_registration": _find_pattern(text, r"REG(?:ISTRATION)?[:.\s]+([A-Z0-9\-]{3,12})"),
            },
            target_table="documents",
            raw_text=text,
        )
    return None


def classify_and_extract(text: str) -> IngestionResult:
    """Classify a document and extract key fields.

    Classification is heuristic: keyword matching against known document
    types. Returns low-confidence results for unknown documents so they
    can be manually classified.

    Classifiers run from most specific to least specific so a historical
    audit / CAR report is not mistaken for a generic operations authorization
    or KCAA correspondence.
    """
    upper = text.upper()

    # --- Historical audit reports and CAR / findings reports ---
    # These route to audit_report_imports (quarantine) and are never written
    # directly to audit_reports / audit_findings / corrective_actions.
    result = _classify_historical_audit_or_car(upper, text)
    if result is not None:
        return result

    # --- Historical KCAA correspondence ---
    result = _classify_kcaa_correspondence(upper, text)
    if result is not None:
        return result

    # --- Historical mission sheets ---
    result = _classify_mission_sheet(upper, text)
    if result is not None:
        return result

    # --- Historical flight logs ---
    result = _classify_flight_log(upper, text)
    if result is not None:
        return result

    # --- Aircraft Insurance Policy ---
    insurance_keywords = ["INSURANCE", "POLICY", "INSURER", "COVERAGE", "PREMIUM", "HULL", "LIABILITY"]
    insurance_score = sum(1 for kw in insurance_keywords if kw in upper)
    if insurance_score >= 3:
        return IngestionResult(
            document_type="insurance_policy",
            confidence=0.85,
            extracted_fields={
                "insurance_type": _detect_insurance_type(upper),
                "insurer": _find_pattern(text, r"INSURER[:.\s]+([^\n]{3,80})") or _find_pattern(text, r"INSURANCE COMPANY[:.\s]+([^\n]{3,80})"),
                "policy_number": _find_pattern(text, r"POLICY (?:NO|NUMBER|#)[:.\s]+([A-Z0-9\-]{3,30})") or _find_pattern(text, r"POL[:.\s]+([A-Z0-9\-]{3,30})"),
                "coverage_amount": _find_pattern(text, r"COVERAGE[:.\s]+([\d,\.]+)"),
                "currency": "USD",
                "start_date": _parse_date(_find_date(text)),
                "expiry_date": _parse_date(_find_date(text)),
            },
            target_table="aircraft_insurance",
            raw_text=text,
        )

    # --- Aircraft Registration Document ---
    reg_keywords = ["REGISTRATION", "REGISTERED", "AIRCRAFT", "TAIL NUMBER", "MARK", "CERTIFICATE OF REGISTRATION"]
    reg_score = sum(1 for kw in reg_keywords if kw in upper)
    if reg_score >= 3 and "REGISTRATION" in upper:
        return IngestionResult(
            document_type="aircraft_registration",
            confidence=0.85,
            extracted_fields={
                "document_type": "registration",
                "document_number": _find_pattern(text, r"REGISTRATION[:.\s#]+([A-Z0-9\-]{3,20})") or _find_pattern(text, r"REG[:.\s#]+([A-Z0-9\-]{3,20})"),
                "issuing_authority": "KCAA",
                "issue_date": _parse_date(_find_date(text)),
                "expiry_date": _parse_date(_find_date(text)),
            },
            target_table="aircraft_documents",
            raw_text=text,
        )

    # --- Personnel License ---
    license_keywords = ["LICENSE", "LICENCE", "PILOT", "REMOTE PILOT", "RATING", "MEDICAL", "TYPE RATING"]
    license_score = sum(1 for kw in license_keywords if kw in upper)
    if license_score >= 3:
        return IngestionResult(
            document_type="personnel_license",
            confidence=0.8,
            extracted_fields={
                "license_type": _detect_license_type(upper),
                "license_number": _find_pattern(text, r"LICENSE (?:NO|NUMBER|#)[:.\s]+([A-Z0-9\-]{3,30})") or _find_pattern(text, r"LIC[:.\s]+([A-Z0-9\-]{3,30})"),
                "issuing_authority": "KCAA",
                "issued_date": _parse_date(_find_date(text)),
                "expiry_date": _parse_date(_find_date(text)),
                "aircraft_type": _find_pattern(text, r"(?:AIRCRAFT|TYPE)[:.\s]+([A-Z0-9\s]{2,30})"),
            },
            target_table="personnel_licenses",
            raw_text=text,
        )

    # --- Import Permit / Temporary Import Permit (KCAA import permits) ---
    # These are personnel/credential document classes uploaded via the document
    # uploader and routed to the documents table for verification.
    import_keywords = ["IMPORT PERMIT", "TEMPORARY IMPORT", "IMPORTATION", "IMPORT"]
    import_score = sum(1 for kw in import_keywords if kw in upper)
    if import_score >= 2 and ("IMPORT PERMIT" in upper or "TEMPORARY IMPORT" in upper):
        document_type = (
            "temporary_import_permit"
            if "TEMPORARY IMPORT" in upper
            else "import_permit"
        )
        return IngestionResult(
            document_type=document_type,
            confidence=0.82,
            extracted_fields={
                "doc_class": document_type,
                "title": document_type.replace("_", " ").title(),
                "description": "Historical KCAA import permit",
                "issuing_authority": "KCAA",
                "permit_number": _find_pattern(
                    text, r"PERMIT (?:NO|NUMBER|#)[:.\\s]+([A-Z0-9\\-]{3,30})"
                )
                or _find_pattern(
                    text, r"IMPORT[:.\\s]+([A-Z0-9\\-]{3,30})"
                ),
                "issue_date": _parse_date(_find_date(text)),
                "expiry_date": _parse_date(_find_date(text)),
                "source_issued_date": _parse_date(_find_date(text)),
            },
            target_table="documents",
            raw_text=text,
        )

    # --- Operations Authorization / Historical Document ---
    auth_keywords = ["AUTHORIZATION", "OPERATIONS AUTHORIZATION", "OA REFERENCE", "KCAA OA", "AUTHORISED", "AUTHORIZED", "KCAA", "OPERATIONS"]
    auth_score = sum(1 for kw in auth_keywords if kw in upper)
    # Higher score if we see specific KCAA OA patterns
    if "KCAA OA" in upper or "OPERATIONS AUTHORIZATION" in upper:
        auth_score += 2
    if auth_score >= 3:
        return IngestionResult(
            document_type="operations_authorization",
            confidence=0.85,
            extracted_fields={
                "doc_class": "policy",
                "title": "Operations Authorization",
                "description": _find_pattern(text, r"AUTHORIZATION[:.\s]+([^\n]{10,200})") or "KCAA Operations Authorization",
                "source_issue_revision": _find_pattern(text, r"(?:ISSUE|REV)[:.\s]+([0-9.]+)"),
                "source_issued_date": _parse_date(_find_date(text)),
            },
            target_table="documents",
            raw_text=text,
        )

    # Unknown -- low confidence, needs manual classification
    return IngestionResult(
        document_type="unknown",
        confidence=0.0,
        extracted_fields={},
        target_table="unknown",
        raw_text=text,
    )


def _detect_insurance_type(upper: str) -> str:
    if "HULL" in upper:
        return "hull"
    if "LIABILITY" in upper and "WAR" not in upper:
        return "liability"
    if "WAR" in upper:
        return "war_risk"
    if "PASSENGER" in upper:
        return "passenger_liability"
    if "CARGO" in upper:
        return "cargo_liability"
    return "hull"


def _detect_license_type(upper: str) -> str:
    if "MEDICAL" in upper:
        return "medical"
    if "TYPE RATING" in upper:
        return "type_rating"
    if "PILOT" in upper:
        return "pilot_license"
    if "ENGLISH" in upper:
        return "english_proficiency"
    return "pilot_license"
