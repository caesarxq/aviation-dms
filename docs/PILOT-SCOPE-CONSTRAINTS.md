# Pilot Scope & Constraints — Restricted Onboarding Pilot

## Purpose

Defines what is in scope and what is explicitly out of scope for the KFL Aviation DMS restricted onboarding pilot. All participants must review and acknowledge before any pilot account is created.

## In Scope

### Accounts and Roles

- Creation of a named, roster-verified `independent_auditor` account as the first restricted pilot account — only after technical gates pass and only with explicit Accountable Manager approval
- System administrator account for staging the first historical audit import
- Role-based access control as defined in `rbac.py` with existing permission grants

### Audit Provenance Workflow (P3)

- Staging historical audit report imports via `/api/p3/audit-report-imports` (system_admin only)
- Independent provenance verification via `/api/p3/audit-report-imports/{import_id}/verify` (independent_auditor only)
- Rejection of pending imports via `/api/p3/audit-report-imports/{import_id}/reject` (independent_auditor only)
- Download of hash-checked source evidence PDF via `/api/p3/audit-report-imports/{import_id}/evidence`

### Personnel Uploads (P2)

- Personnel credential document upload via `/api/p2/personnel/uploads/file`
- Upload verification/rejection via `/api/p2/personnel/uploads/{upload_id}/verify`
- Upload file download via `/api/p2/personnel/uploads/{upload_id}/file`

### Audit Reports (P3)

- Creation of current/future audit reports via `/api/p3/audit-reports` (backdated dates rejected; historical records must use provenance import)
- Listing audit reports with pagination, status filter, and text search
- Evidence download for existing audit reports via `/api/p3/audit-reports/{audit_id}/evidence`

### Backup & Restore Validation

- Read-only backup candidate manifest creation and verification via `backup_validation.py`
- Orphan file inventory via `upload_reconciliation.py` (report only)

## Out of Scope

| Item | Reason |
|------|--------|
| Flight release | `FLIGHT_RELEASE_ENABLED=false`; remains disabled until accountable postholders sign source-to-rule mapping |
| Staging access | Staging URL `https://roc.kfl.ke` remains unchanged; no staging access for pilot |
| Source-PDF upload through UI | P3 API references pre-retained PDFs only; not a file-upload interface |
| Automatic file deletion/repair | Orphan reconciliation is report-only; records custodian must classify findings first |
| Commit or push to repository | Worktree remains uncommitted until explicit authorization |
| Account invitation or role changes | System administrator owns roster/invitations; no changes without authorization |
| Real audit import | No audit has been imported yet; first import requires postholder confirmation |
| Off-host restore drill | Pending Accountable Manager-approved recovery objectives and authorized destination |
| Source-manual reconciliation | DG Appendix 3 mapping discrepancy open for postholder reconciliation |

## Upload Limits

| Parameter | Value | Source |
|-----------|-------|--------|
| Personnel per-file cap | 10 MiB | Existing cap, preserved |
| KCAA evidence per-file cap | 10 MiB | Existing cap, preserved |
| P3 evidence max | 10 MiB (10485760 bytes) | `DMS_AUDIT_EVIDENCE_MAX_BYTES` |
| P3 import body max | 5 MiB (5242880 bytes) | `DMS_P3_IMPORT_BODY_MAX_BYTES` |
| System storage quota | 30 GB | `DMS_UPLOAD_STORAGE_QUOTA_BYTES` |
| Scanner timeout | 60 seconds | `DMS_CLAMD_TIMEOUT_SECONDS` / `DMS_CLAMD_MAX_TIMEOUT_SECONDS` |

## Identity Preservation

- Source auditor ID: `u-safety/security` (literal, including slash)
- Source auditor name: `Brian Swanya` (correct spelling, not Swanka)
- Permission grants: `audit_report:read` for `head_quality` and `accountable_manager`; `safety:read` for `occurrence_reporter`
- `as_contracted` grants unchanged until user-approved per-person/function scope

## Open Gates (Pilot May Proceed, But These Block Operational Go/No-Go)

1. Off-host restore target not yet provided by Accountable Manager
2. Source-manual DG Appendix 3 mapping discrepancy not reconciled by responsible postholders
3. Reverse-proxy body limits not validated under load

## Sign-off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Accountable Manager | | | |
| Records Custodian | | | |
| System Administrator | | | |
| Independent Auditor (pilot) | | | |
