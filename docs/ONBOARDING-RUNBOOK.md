# KFL Aviation DMS — Onboarding Runbook

## Overview

All 15 canonical active accounts start with no password set. Onboarding is a two-phase process:

1. **Bootstrap**: `u-admin` onboards first via the bootstrap endpoint (DEV_MODE loopback only).
2. **Invite**: `u-admin` issues setup tokens/invite codes for the remaining 14 accounts.

Each account then completes a guided welcome flow to set their password and confirm their active role.

## Canonical Accounts

| User ID | Primary Role | Additional Roles |
|---|---|---|
| u-admin | system_admin | — |
| u-lib | librarian | head_quality, records_custodian |
| u-safety | head_safety | head_security |
| u-ops | head_operations | chief_pilot, head_training |
| u-flight-ops | flight_ops_officer | dg_coordinator |
| u-accountable | accountable_manager | — |
| u-auditor | independent_auditor | — |
| u-reporter | occurrence_reporter | — |

Merged/legacy accounts are inactive and cannot authenticate.

## Phase 1 — Bootstrap (u-admin only)

In DEV_MODE, bootstrap is available from loopback (`127.0.0.1`) without a bootstrap token:

```
POST /api/p0/auth/bootstrap
Content-Type: application/json

{
  "username": "u-admin",
  "password": "<min 12 chars, max 72 UTF-8 bytes>"
}
```

Response: session cookie is set; `u-admin` is now authenticated.

**Production**: Bootstrap requires `KFL_BOOTSTRAP_TOKEN` environment variable. The token must be provided in the `Authorization: Bearer <token>` header.

## Phase 2 — Admin Issues Invite Codes

As `u-admin`, invite each remaining account:

```
POST /api/p0/auth/invites
Cookie: __Host-kfl_session=<session>; __Host-kfl_csrf=<csrf>
X-CSRF-Token: <csrf>
Content-Type: application/json

{
  "username": "u-lib",
  "email": "librarian@kfl.example.com",
  "roles": ["librarian", "head_quality", "records_custodian"]
}
```

Response includes the invite code (e.g., `KFL-ABCD-1234`) and setup URL.

Rate limit: max 5 invite requests per actor per 15 minutes.

## Phase 3 — Account Setup (each user)

Each user navigates to their setup URL:

```
GET /setup/invite/<invite-code>
```

They enter their username and a new password (min 12 chars, max 72 UTF-8 bytes). The setup token is single-use and expires after 24 hours.

## Phase 4 — Guided Welcome (first login)

On first login, if `onboarding_completed` is `false`, the user is redirected to `/welcome`, which shows:

1. Name and canonical account ID
2. Assigned roles with descriptions
3. Active-role selector (for multi-role accounts)
4. Completion button

After completing welcome, `onboarding_completed` is set to `true` and the user is redirected to their appropriate post-login destination.

## Post-Login Destinations by Role

| Role(s) | Landing Route |
|---|---|
| head_safety, head_security | `/` (Dashboard) |
| Any with document:read | `/documents` |
| Any with roc:read | `/roc` |
| Any with personnel:read | `/personnel-licenses` |
| Any with aircraft:read | `/aircraft-insurance` |
| No matching permission | `/account/security` |

## Rate Limits & Security

- Invite codes: single-use, 24-hour expiry
- Reset tokens: short-lived, single-use
- Forgot password: generic response (no account enumeration)
- Login failures: 5 attempts per 15-minute window → 15-minute lockout
- Invite requests: 5 per actor per 15-minute window → 15-minute lockout

## Troubleshooting

| Symptom | Cause | Resolution |
|---|---|---|
| "Active user not found" on invite | Username doesn't exist or is inactive | Verify username; check `is_active` and `merged_into_user_id IS NULL` |
| "Invite requests temporarily unavailable" | Rate limit exceeded | Wait 15 minutes or use a different admin actor |
| Setup token expired | Token older than 24 hours | Admin issues a new invite code |
| Blank page after login | Session cookie missing or invalid | Clear cookies, re-login via `/login` |
| Cannot switch role | Role not assigned to account | Admin assigns role via `/api/p0/auth/users/{user_id}/roles` |
