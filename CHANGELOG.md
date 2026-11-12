# KFL Aviation DMS — Changelog

All notable changes to the Aviation DMS project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to Semantic Versioning where applicable.

---

## [Unreleased]

### Fixed
- Fixed indentation bug in `backend/app/database.py`: the `ver_id` and version-insert block was inside `for c in classifications:` instead of `for d in docs:`, causing `UNIQUE constraint failed: document_versions.version_id` on seed (`3465d73`)
- Updated `Caddyfile.bastion` staging proxy to route to new ports 8001 (backend) and 8081 (frontend) after staging instance port changes (`3465d73`)
- Removed Terraform infrastructure (`terraform/`) and all related references from `Caddyfile.bastion`, `.github/workflows/deploy.yml`, `scripts/find-ubuntu-image.sh`, and `.gitignore` (`386e99b`)

### Changed
- Staging instance `10.20.4.234`: backend port 8000→8001, frontend port 8080→8081 (port conflict avoidance)
- Production instance `10.20.1.69`: deployed with `prod-manual-20261111` tag; SMTP configured via env var fallback; notifications disabled
- Bastion `145.241.152.126`: Caddy reload activated `roc.kfl.ke` → production proxy

### Removed
- `terraform/oci-prod/` and `terraform/oci-backup/` directories (all `.tf`, `.tfvars.example`, `README.md`, `variables.tf`, `outputs.tf`)
- `https_proxy` service block from base and production Docker Compose files

---

## [v1.0.0] — 2026-11-12

### Added
- Full Controlled Document Security (Gate 3): RBAC permissions for `document.download`, `document.section.view`, `document.section.extract`, `document.section.manage`, `document.policy.manage`, `document.extract.approve`, `document.classify`
- Database tables: `document_classifications`, `document_sections`, `extraction_requests`, `extractions`, `document_files`
- Section extraction with approval workflow
- Identity-bound watermarking service for controlled document delivery
- KCAA-restricted download hardening
- Document classification management UI (`DocumentControllerDashboard.tsx`)
- Extraction request tracking and audit events UI (`ComplianceDashboard.tsx`)
- API client for controlled document security endpoints (`controlledDocument.ts`)
- Production instance `10.20.1.69` (OCI Ubuntu 26.04 aarch64) with all 4 containers: backend, frontend, upload-validator, clamd
- Staging instance `10.20.4.234` with dev mode, 1 GB quota
- ClamAV 1.5.4 malware scanning (3,628,258 signatures) with EICAR detection verified
- Upload validator isolation: UID 10002, read-only FS, cap_drop ALL, no-new-privileges, 768 MiB, 1 CPU, 32 PIDs
- 15 documents seeded; 9 source PDFs inserted into `document_files`

### Security
- Separated staging (cloud, dev mode, 1 GB quota) from production (OCI, strict security, 30 GB quota)
- Independent `dms_data` volumes for staging and production
- `CONTROLLED_DOCUMENT_SECURITY_ENABLED` feature flag for code deploy without feature activation
- Fail-closed deployment scripts: exit non-zero on any error; nothing deleted from live systems
- Manual approval gate required before production promotion
- `FLIGHT_RELEASE_ENABLED=false` (flight release remains disabled)

---

## [v0.9.0] — 2026-11-11

### Added
- Gate 2: 9 source documents inserted into `document_files` (DOC-001, DOC-002, DOC-006, DOC-007, DOC-012, DOC-016, DOC-017, DOC-018, DOC-019)
- Upload-validator isolation verified (UID 10002, read-only FS, cap_drop ALL, no-new-privileges, 768 MiB, 1 CPU, 32 PIDs, no host port)
- EICAR detected inside clamd container
- Change Request Management: submit, review, approve, reject workflow with SoD enforcement and review comments
- Crew Management: crew directory, duty time tracking, qualifications, FDTL validation, notification integration
- Maintenance Management page: frontend, backend CRUD, tests, E2E coverage

### Fixed
- `ver_id` indentation bug in `database.py` (lines 2612-2639) — duplicate `version_id` on seed

---

## [v0.8.0] — 2026-11-10

### Added
- Document file endpoints: `POST /documents/{doc_id}/file`, `GET /documents/{doc_id}/files`, `GET /documents/{doc_id}/file/{file_id}`
- ClamAV scanning, Pydantic validation, SHA-256 integrity verification for file uploads
- Backup and restore infrastructure with off-host backup server `10.20.173.120`
- Role-specific landing screens

---

## [v0.7.0] — 2026-11-09

### Added
- Document infrastructure: version lifecycle (`draft → in_review → approved → kcaa_approved → published`)
- Atomic change proposals with change detection and batching
- Separation of duties enforcement: change proposer cannot approve/reject/publish their own change
- RBAC matrix: 16 roles with explicit permission allow-lists

---

## [v0.6.0] — 2026-11-08

### Added
- Safety Management System: occurrences, hazards, missions, risk assessments, investigations, corrective actions
- MOR 72-hour clock calculation server-side (reporter cannot self-assess)
- Flight release gates: ROC/OpSpec enforcement, ≤400 ft AGL, no BVLOS/night, 7 OpSpec-listed registrations vs 20-aircraft master fleet
- Dangerous Goods acceptance: Division 6.2 scope validation, Appendix 3 checks

### Fixed
- Draft version creation no longer overwrites effective published content
- P0 Change Request status transitions now enforce review sequence and log audit events
- Distribution acknowledgements bound to named recipient
- QMS CAR/CAP: Level 1 (7d) / Level 2 (30d) timelines, CAP completeness gates, independent auditor verification

---

## [v0.5.0] — 2026-11-07

### Added
- Authentication: HTTP-only session cookies, CSRF double-submit, origin allow-listing
- Session lifecycle: login, logout, profile, active-role switching, bootstrap, password setup/reset
- User management: canonical accounts, role assignments, invite codes, setup tokens
- 16 role profiles with separation of duties

### Security
- Development identity headers disabled in production
- No JWT/OIDC implemented (explicitly not used)

---

<!-- Previous releases are tracked in git history. See `git log --oneline` for commit-level detail. -->
