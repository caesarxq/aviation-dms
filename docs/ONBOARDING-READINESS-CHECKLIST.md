# Onboarding Readiness Checklist — Restricted Pilot

## Purpose

Binary gate confirmation before any pilot account is invited or any upload is enabled. Each item must be verified true before proceeding to the next phase.

## Scope

Applies to the KFL Aviation DMS restricted onboarding pilot. Does not authorize staging access, deployment, source-PDF upload through the UI, commit, or account invitation.

## Gate Items

### Upload Safeguards

| # | Item | Status | Evidence |
|---|------|--------|----------|
| U1 | `DMS_UPLOAD_QUOTA_SCOPE=system` configured | | `docker-compose.yml` line 19 |
| U2 | `DMS_UPLOAD_STORAGE_QUOTA_BYTES=30000000000` configured (30 GB) | | `docker-compose.yml` line 20 |
| U3 | Internal `clamd` service provisioned at `clamd:3310` | | `docker-compose.yml` clamd service |
| U4 | `DMS_CLAMD_TIMEOUT_SECONDS=60` configured | | `docker-compose.yml` line 25 |
| U5 | `DMS_CLAMD_MAX_TIMEOUT_SECONDS=60` configured | | `docker-compose.yml` line 26 |
| U6 | `DMS_AUDIT_EVIDENCE_MAX_BYTES=10485760` (10 MiB) configured | | `docker-compose.yml` line 25 |
| U7 | `DMS_P3_IMPORT_BODY_MAX_BYTES=5242880` (5 MiB) configured | | `docker-compose.yml` line 26 |
| U8 | `upload-validator` container verified: UID/GID 10002, read-only root, cap_drop ALL, no-new-privileges, internal-only network | | Docker inspection completed |
| U9 | `clamd` container verified: dropped capabilities, no-new-privileges, 1 GiB memory, no host port publishing | | Docker inspection completed |
| U10 | Uploads fail closed when any scanner/quota setting is missing | | `upload_safety.py` `load_upload_safety_policy()` |
| U11 | Reverse proxy (Caddy) routes `/api/*` to backend, security headers set | | `Caddyfile` |

### Historical Audit Provenance (P3)

| # | Item | Status | Evidence |
|---|------|--------|----------|
| P1 | Historical report creation rejects backdated dates (before current UTC date) | | `p3_routes.py` `create_audit_report` |
| P2 | Provenance import route requires `system_admin` role | | `p3_routes.py` `create_audit_report_import` |
| P3 | Provenance verification requires `independent_auditor` role, distinct from importer/auditor/auditee | | `p3_routes.py` `verify_audit_report_import` |
| P4 | Verification compares all duplicated metadata fields against hashed payload | | `p3_routes.py` verify field comparison |
| P5 | Verification validates evidence snapshot before `BEGIN IMMEDIATE`, rechecks under short transaction | | `p3_routes.py` `verify_audit_report_import` |
| P6 | Verifier UI displays audit_date, scope, regulatory_basis | | `AuditReportImportWorkflow.tsx` |

### Personnel Uploads (P2)

| # | Item | Status | Evidence |
|---|------|--------|----------|
| W1 | Personnel file validation runs before `BEGIN IMMEDIATE` | | `p2_routes.py` `verify_personnel_upload` |
| W2 | Verification re-reads and compares full row state under short write transaction | | `p2_routes.py` `current_upload != upload` check |
| W3 | Uploader or credential subject cannot verify their own upload | | `p2_routes.py` `same_principal` checks |
| W4 | Rejection requires reason; 1000 character max | | `p2_routes.py` |

### Backup & Restore

|| # | Item | Status | Evidence |
|---|------|--------|----------|
| B1 | `backup_validation.py` validates manifest, SQLite integrity, schema tables/columns, storage references | | `backup_validation.py` — verified on `dms-backup-20261111T085143Z`: SQLite quick_check/integrity_check OK, 62 tables, 25 checksums OK |
| B2 | Validator refuses candidates overlapping active development data | | `backup_validation.py` `_candidate_root` |
| B3 | Orphan reconciliation is report-only; no auto-delete | | `upload_reconciliation.py` |
| B4 | Full-stack backup container run: Docker images (6), SQLite via online backup API, storage roots, configs, security artifacts, dependencies; pushed to `10.20.173.120:~/dms-backups/` | | `backend/scripts/full-stack-backup.sh` — verified end-to-end |
| B5 | Reverse-proxy body limits: Caddy `max_body_size 10MiB` API / `1MiB` frontend; clamd port 3310 not published to host | | `Caddyfile`, `docker-compose.yml` |
| B6 | Cron job installed: `0 2 * * *` daily backup on backend instance | | `crontab -l` on `10.20.4.234` |
| B7 | Off-host restore target confirmed: `ubuntu@10.20.173.120:~/dms-backups/` via bastion `ubuntu@145.241.152.126` | | Verified both instances |

### Retention & Legal Hold

| # | Item | Status | Evidence |
|---|------|--------|----------|
| R1 | `retention_rules` table seeded with RR-023 (36 months general) and RR-025 (lifetime metadata) | | `database.py` seed data |
| R2 | `legal_holds` table implemented with impose/release endpoints | | `p0_routes.py` legal-hold routes |
| R3 | No automatic file disposition; records custodian approves disposition | | `upload_reconciliation.py` report-only |

### Operational Constraints

| # | Item | Status | Evidence |
|---|------|--------|----------|
| O1 | Flight release disabled (`FLIGHT_RELEASE_ENABLED=false`) | | `docker-compose.yml` |
| O2 | Staging untouched; no deployment or account change | | Constraints log |
| O3 | Source manuals not rewritten; DG mapping discrepancy open for postholder reconciliation | | Readiness docs |
| O4 | `u-safety/security` preserved as source auditor ID; `Brian Swanya` spelling preserved | | Constraints log |

## Gate Closure

All items above must be marked complete before proceeding to Pilot Scope & Constraints. Items marked open (off-host restore target, source-manual reconciliation) are recorded as open gates and do not block pilot creation but must be resolved before operational go/no-go.

## Sign-off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Records Custodian | | | |
| Accountable Manager | | | |
| Backend/IT Lead | | | |
| System Administrator | | | |
