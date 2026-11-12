# Contributing to KFL Aviation DMS

## Overview

KFL Aviation DMS is a FastAPI + React document management system for KCAA-regulated UAS operations. This project follows **TDD (Test-Driven Development)** with explicit context passing between agents in multi-agent pipelines.

**Security Rule (verbatim):** Never request, accept, or disclose passwords, tokens, private keys, credentials, or secrets.

---

## Getting Started

### Prerequisites
- Python 3.11
- Node.js 18+ and npm
- Docker and Docker Compose (for deployment)
- OCI CLI (for production infrastructure)

### Backend Setup

```bash
cd /Users/mohamedalsayed/Projects/aviation-dms/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy the local-development environment template
cp ../.env.example ../.env
set -a; source ../.env; set +a

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check: `http://localhost:8000/health`

### Frontend Setup

```bash
cd /Users/mohamedalsayed/Projects/aviation-dms/frontend
npm install
npm run dev          # Vite dev server on http://localhost:5173
npm run build        # Production build
npm test             # Vitest unit tests
npm run test:e2e     # Playwright E2E smoke tests
```

---

## Development Workflow (TDD)

This project enforces **RED → GREEN → REFACTOR**:

1. **RED**: Write a failing test that defines the desired behavior
2. **GREEN**: Write the minimum code to make the test pass
3. **REFACTOR**: Improve code quality while keeping tests passing

### Test Commands

```bash
# Backend (pytest)
cd backend
python -m pytest -q

# Frontend (Vitest)
cd frontend
npm test

# Frontend E2E (Playwright)
cd frontend
npm run test:e2e
```

**E2E Safety:** The E2E suite is mutating — it creates and updates backend records. Run it only with a disposable, seeded local database selected by `DMS_DB_PATH` and dedicated test-only accounts (`KFL_E2E_USER` and `KFL_E2E_PASSWORD`). Do not run E2E against staging, production, or user data.

---

## Code Standards

### Python (Backend)
- Pydantic v2 (use `.model_dump()`, not `.dict()`)
- No `print()` statements in production code
- Type hints on all public functions
- Docstrings for public APIs
- Async/await for I/O-bound operations (`aiosqlite`, `httpx`)
- Fail-closed: missing configuration → HTTP 503, not silent failure

### TypeScript (Frontend)
- Strict TypeScript (`tsc` with 0 errors)
- React 18 + TanStack Query + React Router DOM v7
- DOMPurify for HTML sanitization before DOM insertion
- Vitest for unit tests, Playwright for E2E

### General
- No emojis in the application (user rule)
- Businesslike, terse documentation style
- Bottom-line-first: answer comes first, reasoning after
- Every change must have a corresponding test

---

## Pull Request Process

1. **Create a feature branch** from `main`
2. **Write tests first** (TDD RED phase)
3. **Implement the feature** (GREEN phase)
4. **Run the full test suite** — all tests must pass
5. **Run the linter/build** — TypeScript 0 errors, Vite build clean
6. **Self-review** using the code review checklist
7. **Request review** — do not self-approve
8. **Do not commit without explicit authorization** — worktree changes remain uncommitted until authorized

### Pre-Commit Review Checklist
- [ ] All backend tests pass (`pytest -q`)
- [ ] Frontend tests pass (`npm test`)
- [ ] TypeScript build clean (`tsc && vite build`)
- [ ] No `print()` statements or debug code left in
- [ ] No secrets or credentials committed
- [ ] Database migrations are backward compatible
- [ ] Audit events logged for all state-changing operations
- [ ] Separation of duties enforced (proposer ≠ approver)
- [ ] Documentation updated if user-facing behavior changes

---

## Repository Structure

```
aviation-dms/
├── backend/
│   ├── app/
│   │   ├── main.py          # App entry, CORS, security headers, auth middleware
│   │   ├── p0_auth.py       # Session auth, CSRF, dev identity headers
│   │   ├── p0_routes.py     # P0: documents, versions, change requests, audit
│   │   ├── p1_routes.py     # P1: occurrences, hazards, missions, safety KPIs
│   │   ├── p2_routes.py     # P2: proposals, personnel, aircraft, insurance
│   │   ├── p3_routes.py     # P3: audit reports, provenance imports
│   │   ├── rbac.py          # Role-based access control (16 roles)
│   │   ├── audit.py         # Audit trail logging
│   │   ├── database.py      # SQLite schema, seed data
│   │   ├── notifications.py # Deadline/expiry notifications
│   │   ├── upload_safety.py # ClamAV INSTREAM scanning
│   │   ├── upload_validation.py # Isolated validator client
│   │   ├── watermark.py     # Identity-bound watermarking
│   │   └── backup_validation.py # Backup/restore validation
│   ├── data/                # SQLite DB + uploads (gitignored)
│   └── tests/               # pytest suite
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Routes
│   │   ├── api/client.ts    # Authenticated axios client
│   │   ├── components/      # UI components
│   │   ├── pages/           # Route pages
│   │   └── test/            # Vitest setup
│   ├── e2e/                 # Playwright E2E tests
│   └── vitest.config.ts
├── docs/
│   ├── adr/                 # Architecture Decision Records
│   ├── API-REFERENCE.md
│   ├── PRODUCTION-DEPLOYMENT.md
│   ├── THREAT-MODEL.md
│   ├── DATA-RETENTION-POLICY.md
│   ├── DISASTER-RECOVERY.md
│   └── (onboarding, readiness, pilot docs)
├── docker-compose.yml
├── docker-compose.staging.yml
├── docker-compose.prod.yml
├── Caddyfile.bastion
├── CHANGELOG.md
├── DESIGN.md
└── .gitignore
```

---

## Security Guidelines

### Secrets
- Never commit `.env`, `.env.staging`, `.env.prod`, or secret files
- SMTP passwords and bootstrap tokens are mounted as Docker secrets, never in environment variables
- SSH keys for bastion/production/staging are stored in `~/Downloads/` — never in the repository
- If you accidentally commit a secret, treat it as compromised and rotate immediately

### Authentication
- Development identity headers (`X-Role`, `X-Actor`) are **local-dev only**
- Production uses server-managed HTTP-only sessions with CSRF
- JWT/OIDC is not implemented — do not configure or advertise unused settings

### File Uploads
- All uploads fail closed unless quota, scanner, and size limits are configured
- ClamAV scanning is mandatory before persistence
- SHA-256 integrity verification on all retained files
- No public storage URLs or unrestricted file endpoints

---

## Communication

- All changes are tracked via git commit messages
- Architecture decisions are recorded in `docs/adr/` (ADR format)
- Releases are documented in `CHANGELOG.md`
- Security concerns should be raised with the Backend/IT Lead and System Administrator
- Operational go/no-go decisions require Accountable Manager approval

---

## License

Internal KFL Aviation DMS — operational use only.
