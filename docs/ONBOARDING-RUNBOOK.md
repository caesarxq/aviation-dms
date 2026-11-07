# KFL Aviation DMS — Onboarding Runbook

## Overview

For the current readiness gates and roster-reconciliation sequence, see [Onboarding Readiness and Roster Plan](ONBOARDING-READINESS-PLAN.md). For end-user setup and first-use instructions, see [User Onboarding Procedure](USER-ONBOARDING-PROCEDURE.md). This runbook remains the administrator's controlled provisioning procedure.

## Staging account snapshot (as of 2026-11-06)

The **read-only staging snapshot as of 2026-11-06** recorded 1 active, onboarded canonical account: user ID `u-admin`, sign-in username `admin`, role `system_admin`; no other members had been invited at that time. Source: read-only staging account inspection. This is a dated snapshot, not a current-state assertion; revalidate against the authorized account inventory before provisioning. The role profiles below are the planned mapping, not a count of invited/onboarded users. Do not issue invitations until the authoritative roster is confirmed and the controlled manuals and conducted safety audit are reconciled.

In that snapshot, the seven non-admin canonical profiles were retained as pre-seeded, passwordless accounts and inactive; merged legacy accounts were also inactive. A database `is_active` flag alone is not evidence that a person has been invited or onboarded. Preserve the confirmed person-to-role mapping; reconcile the invite roster before activating additional members.

**Fresh-install difference:** the clean database seed inserts canonical profiles active by default; identity consolidation deactivates merged rows but does not reproduce this staging snapshot's one-active-account state. Before any clean-install invitation, inspect the actual target database and reconcile its roster through the approved procedure. Do not assume this staging snapshot or a seed `is_active` value proves invitation or onboarding.

## Owner-approved canonical role profiles

The project owner confirmed these canonical IDs and role assignments on 2026-11-07. This mapping is authoritative for planning; account activation and invitation status are separate and must not be inferred from this table.

| User ID | Primary Role | Additional Roles |
|---|---|---|
| u-admin | system_admin | head_maintenance |
| u-quality | head_quality | librarian, records_custodian |
| u-safety/security | head_safety | head_security |
| u-ops | head_operations | chief_pilot, head_training |
| u-flight-ops | flight_ops_officer | dg_coordinator |
| u-accountable | accountable_manager | — |
| u-auditor | independent_auditor | — |
| u-reporter | occurrence_reporter | — |

**Historical status snapshot:** In the read-only staging snapshot dated 2026-11-06, only `u-admin` was onboarded and the other canonical profiles were inactive. Do not use that dated status as a current account-state assertion. Legacy IDs remain aliases for historical records and compatibility; they are not separate approved accounts.

## Phase 1 — Initial administrator bootstrap

The staging administrator had completed this phase in the 2026-11-06 snapshot. For a fresh deployment, first query `GET /api/p0/auth/bootstrap-status`; proceed only when `setup_required`, `bootstrap_configured`, and `bootstrap_token_required` are true. Open `/setup` and enter the one-time token read directly from the protected file configured by `KFL_BOOTSTRAP_TOKEN_FILE`, then choose a password of at least 12 characters and no more than 72 UTF-8 bytes. The form sets the seeded `u-admin` account (sign-in username `admin`) and creates its session. The token is submitted in the bootstrap request body by the UI; it is not a bearer header and must never be shared in chat or stored in this document.

After success, verify `setup_required` is false and invalidate the consumed token. Do not reset the database to repeat bootstrap. Local `DEV_MODE` loopback bootstrap is for development only and is not the production/staging procedure.

## Phase 2 — Member invites (not started)

No member invitations had been issued as of the 2026-11-06 snapshot. The project owner has since confirmed the live roster and role mapping are accurate; source manuals, safety-audit evidence, backup/restore, technical controls, and postholder approvals remain outstanding. The current ordering has a dependency: creating an audit report through the P3 API requires an active `independent_auditor`, while the snapshot recorded only the administrator active and this phase says to wait until the audit is loaded. Obtain an explicit decision on the approved audit-provisioning path before activating or inviting an auditor. After the remaining gates and explicit go/no-go, the `system_admin` issues one invitation per approved person:

Before issuing an invite, verify that the approved canonical account is active through the authorized roster-reconciliation procedure. The invite endpoint returns 404 for inactive profiles. Do not activate a pre-seeded profile merely to make an invite succeed; if the approved account is still inactive and no authorized activation procedure is available, stop and obtain an operational decision.

```
POST /api/p0/auth/invites
Cookie: __Host-kfl_session=<session>; __Host-kfl_csrf=<csrf>
X-CSRF-Token: <csrf>
Content-Type: application/json

{
  "username": "<approved-username>"
}
```

The invite endpoint selects an existing active account by username; it does not update the account's email or roles from the request. Reconcile and verify those fields through the authorized account/role-management workflow first. The response includes the one-time invite code and setup URL; deliver each only to that person through the approved channel.

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
2. Department, or a prompt to confirm it if not listed
3. Assigned roles
4. Active-role selector (for multi-role accounts)
5. Completion button

After completing welcome, `onboarding_completed` is set to `true` and the user is redirected to the active role's workspace. A small, dismissible workspace guide then explains the role shortcuts, **All modules**, and role switching. Its dismissal is stored in that browser profile under the canonical user ID; clearing site storage or using another browser may show it again. It does not change permissions. See the user procedure for the guide's details.

## Post-Login Destinations by Role

| Role | Landing Route |
|---|---|
| system_admin | `/admin/observability` |
| accountable_manager | `/organization-overview` |
| librarian, records_custodian, as_contracted | `/documents` (for `as_contracted`, only if its shared baseline permissions are approved; it is not contract-scoped) |
| head_quality | `/audit-dashboard` |
| head_safety | `/safety-actions` |
| head_security | `/security-reviews` |
| head_operations, chief_pilot, flight_ops_officer | `/missions` |
| head_training | `/training` |
| head_maintenance | `/maintenance` |
| dg_coordinator | `/dangerous-goods` |
| occurrence_reporter | `/occurrences` |
| independent_auditor | `/audit-reports` |

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
