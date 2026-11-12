# Aviation DMS — Decision Log

**Purpose:** Lightweight record of operational and technical decisions made during development and deployment. ADRs (Architecture Decision Records) live in `docs/adr/`; this log captures day-to-day decisions that don't warrant a full ADR.

**Format:** Date | Decision | Owner | Rationale | Status

---

## 2026-11-12

| Date | Decision | Owner | Rationale | Status |
|------|----------|-------|-----------|--------|
| 2026-11-12 | Removed Terraform infrastructure (`terraform/`) and all related references | Backend/IT | Terraform OCI provisioning not applied; production instance created manually; Terraform files contained uncommitted OCIDs and were no longer useful | Complete |
| 2026-11-12 | Changed staging ports: backend 8000→8001, frontend 8080→8081 | Backend/IT | Persistent port conflicts on staging instance `10.20.4.234` from dead `docker-proxy` processes; localhost-only binding avoids conflicts | Complete |
| 2026-11-12 | Deployed production on dedicated OCI instance `10.20.1.69` | Backend/IT | Production containers were incorrectly deployed on bastion and staging; user directed correction to dedicated production instance | Complete |
| 2026-11-12 | Deployed staging on `10.20.4.234` after Docker restart | Backend/IT | Docker restart freed ports 8000/8080 held by dead `docker-proxy` processes | Complete |
| 2026-11-12 | Reloaded Caddy on bastion `145.241.152.126` | Backend/IT | Activated `roc.kfl.ke` → production proxy via HTTPS | Complete |
| 2026-11-12 | Fixed `database.py` indentation: `ver_id` block inside `for d in docs:` loop | Backend/IT | `UNIQUE constraint failed: document_versions.version_id` on seed; block was incorrectly inside `for c in classifications:` | Complete |

## 2026-11-11

| Date | Decision | Owner | Rationale | Status |
|------|----------|-------|-----------|--------|
| 2026-11-11 | Production and staging separated: staging on `10.20.4.234` (dev mode, 1 GB quota), production on OCI `10.20.1.69` (strict security, 30 GB quota) | Backend/IT + User | Clear environment boundaries; production handles operational records | Complete |
| 2026-11-11 | `https_proxy` removed from target compose — Caddy TLS termination on bastion only | Backend/IT | `https_proxy` service block caused compose failure on target (no Caddy on target) | Complete |
| 2026-11-11 | Data volumes separated: staging and production use independent `dms_data` volumes | Backend/IT | Prevent cross-environment data exposure | Complete |
| 2026-11-11 | `CONTROLLED_DOCUMENT_SECURITY_ENABLED` feature flag for code deploy without feature activation | Backend/IT | Allows code deployment without activating unapproved features | Complete |
| 2026-11-11 | Fail-closed deployment scripts: exit non-zero on error; nothing deleted from live systems | Backend/IT | Prevent accidental data loss during deployment | Complete |
| 2026-11-11 | Manual approval gate required before production promotion | User | Production promotion requires explicit authorization | Complete |
| 2026-11-11 | Flight release disabled (`FLIGHT_RELEASE_ENABLED=false`) | User | Pending accountable postholder sign-off on source-to-rule mapping | Complete |

## 2026-11-10

| Date | Decision | Owner | Rationale | Status |
|------|----------|-------|-----------|--------|
| 2026-11-10 | Upload-validator isolation: UID 10002, read-only FS, cap_drop ALL, no-new-privileges, 768 MiB, 1 CPU, 32 PIDs, no host port | Backend/IT | Defense in depth for file upload processing | Complete |
| 2026-11-10 | ClamAV INSTREAM scanning with 7-second deadline | Backend/IT | Fail-closed malware detection without external API dependency | Complete |
| 2026-11-10 | File upload/download with SHA-256 integrity verification | Backend/IT | File integrity from scan time to download | Complete |

## 2026-11-09

| Date | Decision | Owner | Rationale | Status |
|------|----------|-------|-----------|--------|
| 2026-11-09 | Document version lifecycle: `draft → in_review → approved → kcaa_approved → published` | User | KCAA-regulated document control with approval gates | Complete |
| 2026-11-09 | Separation of duties: change proposer cannot approve/reject/publish own change | User | ICAO Annex 19 SMS §2.6 and KCAA SMS regulations | Complete |
| 2026-11-09 | 16 role RBAC matrix with explicit permission allow-lists | User | Role-based access control for aviation compliance | Complete |
| 2026-11-09 | No JWT/OIDC authentication — server-managed sessions only | Backend/IT | Simplicity, server-side revocation, reduced attack surface | Complete |

## Open Decisions (Pending)

| Date | Decision Needed | Owner | Rationale | Status |
|------|-----------------|-------|-----------|--------|
| — | RPO/RTO targets for disaster recovery | Accountable Manager | Required before operational go/no-go | Pending |
| — | Off-host restore drill approval | Accountable Manager | Required before operational go/no-go | Pending |
| — | DG Appendix 3 source-manual mapping | Responsible Postholders | Source-manual reconciliation | Pending |
| — | Reverse-proxy body limits under load validation | Backend/IT | Production readiness | Pending |
| — | Local missing/unmatched file classification | Records Custodian | Disposition approval | Pending |
