# KFL Aviation DMS

Kenya Flying Labs — Aviation Document Management & ROC (Remotely Piloted Aircraft Operations) Compliance System.

A local-first, FastAPI + React document management system for aviation safety, compliance, fleet, and document control. Built for KCAA-regulated UAS operations under ROC No. 06.

## Architecture

```
aviation-dms/
├── backend/                 # FastAPI (Python 3.11) API
│   ├── app/
│   │   ├── main.py          # App entry, CORS, security headers, auth middleware
│   │   ├── p0_auth.py       # JWT validation (production) / dev identity (development)
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
│   └── tests/               # pytest suite (80 tests)
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
│   ├── e2e/                 # Playwright smoke tests (14 tests)
│   ├── vitest.config.ts
│   └── tsconfig.json
├── docker-compose.yml       # Backend, frontend, Keycloak
├── DESIGN.md                # Design system tokens (KFL brand)
└── .env.example             # Environment variable template
```

## Tech Stack

**Backend**
- FastAPI, Python 3.11, aiosqlite (SQLite)
- python-jose (JWT validation)
- pytest (80 tests)

**Frontend**
- React 18, TypeScript, Vite, Tailwind CSS
- @tanstack/react-query, React Router DOM, Lucide icons, DOMPurify
- Vitest (unit), Playwright (E2E)

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # or install deps manually: fastapi uvicorn aiosqlite python-jose python-multipart

# Copy env template
cp ../.env.example .env
# Edit DEV_MODE=true for local development (header-based auth)

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
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

### Docker

```bash
docker compose up --build
```

Services: backend (8000), frontend (80), Keycloak (8080).

## Authentication & RBAC

### Development mode (`DEV_MODE=true`)

Identity is supplied via request headers:
- `X-Role` — one of the 16 known roles
- `X-Actor` — the seeded user ID (e.g. `u-admin`, `u-quality`, `u-safety`)

Invalid or unknown actor/role pairs return `401`.

### Production mode (`DEV_MODE=false`)

Bearer JWT validation via `python-jose`. Required claims: `sub`, `role`, `aud`, `iss`. Tokens must be signed with `JWT_SECRET` using `JWT_ALGORITHM` (HS256).

### Role profiles (16 roles)

| Role | Access | Key capabilities |
|------|--------|------------------|
| `system_admin` | L4 | All permissions, observability |
| `accountable_manager` | L4 | Executive oversight, approve/publish |
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
| `independent_auditor` | L2 | Audit/compliance read |
| `occurrence_reporter` | L1 | Occurrence reporting only |
| `as_contracted` | L1 | Read-only operational/safety info |

Separation of duties: a change proposer cannot approve/reject/publish their own change.

## Document Control Workflow

### Version lifecycle

`draft → in_review → {approved → kcaa_approved → published}` with `rejected` as an exit at most stages.

- `draft → in_review`: librarian (document:update)
- `in_review → approved`: head_quality (document:approve)
- `approved → kcaa_approved`: system_admin (KCAA gate)
- `kcaa_approved → published`: system_admin (document:publish, SoD: creator cannot publish)
- KCAA gate: documents requiring KCAA approval cannot be published without `kcaa_approved`

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
POST   /api/p2/personnel/uploads/file              # Multipart file upload
PATCH  /api/p2/personnel/uploads/{id}/verify       # Verify/reject upload
```

## Database

SQLite at `backend/data/dms.db`. Schema includes:
- `users` / `user_roles` — 16 seeded profiles
- `documents` / `document_versions` — controlled documents with KCAA gates
- `document_proposals` — atomic change proposals
- `change_requests` — formal change requests with SoD
- `audit_events` — immutable audit trail
- `personnel_licenses` / `license_renewal_history` — license expiry tracking
- `aircraft_insurance` / `insurance_renewal_history` — insurance expiry tracking
- `notifications` — deadline/expiry notifications

## Testing

```bash
# Backend
cd backend
python -m pytest -q          # 80 tests

# Frontend
cd frontend
npm test                     # Vitest unit tests (14 tests)
npm run test:e2e             # Playwright E2E smoke tests (14 tests)
npm run build                # TypeScript + Vite production build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_MODE` | `false` | Header-based auth when true |
| `DMS_DB_PATH` | `data/dms.db` | SQLite database path |
| `JWT_SECRET` | `change-me...` | Production JWT signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_AUDIENCE` | `kfl-aviation-dms` | JWT audience claim |
| `JWT_ISSUER` | `kfl-aviation-dms` | JWT issuer claim |
| `UPLOAD_DIR` | `data/uploads` | Multipart upload storage |
| `SMTP_*` | — | Email notification config |
| `NOTIFICATION_ENABLED` | `false` | Enable email notifications |

See `.env.example` for the full template.

## Design System

`DESIGN.md` defines KFL brand tokens: brand blue `#1B7ABF`, deep aviation navy `#0B2942`, canvas gray, semantic status colors, and component specifications. Implemented via Tailwind CSS and custom CSS variables.

Form UX, accessibility, and mutation-testing guidance is documented in [`docs/FORM-UX-AND-QUALITY-PLAN.md`](docs/FORM-UX-AND-QUALITY-PLAN.md).

## Security

- Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, Referrer-Policy headers
- CORS restricted to `http://localhost:5173` in dev
- DOMPurify sanitization for all rendered document HTML
- Role-based access control with separation of duties
- No hardcoded credentials; all secrets via environment variables
- Audit events logged for all state-changing operations

## License

Internal KFL Aviation DMS — operational use only.