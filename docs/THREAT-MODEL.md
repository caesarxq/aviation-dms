# Aviation DMS — Threat Model

**Version:** 1.0
**Date:** 2026-11-12
**Scope:** Aviation DMS production deployment (staging `10.20.4.234`, production `10.20.1.69`, bastion `145.241.152.126`)
**Classification:** Internal — not a controlled manual, not an operational release

---

## 1. System Overview

The Aviation DMS is a FastAPI + React document management system for KCAA-regulated UAS operations. It manages controlled documents, safety occurrences, personnel credentials, audit reports, and compliance records. The architecture consists of:

- **Backend** (FastAPI, Python 3.11, SQLite) — API, auth, RBAC, document control, uploads
- **Frontend** (React 18, TypeScript, Vite) — browser UI
- **Upload-validator** — isolated container for malware scanning and file validation (UID 10002, read-only root, no DB access)
- **Clamd** — ClamAV antivirus daemon (internal network, no host port)
- **Caddy (bastion)** — TLS termination and reverse proxy for `roc.kfl.ke` and `stage.kfl.ke`
- **SQLite database** — single file at `/app/data/dms.db`, plus `/app/data/uploads/`, `/app/data/kcaa-evidence/`, `/app/data/attachments/`
- **Backup server** — `10.20.173.120` for off-host backups

---

## 2. Trust Boundaries

| Boundary | Description | Controls |
|----------|-------------|----------|
| **Browser → Caddy** | Public HTTPS to bastion | TLS 1.2+, HSTS, security headers, Caddy rate limits |
| **Caddy → Backend** | Bastion to production backend (private IP) | `X-Forwarded-For` only honored from bastion IP `145.241.152.126/32` |
| **Backend → Upload-validator** | Internal Compose network | Isolated `upload_validator` network, no host port, backend fails closed if unreachable |
| **Backend → Clamd** | Internal Compose network | Clamd on port 3310, not published to host, INSTREAM scan only |
| **Backend → SQLite** | Local filesystem | Database file read/write by backend UID 10001 only |
| **Admin → Bastion** | SSH via key | `ssh-key-2026-11-06-2.key` / `ssh-key-2026-11-11-2.key`, bastion proxy to instances |

---

## 3. Threat Enumeration (STRIDE)

### Spoofing

| ID | Threat | Asset | Impact | Likelihood | Mitigation |
|----|--------|-------|--------|------------|------------|
| T-01 | Attacker spoofs `X-Forwarded-For` to bypass IP-based trust | Backend | High — unauthorized access via trusted-IP path | Low | `X-Forwarded-For` only honored from bastion IP `145.241.152.126/32`; backend uses peer address otherwise |
| T-02 | Attacker impersonates a user via stolen session cookie | User sessions | High — account takeover | Medium | HTTP-only, SameSite=Strict, Secure cookies; CSRF double-submit; 8h sliding / 24h absolute session TTL |
| T-03 | Attacker reuses a revoked setup token or invite code | Auth system | Medium — unauthorized account creation | Low | Single-use tokens, 24-hour expiry, rate limiting (5/actor/15min) |
| T-04 | Attacker spoofs source auditor identity in P3 provenance import | Audit reports | High — false attribution of audit findings | Low | Alias-aware separation: source auditor, auditee, importer, verifier must be four distinct principals; verifier permission unavailable to `system_admin` |

### Tampering

| ID | Threat | Asset | Impact | Likelihood | Mitigation |
|----|--------|-------|--------|------------|------------|
| T-05 | Attacker modifies uploaded file after malware scan but before persistence | Uploaded files | High — malicious file persists | Low | Hash computed server-side at scan time; SHA-256 verified on download; file not persisted until scan passes |
| T-06 | Attacker changes document version state without approval | Document versions | High — uncontrolled document publication | Medium | State transitions enforced server-side; `draft → in_review → approved → kcaa_approved → published`; creator cannot approve/publish own version; audit event on every transition |
| T-07 | Attacker modifies SQLite database file directly | Database | Critical — data integrity loss | Low | File permissions restricted to backend UID 10001; no direct host access to `/app/data` volume |
| T-08 | Attacker alters audit events after creation | Audit trail | Critical — loss of accountability | Medium | `audit_events` table is append-only; no update/delete endpoints; events recorded transactionally with state changes |

### Repudiation

| ID | Threat | Asset | Impact | Likelihood | Mitigation |
|----|--------|-------|--------|------------|------------|
| T-09 | User denies performing a state-changing action | Audit trail | High — cannot attribute actions | Low | Every state-changing endpoint logs `audit_event` with actor, action, target, timestamp; sessions tied to canonical user IDs |
| T-10 | Importer denies staging a P3 audit import | Provenance imports | Medium — disputed import origin | Low | Import operator recorded on candidate; verifier must be distinct principal; verification rechecks candidate state under short transaction |

### Information Disclosure

| ID | Threat | Asset | Impact | Likelihood | Mitigation |
|----|--------|-------|--------|------------|------------|
| T-11 | Attacker accesses KCAA evidence or personnel credentials without authorization | Uploaded files | High — sensitive aviation/HR data exposure | Medium | File endpoints require authentication and role-based permissions; downloads verify size/hash from bounded snapshot; no public storage URLs |
| T-12 | Attacker reads sensitive investigation notes (`investigation_notes`) | Security incidents | Medium — SSI exposure | Low | `investigation_notes` masked as `[SSI REDACTED]` for callers without `security:read_sensitive`; permission granted to `head_security`, `head_safety` (alternate), `accountable_manager`, `system_admin` |
| T-13 | Attacker enumerates users via password reset or login | Auth system | Medium — account enumeration | Low | Generic responses (no enumeration); forgot-password returns generic message; login failures rate-limited |
| T-14 | Attacker intercepts traffic between bastion and production instance | Network traffic | Medium — credential/session interception | Low | Traffic over private IP via bastion proxy; Caddy TLS termination at bastion |

### Denial of Service

| ID | Threat | Asset | Impact | Likelihood | Mitigation |
|----|--------|-------|--------|------------|------------|
| T-15 | Attacker floods upload endpoint with large files | Storage / backend | Medium — storage exhaustion, upload unavailability | Low | Per-file limits (10 MiB), system quota (30 GB), two-request semaphore per backend process, reverse-proxy body limits (10 MiB API / 1 MiB frontend) |
| T-16 | Attacker exhausts ClamAV scanner with malicious files | Clamd | Medium — upload failures | Low | 7-second validation deadline, chunked send/read with cancellation, 60s scan timeout, fail-closed on scanner outage |
| T-17 | Attacker exhausts backend connections | Backend | High — API unavailability | Low | Rate limiting (100 req/min per client), session TTL caps, process-local request semaphore |

### Elevation of Privilege

| ID | Threat | Asset | Impact | Likelihood | Mitigation |
|----|--------|-------|--------|------------|------------|
| T-18 | User with `document:read` acknowledges another holder's distribution | Distributions | Medium — false acknowledgement records | Low | `acknowledge_distribution` enforces `actor == recipient_id` or `distribution:manage`/`system_admin` |
| T-19 | Change proposer approves their own change request | Change requests | High — SoD bypass | Medium | `update_change_request` enforces `requester_id != actor`; state transition map enforced |
| T-20 | `system_admin` verifies P3 import (should be `independent_auditor` only) | Provenance imports | High — unverified audit import | Low | `verify_audit_report_import` restricted to `independent_auditor`; explicit alias-aware separation checks |
| T-21 | User accesses `DEV_MODE` identity headers in production | Auth system | Critical — unauthorized role assumption | Low | `DEV_MODE` header fallback disabled in production; development-only identity headers rejected |

---

## 4. Data Flow Diagram (Trust Boundaries)

```
┌─────────────┐     HTTPS/TLS     ┌─────────────┐
│   Browser   │───────────────────│   Caddy     │
│  (Client)   │  roc.kfl.ke:443   │ (Bastion)   │
└─────────────┘                   └──────┬──────┘
                                        │ X-Forwarded-For (trusted only from 145.241.152.126/32)
                                        │
                                        │ internal (10.20.1.69:8000/8080)
                                        ▼
                              ┌─────────────────┐
                              │   Backend       │
                              │  (FastAPI)      │
                              │  UID 10001      │
                              └──────┬──────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
        ┌──────────┐          ┌──────────┐          ┌──────────┐
        │  SQLite  │          │ Upload-  │          │  Clamd   │
        │  dms.db  │          │ validator│          │  (INSTREAM)│
        │ UID 10001│          │ UID 10002│          │  port 3310│
        └──────────┘          │ read-only │          │ internal │
                              │ root FS   │          │ no host  │
                              │ isolated  │          │ port     │
                              └──────────┘          └──────────┘
                                    │
                                    │ internal network only
                                    ▼
                              ┌──────────┐
                              │  Backup  │
                              │  server  │
                              │ 10.20.173│
                              │ .120     │
                              └──────────┘
```

---

## 5. Security Controls Summary

| Control | Implementation |
|---------|---------------|
| **Authentication** | Opaque server-managed sessions, HTTP-only cookies, CSRF double-submit |
| **Authorization** | 16 roles, explicit permission allow-lists, SoD enforcement |
| **Transport security** | TLS via Caddy on bastion, HSTS, security headers |
| **Input validation** | Pydantic models, per-file size limits, body size caps |
| **Malware scanning** | ClamAV INSTREAM, isolated validator container, fail-closed |
| **File integrity** | SHA-256 at scan time, verified on download, bounded snapshots |
| **Audit logging** | Immutable `audit_events`, transactional with state changes |
| **Network isolation** | Upload-validator on internal network, clamd port not published |
| **Resource bounds** | Memory, CPU, PID, file descriptor limits on all containers |
| **Secret management** | Mounted Docker secrets (bootstrap token, SMTP password), no env var secrets |

---

## 6. Residual Risks (Accepted / Monitored)

| Risk | Status | Owner | Review |
|------|--------|-------|--------|
| Bastion is single point of failure for production HTTPS | Accepted | System Administrator | Quarterly |
| Single SQLite instance (no replication) | Accepted | Backend/IT Lead | Before scaling |
| Sessions tied to single server instance | Accepted | Backend/IT Lead | Before multi-instance |
| Reverse-proxy body limits not validated under load | Open — backlog item | Backend/IT Lead | Before production go/no-go |
| Off-host restore drill not yet completed | Open — blocker | Accountable Manager | Before operational go/no-go |

---

## 7. Review Cycle

This threat model is reviewed:
- Before any production deployment or promotion
- When new API endpoints or user roles are added
- After any security incident or near-miss
- At least quarterly during operational use

**Reviewers:** Backend/IT Lead, System Administrator, Records Custodian, Accountable Manager
