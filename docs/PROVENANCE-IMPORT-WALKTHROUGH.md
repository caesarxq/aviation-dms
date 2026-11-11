# Provenance Import Walkthrough — Historical Audit Import

## Purpose

Step-by-step guide for staging and verifying a historical audit import through the P3 provenance workflow. For system administrator (importer) and independent auditor (verifier).

## Overview

Historical audit reports must use the provenance import workflow. The system administrator stages a candidate; it remains quarantined until an independent auditor verifies it. Verification atomically creates the audit report and findings.

## Prerequisites

- Source PDF already retained under `attachments/` (this API does not upload files)
- `DMS_AUDIT_EVIDENCE_MAX_BYTES` configured (10 MiB)
- System administrator account (`system_admin` role)
- Independent auditor account (`independent_auditor` role), distinct from importer
- Source auditor ID: `u-safety/security` (Brian Swanya)

## Step 1: Stage the Candidate (System Administrator)

```http
POST /api/p3/audit-report-imports
Content-Type: application/json
Cookie: __Host-kfl_session=<session>; __Host-kfl_csrf=<csrf>
X-CSRF-Token: <csrf>

{
  "audit_number": "SS-KFL-SEP-2026",
  "audit_date": "2026-09-28",
  "source_auditor_id": "u-safety/security",
  "source_auditor_name": "Brian Swanya",
  "auditee_id": "u-accountable",
  "scope": "Safety and Security",
  "regulatory_basis": "Controlled source report",
  "evidence_file": "attachments/SAFETY AND SECURITY SEPTEMBER 2026 AUDIT REPORT.pdf",
  "expected_evidence_sha256": "<sha256 of the retained PDF>",
  "findings": [
    {
      "finding_number": "1",
      "area": "Safety",
      "level": 2,
      "title": "Source-reconciled finding",
      "description": "A representative finding from the controlled source.",
      "regulatory_reference": "KCAA source report",
      "due_date": null
    }
  ]
}
```

Expected: HTTP 201, response includes `import_id` and `status: "pending_verification"`.

### Validation performed at staging

- Source auditor and auditee must be existing canonical users and must be different people
- Source auditor must not be the same as the import operator
- audit_number must not already exist in audit_reports or active imports
- Evidence file must exist under attachments/ with matching SHA-256
- Evidence size must not exceed `DMS_AUDIT_EVIDENCE_MAX_BYTES`
- Evidence is malware-scanned and structurally parsed

## Step 2: Review the Candidate (Independent Auditor)

```http
GET /api/p3/audit-report-imports/{import_id}
```

The response includes:
- `audit_number`, `audit_date`, `source_auditor_id`, `source_auditor_name`, `auditee_id`
- `scope`, `regulatory_basis`
- `evidence_sha256`, `payload_sha256`
- `imported_by`, `created_at`, `status`
- `findings` array

Download and review the source PDF:

```http
GET /api/p3/audit-report-imports/{import_id}/evidence
```

The response is the hash-checked source PDF. Compare it against the controlled source.

### What to verify

| Item | How to Verify |
|------|---------------|
| Source auditor | `u-safety/security` (Brian Swanya) |
| Evidence SHA-256 | Matches controlled source PDF |
| Payload SHA-256 | Matches stored canonical hash |
| Findings | Reconcile every finding against the source report |
| audit_date, scope, regulatory_basis | Compare against controlled source |

## Step 3: Verify the Import (Independent Auditor)

```http
POST /api/p3/audit-report-imports/{import_id}/verify
Content-Type: application/json

{
  "source_checksum_confirmed": true,
  "findings_reconciled": true,
  "verification_notes": "<20+ characters explaining the review basis>"
}
```

Expected: HTTP 200, response includes `audit_id`, `status: "imported"`, `verified_by`.

### Validation performed at verification

- Verifier must be active `independent_auditor`
- Verifier must be distinct from importer, source auditor, and auditee
- Stored payload hash must match recomputed hash
- All duplicated metadata fields (audit_number, audit_date, source_auditor_id, source_auditor_name, auditee_id, scope, regulatory_basis, evidence_file, evidence_sha256) must match stored values
- Evidence file must still exist with matching SHA-256
- No existing audit_report with same audit_number
- Candidate state rechecked under short write transaction

## Step 4: Reject the Import (Independent Auditor, if needed)

```http
POST /api/p3/audit-report-imports/{import_id}/reject
Content-Type: application/json

{
  "reason": "<10+ characters explaining the rejection>"
}
```

Expected: HTTP 200, response includes `status: "rejected"`.

Rejected candidates publish no report or findings and may be resubmitted for review.

## Role Separation Requirements

| Role | Can Stage | Can Verify | Can Reject |
|------|-----------|------------|------------|
| system_admin | Yes | No | No |
| independent_auditor | No | Yes | Yes |
| source auditor (u-safety/security) | No | No | No |
| auditee | No | No | No |

The source auditor, auditee, importer, and verifier must be four distinct principals.

## Error Handling

| Error | Meaning | Action |
|-------|---------|--------|
| HTTP 409 checksum mismatch | Evidence digest does not match supplied checksum | Re-stage with correct checksum |
| HTTP 409 audit number exists | Duplicate audit_number | Use a different audit number |
| HTTP 403 self-verification | Verifier is importer or source participant | Use a distinct independent_auditor |
| HTTP 409 evidence changed | Evidence modified during verification | Re-stage and re-verify |
| HTTP 503 safeguards unavailable | Scanner or quota not configured | Backend/IT to configure |

## What Is NOT Authorized

- Do not use the development-only importer
- Do not change account roles
- Do not activate or invite accounts beyond the pilot
- Do not deploy this workflow to staging
- Do not import the source audit until technical gates pass and review is authorized
