# KFL Aviation DMS — API Reference

## Authentication

All API routes are prefixed with `/api/p0`, `/api/p1`, or `/api/p2`. Authentication is **session-cookie based** (HTTP-only `__Host-kfl_session` + `__Host-kfl_csrf` CSRF pair). JWT/Bearer authentication is **not implemented** in this release.

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
| `/api/p0/auth/invites` | POST | Issue a one-time invite code (max 5 per actor per 15 min) | `settings:manage` |

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
| `/api/p2/maintenance-records` | GET/POST | List/create maintenance records | `aircraft:read`/`aircraft:manage` |
| `/api/p2/aircraft-insurance` | GET/POST | List/create aircraft insurance records | `aircraft:read`/`aircraft:manage` |

## Role-Based Access Control

16 roles are defined with explicit permission allow-lists. Unknown roles receive no permissions.

| Role | Access Level | Key Permissions |
|---|---|---|
| system_admin | L4 | All permissions |
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
| independent_auditor | L2 | Audit manage, safety read only |
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
