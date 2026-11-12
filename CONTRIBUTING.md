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
├── .gitignore
```

---

## Code Knowledge Graph (Graphify)

This project uses [Graphify](https://github.com/Graphify-Labs/graphify) (PyPI: `graphifyy`) to maintain a local, queryable knowledge graph of the codebase. Graphify parses code with tree-sitter AST — fully offline, nothing leaves your machine — and maps cross-file calls, imports, SQL schema relationships, and community structure.

### When to use Graphify

- **Re-orienting after context compaction** — instead of re-reading 20 files, run `graphify explain "<function>" --all` to see all callers and dependents.
- **Change impact analysis** — before editing `database.py` or `rbac.py`, check blast radius: `graphify explain "get_db()"` shows 342 edges across every route module.
- **Refactoring prioritization** — low community cohesion scores (e.g. `p2_routes.py` at 0.05) flag weakly coupled modules that are candidates for splitting.
- **Path tracing** — `graphify path "node-A" "node-B" --undirected` shows the shortest dependency chain between any two functions.

### Procedure

**1. Install (one-time)**
```bash
pip install graphifyy
# or: uv tool install graphifyy
which graphify
```

**2. Extract (code-only, free, offline)**
```bash
# Backend
graphify extract backend/ --code-only

# Frontend
graphify extract frontend/src/ --code-only
```
Output lands in `<path>/graphify-out/`:
- `graph.json` — full graph, queryable via `graphify explain` / `graphify path`
- `GRAPH_REPORT.md` — human-readable summary (god nodes, cohesion, surprising connections)
- `graph.html` — clickable interactive graph in any browser

**3. Regenerate after changes**
```bash
graphify update backend/
graphify update frontend/src/
```
Compare `git rev-parse HEAD` to the commit recorded in `GRAPH_REPORT.md` to check staleness. The CI pipeline (`graphify-extract` job) regenerates these on every push to `main`.

**4. Query**
```bash
graphify explain "transition_version_state" --all
graphify path "app/p0_routes.py:transition_version_state" "app/database.py:init_db" --undirected
```

### Rules

- Graphify output complements — does not replace — human-authored documentation (ADRs, CHANGELOG, threat model).
- **Never commit** `graph.json`, `graph.html`, or `GRAPH_REPORT.md` — they are build artifacts that go stale quickly. They are in `.gitignore`.
- Code-only extraction needs no API key. Docs/PDFs/images semantic extraction requires a configured LLM key (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) — skip with `--code-only`.
- Graphify shows structure; use `read_file` / `grep` for exact line-level inspection.


## Proactive Graphify Method (Agent-Use Standard)

Agents use Graphify **proactively and preemptively** — before every code-editing task — rather than reactively after a problem is found. This is a required step in the agent workflow, not optional.

### Before every code change

Run this sequence against the directory being edited:

**Step 1 — Verify graph freshness**
```bash
git rev-parse HEAD
# Compare to the commit recorded in GRAPH_REPORT.md
graphify update backend/      # or frontend/src/
```

**Step 2 — Assess blast radius**
```bash
graphify explain "<function-or-class-being-changed>" --all
```
Review every caller, importer, and dependent. If a god node like `get_db()` (342 edges) is affected, the change is high-risk.

**Step 3 — Check dependency paths**
```bash
graphify path "<source>" "<target>" --undirected
```
Verify no unintended coupling is introduced, and no new import cycles would be created.

**Step 4 — Re-extract after the change**
```bash
graphify extract backend/ --code-only
graphify cluster-only backend/
```
Confirm the graph still reflects reality before committing.

### Integration points

| Workflow stage | Graphify action |
|---------------|-----------------|
| Task kickoff | `graphify update <path>` + compare `git rev-parse HEAD` to `GRAPH_REPORT.md` commit |
| Before editing any function/class | `graphify explain "<target>" --all` |
| During refactor / module split | `graphify path` to verify no new import cycles |
| PR / self-review | Reviewer checks blast radius output from `graphify explain` |
| CI (automated) | `graphify-extract` job on every push to `main` (see `.github/workflows/deploy.yml`) |

### Rule

**Never edit a function, route, or module without first running `graphify explain` on it.** The graph is the source of truth for structural relationships; human-authored docs (ADRs, CHANGELOG, threat model) remain the source of truth for rationale and policy.


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
