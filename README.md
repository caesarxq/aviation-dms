# KFL Aviation DMS

Kenya Flying Labs — Aviation Document Management & ROC (Remotely Piloted Aircraft Operations) Compliance System.

A local-first, FastAPI + React document management system for aviation safety, compliance, fleet, and document control. Built for KCAA-regulated UAS operations under ROC No. 06.

## Architecture

```
aviation-dms/
├── backend/                 # FastAPI (Python 3.11) API
│   ├── app/
│   │   ├── main.py          # App entry, CORS, security headers, auth middleware
│   │   ├── p0_auth.py       # HTTP-only session auth, CSRF, dev-only identity headers
│   │   ├── p0_routes.py     # P0: documents, versions, content, change requests,
│   │   │                  # distributions, retention, legal holds, compliance,
│   │   │                  # audit events, evidence pack, admin observability,
│   │   │                  # auth profile
│   │   ├── p1_routes.py     # P1: occurrences, hazards, missions, ROC, safety KPIs,
│   │   │                  # deadlines, notifications
│   │   ├── p2_routes.py     # P2: document proposals (atomic, batched), annotations,
│   │   │                  # personnel licenses, aircraft insurance, self-service uploads
│   │   ├── proposal_engine.py  # Change detection + atomic proposal grouping
│   │   ├── rbac.py          # Role-based access control matrix (16 roles)
│   │   ├── audit.py         # Audit trail logging
│   │   ├── database.py      # SQLite schema, seed data, migrations
│   │   └── notifications.py # Deadline/ expiry notification scheduler
│   ├── data/                # SQLite DB + uploads (gitignored)
│   └── tests/               # pytest suite
├── frontend/                # React 18 + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── App.tsx          # Lazy-loaded routes (Suspense)
│   │   ├── api/client.ts    # Authenticated axios client (dev identity headers)
│   │   ├── auth/identity.ts # Dev identity profile (system_admin default)
│   │   ├── components/
│   │   │   ├── documents/   # DocumentOutline, InlineSuggestionView, DiffTable
│   │   │   ├── layout/      # AppShell (sidebar), Modal, Toast
│   │   │   └── ui/          # Base UI primitives
│   │   ├── pages/           # Route pages (Dashboard, DocumentEditor, etc.)
│   │   ├── test/            # Vitest setup
│   │   └── utils/           # diff.ts, inlineSuggestion
│   ├── e2e/                 # Playwright smoke and isolated mock-backed tests
│   ├── vitest.config.ts
│   └── tsconfig.json
├── docker-compose.yml       # HTTPS production stack; see docs/PRODUCTION-DEPLOYMENT.md
├── DESIGN.md                # Design system tokens (KFL brand)
└── .env.example             # Environment variable template
```

## Tech Stack

**Backend**
- FastAPI, Python 3.11, aiosqlite (SQLite)
- Opaque server-managed HTTP-only sessions with CSRF validation (JWT/OIDC is not implemented)
- pytest

**Frontend**
- React 18, TypeScript, Vite 6, Tailwind CSS
- @tanstack/react-query, React Router DOM v7, Lucide icons, DOMPurify
- Vitest (unit), Playwright (E2E)

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy the local-development environment template at the repository root.
cp ../.env.example ../.env
set -a; source ../.env; set +a

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check: `http://localhost:8000/health`

### Frontend

```bash
cd frontend
npm install
npm run dev          # Vite dev server on http://localhost:5173
npm run build        # Production build
npm test             # Vitest unit tests
npm run test:e2e     # Playwright E2E smoke tests
```

The frontend proxies `/api` to `http://localhost:8000` in dev.

**E2E safety:** `npm run test:e2e` is mutating: the smoke suite creates and updates backend records. Run it only with a disposable, seeded local database selected by `DMS_DB_PATH` and dedicated test-only accounts/credentials (`KFL_E2E_USER` and `KFL_E2E_PASSWORD`). Because Vite proxies API requests to `localhost:8000`, do not run this suite while that backend is connected to staging, production, or user data. If the target cannot be proven disposable, do not run the E2E suite.

### Docker

Local development should use the backend and Vite commands above. The root `docker-compose.yml` is a production-shaped HTTPS deployment and intentionally requires a hostname, SMTP configuration, and a mounted bootstrap-token file; it will not start with development defaults. Follow [`docs/PRODUCTION-DEPLOYMENT.md`](docs/PRODUCTION-DEPLOYMENT.md) for staging/production setup and release gates.

## Authentication & RBAC

### Development mode (`DEV_MODE=true`)

Identity is supplied via request headers:
- `X-Role` — one of the 16 known roles
- `X-Actor` — a canonical or retained legacy user ID (e.g. `u-admin`, `u-quality`, `u-safety/security`)

Invalid or unknown actor/role pairs return `401`.

### Production mode (`DEV_MODE=false`)

Production API requests use an opaque, server-managed HTTP-only session cookie and a separate CSRF cookie/header pair. Mutations require an allowed HTTPS Origin. Session roles are loaded from the server-side assignments and active-role context. Development identity headers are disabled in production. Bearer JWT/OIDC validation is not implemented; do not configure or advertise those unused settings as an authentication method.

### Role profiles (16 roles)

| Role | Access | Key capabilities |
|------|--------|------------------|
| `system_admin` | L4 | Broad administration and audit import; cannot verify provenance |
| `accountable_manager` | L4 | Organization overview, approve/publish |
| `head_quality` | L3 | Document approve/publish, QA, audits |
| `head_safety` | L3 | Safety SMS, occurrences, investigations |
| `head_security` | L3 | Security records, audit read |
| `head_operations` | L3 | ROC/fleet, missions, personnel ops |
| `head_training` | L3 | Training program, personnel manage |
| `head_maintenance` | L3 | Maintenance, aircraft manage |
| `librarian` | L2 | Document create/update/propose, distribution |
| `chief_pilot` | L2 | Flight ops, safety read |
| `flight_ops_officer` | L2 | Missions, safety read |
| `dg_coordinator` | L2 | Dangerous goods, safety read |
| `records_custodian` | L2 | Retention, legal holds |
| `independent_auditor` | L2 | Audit/compliance read and narrow source-provenance verification |
| `occurrence_reporter` | L1 | Safety read and occurrence reporting |
| `as_contracted` | L1 | Baseline read-only access; contract-specific scope is assigned separately |

Separation of duties: a change proposer cannot approve/reject/publish their own change.

New users should follow the [User Onboarding Procedure](docs/USER-ONBOARDING-PROCEDURE.md). Administrators should use the [Onboarding Runbook](docs/ONBOARDING-RUNBOOK.md) for roster reconciliation and controlled invitations.

## Document Control Workflow

### Version lifecycle

`draft → in_review → {approved → kcaa_approved → published}` with `rejected` as an exit at most stages.

- `draft → in_review`: librarian (document:update)
- `in_review → approved`: an authorized `document:approve` role; creator cannot approve
- `approved → kcaa_approved`: `document:approve` after a retained evidence PDF is independently verified; uploader, verifier, and KCAA approver must be distinct
- `kcaa_approved → published`: an authorized `document:publish` role; creator cannot publish and the verified evidence file/hash is rechecked
- KCAA gate: documents requiring KCAA approval cannot be published without a retained PDF evidence artifact whose SHA-256 is computed server-side, verified by a separate `document:approve` principal, and linked to the exact version. This records internal evidence review; it is not an automated validation against KCAA systems.

### Atomic change proposals

When a user edits a document, the system detects changes and groups them into reviewable proposals:

1. **Preview** (`POST /api/p2/documents/{doc_id}/proposals/preview`) — detect changes without persisting
2. **Batch submit** (`POST /api/p2/documents/{doc_id}/proposals/batch`) — creates one proposal per detected change
3. **Review** — quality head approves/rejects (SoD enforced)
4. **Apply** — system_admin applies an approved proposal as a new draft version

Change grouping heuristics:
- Changes within 8 tokens, ≥25% density, or ≥10 changed tokens are merged into one proposal
- Changes across paragraph/section boundaries are never merged
- Proposal types: `word`, `phrase`, `paragraph`, `section`
- Change fingerprint deduplicates repeated submissions

### Proposal fields

Each proposal stores: `target_ref` (e.g. `§4.2 — Emergency Procedures · paragraph 1`), `section_number`, `section_heading`, `block_type`, `block_index`, `anchor_id`, `original_text`, `proposed_text`, sanitized `original_excerpt_html` / `proposed_excerpt_html`, `context_before` / `context_after`, `changed_token_count`, `change_density`, `grouping_reason`, `change_fingerprint`.

Raw HTML is never exposed in proposal views — only sanitized, focused excerpts.

## API Endpoints

### P0 — Document Control
```
GET    /api/p0/auth/profile                 # Authenticated user profile
GET    /api/p0/admin/observability          # System health, tables, users, role matrix (admin)
GET    /api/p0/documents                    # List documents
POST   /api/p0/documents                    # Create document
GET    /api/p0/documents/{id}               # Get document
PATCH  /api/p0/documents/{id}               # Update document
GET    /api/p0/documents/{id}/content       # Get latest version content
PUT    /api/p0/documents/{id}/content       # Save content as new draft version
POST   /api/p0/versions                     # Create version
PATCH  /api/p0/versions/{id}/state          # State transition (draft→in_review→approved→kcaa_approved→published)
GET    /api/p0/versions                     # List versions
GET    /api/p0/change-requests              # List change requests
POST   /api/p0/change-requests              # Create change request
PATCH  /api/p0/change-requests/{id}         # Review/approve/reject (SoD enforced)
GET    /api/p0/distributions                # List distributions
POST   /api/p0/distributions                # Create distribution
POST   /api/p0/distributions/{id}/acknowledge
GET    /api/p0/retention-rules
GET    /api/p0/legal-holds                  # List legal holds
POST   /api/p0/legal-holds                  # Create legal hold
PATCH  /api/p0/legal-holds/{id}/release
GET    /api/p0/compliance-obligations
GET    /api/p0/regulatory-references
GET    /api/p0/audit-events                 # Audit trail
POST   /api/p0/evidence-pack                # SHA-256 signed evidence pack
```

### P1 — Safety & Operations
```
GET/POST   /api/p1/occurrences              # Safety occurrences (confidential reporter masking)
PATCH      /api/p1/occurrences/{id}         # Update occurrence
POST       /api/p1/occurrences/{id}/acknowledge
GET/POST   /api/p1/hazards                  # Hazard register
GET/POST   /api/p1/missions                 # Missions (license/insurance eligibility hard-block)
PATCH      /api/p1/missions/{id}/state      # Mission state machine
GET        /api/p1/safety-kpis
GET        /api/p1/deadlines                # Upcoming/overdue deadlines
GET        /api/p1/notifications            # Notifications
```

### P2 — Document Proposals, Licenses, Insurance
```
POST   /api/p2/documents/{id}/proposals/preview    # Detect changes (no persist)
POST   /api/p2/documents/{id}/proposals/batch      # Create batched proposals
GET    /api/p2/documents/{id}/proposals
PATCH  /api/p2/proposals/{id}                      # Submit/approve/reject/defer
DELETE /api/p2/proposals/{id}
POST   /api/p2/proposals/{id}/apply                # Apply approved proposal
GET/POST /api/p2/documents/{id}/annotations
PATCH  /api/p2/annotations/{id}
DELETE /api/p2/annotations/{id}
POST   /api/p2/personnel/licenses                  # Personnel licenses + expiry tracking
GET    /api/p2/personnel/licenses                  # With expiring filter
GET    /api/p2/personnel/expiring-licenses
POST   /api/p2/aircraft/{id}/insurance             # Aircraft insurance + expiry tracking
GET    /api/p2/aircraft/{id}/insurance
GET    /api/p2/insurance/expiring
POST   /api/p2/personnel/uploads/file              # Private multipart credential upload
GET    /api/p2/personnel/uploads/{person_id}       # Paginated own uploads/staff view; status, limit, offset
GET    /api/p2/personnel/uploads                   # Staff verification queue
GET    /api/p2/personnel/uploads/{id}/file         # Authenticated private download
PATCH  /api/p2/personnel/uploads/{id}/verify       # Independent verify/reject decision
```

## Database

SQLite at `backend/data/dms.db`. Schema includes:
- `users` / `user_roles` / `user_id_aliases` — 15 seeded role profiles consolidate to 8 canonical active accounts with 15 assigned roles; legacy IDs and audit references are retained
- `auth_sessions` — opaque, revocable sessions with a server-stored active role
- `documents` / `document_versions` — controlled documents with KCAA gates
- `document_proposals` — atomic change proposals
- `change_requests` — formal change requests with SoD
- `audit_events` — immutable audit trail
- `personnel_licenses` / `license_renewal_history` — license expiry tracking
- `personnel_uploads` — private credential file metadata, SHA-256 integrity, and independent review status
- `aircraft_insurance` / `insurance_renewal_history` — insurance expiry tracking
- `notifications` — deadline/expiry notifications

## Multi-role identity and session roles

- One verified individual maps to one canonical `user_id`; all assigned roles are stored in `user_roles`.
- Each browser session stores an `active_role`. The profile and API permissions are scoped to that role; users can switch only among roles assigned to their canonical account.
- Administrators can inspect canonical users at `GET /api/p0/auth/users` and replace role assignments with `PUT /api/p0/auth/users/{user_id}/roles`. Role changes are audited and revoke the target account's active sessions.
- Historical account IDs and former usernames map through `user_id_aliases` for audit and SoD resolution; merged usernames cannot authenticate. Duplicate user rows remain inactive with `merged_into_user_id`; business and audit records are not rewritten.
- Startup consolidation is keyed by owner-verified immutable IDs, not names. It refuses to merge accounts with conflicting password hashes rather than choosing a credential.

## Testing

```bash
# Backend
(cd backend && python -m pytest -q)

# Frontend
(cd frontend && npm test)       # Vitest unit tests
(cd frontend && npm run test:e2e) # Playwright E2E smoke tests
(cd frontend && npm run build)  # TypeScript + Vite production build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_MODE` | local template: `true` | Development-only identity-header fallback; production must set `false` |
| `DMS_DB_PATH` | backend `data/dms.db` locally | SQLite database path |
| `SESSION_COOKIE_SECURE` | secure when `DEV_MODE=false` | Production must keep `true` and use HTTPS |
| `AUTH_ALLOWED_ORIGINS` | localhost only in local dev | Exact browser origins permitted for session requests |
| `PUBLIC_APP_URL` | localhost in local dev | HTTPS base URL used for password-reset links |
| `KFL_BOOTSTRAP_TOKEN_FILE` | unset locally | Protected file containing the one-time production bootstrap token |
| `UPLOAD_DIR` | `data/uploads` | Multipart upload storage |
| `FLIGHT_RELEASE_ENABLED` | `false` | Disabled until source-to-rule mapping and postholder validation are complete |
| `SMTP_*` | unset in local dev | Required production email/reset delivery settings |
| `NOTIFICATION_ENABLED` | `false` locally | Enables configured email notifications |

See `.env.example` for the full template.

## Design System

`DESIGN.md` defines KFL brand tokens: brand blue `#1B7ABF`, deep aviation navy `#0B2942`, canvas gray, semantic status colors, and component specifications. Implemented via Tailwind CSS and custom CSS variables.

Form UX, accessibility, and mutation-testing guidance is documented in [`docs/FORM-UX-AND-QUALITY-PLAN.md`](docs/FORM-UX-AND-QUALITY-PLAN.md).

## Security

- Production Compose uses HTTPS termination, HSTS and response security headers; local development uses localhost-only origins.
- Browser authentication uses server-managed HTTP-only sessions, CSRF validation and explicit server-side role permissions; development identity headers are disabled in production.
- Stored manual HTML is rendered in a script-disabled sandbox with a restrictive document CSP. The editor sanitizes untrusted pasted/proposed markup; direct draft saves are disabled for high-fidelity manuals when the editor would lose source layout.
- Upload handling binds self-service access to the authenticated user, restricts filesystem paths, checks file signatures and enforces a size limit.
- Production secrets are supplied through protected configuration or mounted secret files; no shared test password is embedded in the data seeder or E2E suite.
- Audit events are recorded for controlled workflow operations; verify event coverage for every new state-changing endpoint before release.
- Security and operational gates do not establish regulatory approval; use the release controls in [`docs/PRODUCTION-DEPLOYMENT.md`](docs/PRODUCTION-DEPLOYMENT.md).

## License

Internal KFL Aviation DMS — operational use only.