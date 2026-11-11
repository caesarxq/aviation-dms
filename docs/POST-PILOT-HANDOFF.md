# Post-Pilot Handoff Memo — Restricted Onboarding Pilot

## Purpose

Handoff document for the ongoing operations team. Records what was validated during the pilot, what remains open, and what approvals are needed before operational go/no-go.

## Pilot Summary

| Parameter | Value |
|-----------|-------|
| Pilot scope | Restricted onboarding: independent_auditor account, provenance import, personnel uploads, audit reports |
| Pilot duration | From first account creation to go/no-go decision |
| Accounts created | `independent_auditor` (first restricted pilot) |
| Imports performed | None yet (first import pending postholder confirmation) |
| Staging access | None |
| Deployment | None |

## What Was Validated

| Area | Item | Status |
|------|------|--------|
| Upload safeguards | Quota 30 GB, scanner clamd:3310, timeouts 30s/60s | Verified |
| Upload safeguards | P3 evidence max 10 MiB, import body max 5 MiB | Verified |
| Parser isolation | UID 10002, read-only root, cap_drop ALL, internal network | Verified |
| ClamAV isolation | Dropped caps, no-new-privileges, 1 GiB memory, no host port | Verified |
| Historical date gate | Backdated report creation rejected | Verified |
| Provenance import | Role separation, metadata comparison, snapshot validation | Verified |
| Personnel upload | Validation before write, full row recheck | Verified |
| Retention policy | RR-023 (36 months), RR-025 (lifetime metadata) | Seeded |
| Legal hold | Impose/release endpoints implemented | Implemented |
| Reverse proxy | Caddy routes, security headers, proxy headers | Configured |

## Open Items (Block Operational Go/No-Go)

| Item | Owner | Required For | Status |
|------|-------|--------------|--------|
| Off-host restore target | Accountable Manager | Restore drill, go/no-go | Pending |
| Source-manual DG Appendix 3 mapping | Responsible Postholders | Source-manual reconciliation | Pending |
| Local missing/unmatched file classification | Records Custodian | Disposition approval | Pending |
| Reverse-proxy body limits under load | Backend/IT | Production readiness | Pending |

## Configuration Values in Effect

| Variable | Value |
|----------|-------|
| `DMS_UPLOAD_QUOTA_SCOPE` | `system` |
| `DMS_UPLOAD_STORAGE_QUOTA_BYTES` | `30000000000` |
| `DMS_CLAMD_HOST` | `clamd` |
| `DMS_CLAMD_PORT` | `3310` |
| `DMS_CLAMD_TIMEOUT_SECONDS` | `30` |
| `DMS_CLAMD_MAX_TIMEOUT_SECONDS` | `60` |
| `DMS_AUDIT_EVIDENCE_MAX_BYTES` | `10485760` |
| `DMS_P3_IMPORT_BODY_MAX_BYTES` | `5242880` |
| `FLIGHT_RELEASE_ENABLED` | `false` |

## Identity Map (Preserved)

| User ID | Primary Role | Additional Roles |
|---------|-------------|-----------------|
| u-admin | system_admin | head_maintenance |
| u-quality | head_quality | librarian, records_custodian |
| u-safety/security | head_safety | head_security |
| u-ops | head_operations | chief_pilot, head_training |
| u-flight-ops | flight_ops_officer | dg_coordinator |
| u-accountable | accountable_manager | — |
| u-auditor | independent_auditor | — |
| u-reporter | occurrence_reporter | — |

## Permission Grants (Preserved)

| Permission | Grantee |
|------------|---------|
| `audit_report:read` | head_quality, accountable_manager |
| `safety:read` | occurrence_reporter |

## Next Steps for Operations Team

1. Receive off-host restore target from Accountable Manager
2. Schedule restore drill using `backup_validation.py verify`
3. Complete source-manual DG Appendix 3 reconciliation with responsible postholders
4. Classify local missing/unmatched files with Records Custodian
5. Validate reverse-proxy body limits under load
6. Obtain Accountable Manager go/no-go for operational cutover

## Escalation Contacts

| Area | Contact |
|------|---------|
| Scanner outage | Backend/IT Lead |
| Quota exhaustion | Backend/IT Lead |
| Retention/disposition | Records Custodian |
| Restore drill | Accountable Manager |
| Source-manual mapping | Responsible Postholders |
