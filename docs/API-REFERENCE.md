# KFL Aviation DMS — API Reference

## Authentication

All API routes are prefixed with `/api/p0`, `/api/p1`, `/api/p2`, or `/api/p3`. Authentication is **session-cookie based** (HTTP-only `__Host-kfl_session` + `__Host-kfl_csrf` CSRF pair). JWT/Bearer authentication is **not implemented** in this release.

### Session lifecycle

| Endpoint | Method | Description | Auth |
|---|---|---|---|
| `/api/p0/auth/login` | POST | Authenticate with username/password; establishes session cookie | Public |
| `/api/p0/auth/logout` | POST | Revoke current session and clear cookies | Session cookie |
| `/api/p0/auth/profile` | GET | Return canonical identity, roles, active role, and permissions | Session cookie |
| `/api/p0/auth/active-role` | POST | Switch session to one of the user's assigned roles | Session cookie |
| `/api/p0/auth/bootstrap-status` | GET | Check if bootstrap is required | Public |
| `/api/p0/auth/bootstrap` | POST | First-time bootstrap (DEV_MODE loopback only) | Public (loopback) |
| `/api/p0/auth/password-setup` | POST | Set initial password via setup token or invite code | Public |
| `/api/p0/auth/forgot-password` | POST | Request password reset token (generic response, no enumeration) | Public |
| `/api/p0/auth/reset-password` | POST | Reset password via reset token | Public |
| `/api/p0/auth/me/onboarding` | GET | Check onboarding completion status | Session cookie |
| `/api/p0/auth/me/onboarding/complete` | POST | Mark onboarding as complete | Session cookie |

### User management (admin)

| Endpoint | Method | Description | Auth |
|---|---|---|---|
| `/api/p0/auth/users` | GET | List canonical active accounts with roles and password status | `settings:manage` |
| `/api/p0/auth/users/{user_id}/roles` | PUT | Replace a user's role assignments; revokes active sessions | `settings:manage` |
| `/api/p0/auth/users/{user_id}/setup-token` | POST | Issue a one-time password setup token for an active canonical account | `settings:manage` |
| `/api/p0/auth/invites` | POST | Issue a one-time invite code (max 5 per actor per 15 min) | `settings:manage` |

For the literal canonical ID `u-safety/security`, URL-encode the slash as `%2F` in `{user_id}` path segments (for example, `/api/p0/auth/users/u-safety%2Fsecurity/roles`). API profile payloads retain the exact canonical ID. Owner-confirmed legacy IDs continue to resolve through the account-alias table for role administration, setup-token issuance, and personnel upload/license ownership and filtering.

## P1 — Safety Management

| Endpoint | Method | Description | Auth |
|---|---|---|---|
| `/api/p1/hazards` | GET | List hazards (filter by status, risk_level) | `safety:read` |
| `/api/p1/hazards` | POST | Create a new hazard | `safety:create` |
| `/api/p1/hazards/{hazard_id}` | PATCH | Update a hazard | `safety:update` |
| `/api/p1/risk-assessments` | GET | List risk assessments (supports multiple hazards per assessment) | `safety:read` |
| `/api/p1/risk-assessments` | POST | Create a risk assessment linked to one or more hazards | `safety:create` |
| `/api/p1/risk-assessments/{assessment_id}` | PATCH | Update a risk assessment (replace hazard links via `hazard_ids`) | `safety:update` |
| `/api/p1/occurrences` | GET/POST | List/create safety occurrences | `safety:read`/`safety:create` |
| `/api/p1/occurrences/{occ_id}` | PATCH | Update an occurrence | `safety:update` |
| `/api/p1/occurrences/{occ_id}/acknowledge` | POST | Acknowledge an occurrence | `safety:update` |
| `/api/p1/occurrences/{occ_id}/close` | POST | Close an occurrence (requires effectiveness confirmation) | `safety:close` |
| `/api/p1/investigations` | GET/POST | List/create investigations | `safety:update` |
| `/api/p1/investigations/{inv_id}` | PATCH | Update an investigation | `safety:update` |
| `/api/p1/safety-actions` | GET/POST | List/create safety corrective actions | `safety:read`/`safety:create` |
| `/api/p1/safety-actions/{action_id}` | PATCH | Update a safety action | `safety:update` |
| `/api/p1/safety/trends` | GET | Safety trend analytics | `safety:read` |

## P2 — Operations

| Endpoint | Method | Description | Auth |
|---|---|---|---|
| `/api/p2/missions` | GET/POST | List/create missions | `safety:read`/`safety:create` |
| `/api/p2/missions/{mission_id}` | PATCH | Update a mission | `safety:update` |
| `/api/p2/flight-plans` | GET/POST | List/create flight plans | `roc:read`/`roc:manage` |
| `/api/p2/flight-releases` | GET/POST | List/create flight releases (requires `flight:release`) | `flight:release` |
| `/api/p2/crew-members` | GET/POST | List/create crew members | `personnel:read`/`personnel:manage` |
| `/api/p2/duty-records` | GET/POST | List/create duty time records | `personnel:read`/`personnel:manage` |
| `/api/p2/crew-qualifications` | GET/POST | List/create crew qualifications | `personnel:read`/`personnel:manage` |
| `/api/p2/personnel/uploads/file` | POST | Upload a private credential file via multipart form data | `personnel:view`; `personnel:manage` is also required when uploading for another person |
| `/api/p2/personnel/uploads/{person_id}` | GET | List a person's uploads; slash-containing canonical IDs must encode `/` as `%2F` | `personnel:view` (self) or `personnel:read`/`personnel:manage` |
| `/api/p2/personnel/uploads` | GET | List the staff verification queue (filter by status, limit, offset) | `personnel:read`/`personnel:manage` |
| `/api/p2/personnel/uploads/{upload_id}/file` | GET | Download a private uploaded credential file | `personnel:view` (self) or `personnel:read`/`personnel:manage` |
| `/api/p2/personnel/uploads/{upload_id}/verify` | PATCH | Independently verify or reject a pending upload | `personnel:manage` |
| `/api/p2/maintenance-records` | GET/POST | List/create maintenance records | `aircraft:read`/`aircraft:manage` |
| `/api/p2/aircraft-insurance` | GET/POST | List/create aircraft insurance records | `aircraft:read`/`aircraft:manage` |

## P3 — Audit reports and provenance

| Endpoint | Method | Description | Auth |
|---|---|---|---|
| `/api/p3/audit-reports` | GET | List audit reports; supports `status`, literal `search`, `limit` (1–100), and `offset`; deterministic order is audit date descending then ID ascending | `audit_report:read` |
| `/api/p3/audit-reports` | POST | Create an in-app report; assigned auditor must be an active independent auditor | `audit_report:create` |
| `/api/p3/audit-reports/{audit_id}/evidence` | GET | Download a hash-checked report evidence PDF | `audit_report:read` |
| `/api/p3/audit-findings` | GET/POST | List/create findings | `audit_finding:read`/`audit_finding:create` |
| `/api/p3/audit-findings/{finding_id}` | GET/PATCH | Read/update a finding | `audit_finding:read`/`audit_finding:update` |
| `/api/p3/audit-findings/{finding_id}/car` | POST | Create a corrective action from a finding | `audit_finding:update` |
| `/api/p3/audit-findings/summary` | GET | Finding summary | `audit_finding:read` |
| `/api/p3/audit-report-imports` | POST | Stage a historical report and findings; creates no live report or findings | `audit_report:import` (`system_admin` only) |
| `/api/p3/audit-report-imports` | GET | List staged/imported/rejected candidates (filter by status, limit, offset) | `audit_report:import` or `audit_report:provenance_verify` |
| `/api/p3/audit-report-imports/{import_id}` | GET | Read candidate metadata, source identity, hashes, and findings | `audit_report:import` or `audit_report:provenance_verify` |
| `/api/p3/audit-report-imports/{import_id}/evidence` | GET | Download the source PDF after hash verification | `audit_report:import` or `audit_report:provenance_verify` |
| `/api/p3/audit-report-imports/{import_id}/verify` | POST | Recheck stored hashes and atomically publish report/findings after independent attestation | `audit_report:provenance_verify` (`independent_auditor` only) |
| `/api/p3/audit-report-imports/{import_id}/reject` | POST | Reject a pending import with a recorded reason | `audit_report:provenance_verify` (`independent_auditor` only) |

The import candidate must include the literal source auditor ID/name, a source PDF checksum, report metadata, and all findings. The server recomputes and stores a canonical payload hash; verification compares the date, scope, regulatory basis, identities, evidence reference/digest, and other duplicated report fields against that hashed payload. The source auditor, auditee, import operator, and verifier must be distinct principals; alias-aware checks enforce separation. Only the independent verifier can finalize the import; after evidence validation, one short transaction re-reads and checks candidate state/digest before atomically creating report/finding rows and finalizing the import. A verified checksum and verifier attestation do not by themselves prove the source's authenticity; the verifier must compare the source PDF and every finding against the controlled source. No historical audit has been imported by this workflow yet.

- `POST /api/p3/audit-reports` is for in-app current/future audit records. If `audit_date` is earlier than the current UTC date, it returns 422 and requires the historical provenance-import workflow instead.
- `POST /api/p3/audit-report-imports` accepts `audit_number`, `audit_date`, `source_auditor_id`, `source_auditor_name`, `auditee_id`, optional `scope`/`regulatory_basis`, `evidence_file`, lowercase `expected_evidence_sha256`, and a `findings` array. The PDF must already be retained under the application `attachments/` evidence root; this API does not upload files. Before use, evidence must pass the explicit `DMS_AUDIT_EVIDENCE_MAX_BYTES` limit, shared quota/scanner configuration, malware screening, and bounded validator-service PDF parsing; the endpoint returns a service-unavailable error if required safeguards are unconfigured.
- P3 mutations are admitted by ASGI before Pydantic parses the body. Non-import mutation bodies are capped at 128 KiB; import creation additionally requires a positive `DMS_P3_IMPORT_BODY_MAX_BYTES`, which defaults empty in Compose and keeps that endpoint fail-closed until explicitly configured. Reverse-proxy limits and worker-count memory budgets still require deployment validation.
- `POST /api/p3/audit-report-imports/{import_id}/verify` requires `source_checksum_confirmed`, `findings_reconciled`, and at least 20 characters of `verification_notes` from a different active independent-auditor principal.
- `POST /api/p3/audit-report-imports/{import_id}/reject` accepts a `reason` and records the independent auditor's rejection. Rejected candidates publish no report or findings and may be resubmitted for review.
- The browser staging and review controls are on `/audit-reports`, gated by `audit_report:import` and `audit_report:provenance_verify`. The PDF must already be retained under `attachments/`; the UI does not upload files. The workflow is implemented locally, not deployed. Compose defaults the evidence-size limit and scanner/quota settings to empty, so the file-reference endpoints remain fail-closed until approved configuration is supplied.

## Role-Based Access Control

16 roles are defined with explicit permission allow-lists. Unknown roles receive no permissions.

| Role | Access Level | Key Permissions |
|---|---|---|
| system_admin | L4 | Broad administration and import; no provenance verification |
| accountable_manager | L4 | Approve, publish, flight release, security manage |
| head_quality | L3 | Document approve/publish, audit manage, safety close |
| head_safety | L3 | Safety create/update/close, occurrence investigate |
| head_security | L3 | Security manage, sensitive read |
| head_operations | L3 | Flight release, ROC manage, aircraft manage |
| head_training | L3 | Personnel manage |
| head_maintenance | L3 | Aircraft manage, safety create |
| librarian | L2 | Document create/update, distribution manage |
| chief_pilot | L2 | Flight release, safety create |
| flight_ops_officer | L2 | Safety create |
| dg_coordinator | L2 | Safety create |
| records_custodian | L2 | Retention/legal hold manage |
| independent_auditor | L2 | Audit read and narrow source-provenance verification; safety read only |
| occurrence_reporter | L1 | Occurrence report, safety create |
| as_contracted | L1 | Read-only (document, safety, roc, aircraft) |

### Separation of Duties

- **change_request**: The proposer cannot approve, reject, or publish their own change request.
- **version**: The proposer cannot approve or publish their own document version.

These rules are grounded in ICAO Annex 19 SMS §2.6 and KCAA SMS regulations.

## Session Security

- Session cookies are HTTP-only, SameSite=Strict, secure in production
- CSRF double-submit token required on all state-changing requests
- Origin allow-listing via `CORS_ORIGINS` environment variable
- Session expiry uses a sliding `SESSION_TTL_SECONDS` (default 8 hours) capped by `SESSION_ABSOLUTE_MAX_SECONDS` (default 24 hours); requests cannot extend a session beyond the absolute maximum age.
- Sessions are revoked on logout, role change, and user role assignment changes
- Failed attempt rate limiting: 5 failures per 15-minute window triggers 15-minute lockout
