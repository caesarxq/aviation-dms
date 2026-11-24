"""Document ingestion pipeline: PDF text extraction + auto-routing.

Uploaded credential/certificate PDFs are text-extracted, classified by
document type, and auto-routed to the correct business table with extracted
fields pre-populated. All extracted records require human verification
(verification_status = 'pending') before becoming authoritative.
"""

import io
import re
import logging
import hashlib
from datetime import datetime, date
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


def classify_and_extract(text: str) -> IngestionResult:
    """Classify a document and extract key fields.

    Classification is heuristic: keyword matching against known document
    types. Returns low-confidence results for unknown documents so they
    can be manually classified.
    """
    upper = text.upper()

    # --- Aircraft Insurance Policy ---
    insurance_keywords = ["INSURANCE", "POLICY", "INSURER", "COVERAGE", "PREMIUM", "HULL", "LIABILITY"]
    insurance_score = sum(1 for kw in insurance_keywords if kw in upper)
    if insurance_score >= 3:
        return IngestionResult(
            document_type="insurance_policy",
            confidence=0.85,
            extracted_fields={
                "insurance_type": _detect_insurance_type(upper),
                "insurer": _find_pattern(text, r"INSURER[:\\s]+([^\n]{3,80})") or _find_pattern(text, r"INSURANCE COMPANY[:\\s]+([^\n]{3,80})"),
                "policy_number": _find_pattern(text, r"POLICY (?:NO|NUMBER|#)[:\\s]+([A-Z0-9\\-]{3,30})") or _find_pattern(text, r"POL[:\\s]+([A-Z0-9\\-]{3,30})"),
                "coverage_amount": _find_pattern(text, r"COVERAGE[:\\s]+([\d,\.]+)"),
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
                "document_number": _find_pattern(text, r"REGISTRATION[:\\s#]+([A-Z0-9\\-]{3,20})") or _find_pattern(text, r"REG[:\\s#]+([A-Z0-9\\-]{3,20})"),
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
                "license_number": _find_pattern(text, r"LICENSE (?:NO|NUMBER|#)[:\\s]+([A-Z0-9\\-]{3,30})") or _find_pattern(text, r"LIC[:\\s]+([A-Z0-9\\-]{3,30})"),
                "issuing_authority": "KCAA",
                "issued_date": _parse_date(_find_date(text)),
                "expiry_date": _parse_date(_find_date(text)),
                "aircraft_type": _find_pattern(text, r"(?:AIRCRAFT|TYPE)[:\\s]+([A-Z0-9\\s]{2,30})"),
            },
            target_table="personnel_licenses",
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
            confidence=0.85,  # Increased from 0.75
            extracted_fields={
                "doc_class": "policy",
                "title": "Operations Authorization",
                "description": _find_pattern(text, r"AUTHORIZATION[:\\s]+([^\n]{10,200})") or "KCAA Operations Authorization",
                "source_issue_revision": _find_pattern(text, r"(?:ISSUE|REV)[:\\s]+([0-9.]+)"),
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