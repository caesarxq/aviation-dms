# KFL Aviation DMS — Onboarding Readiness and Roster Plan

**Status:** Planning approved; project owner confirms the live roster is accurate (2026-11-07). This is an owner attestation, not an agent-side read of live account rows.

**Execution guard:** The owner-approved canonical-ID and role corrections may be implemented in local code and documentation with a versioned migration. This does not authorize live account activation, invitations, direct live role changes, staging deployment, operational use, audit import, or flight release.

## Situation

### Verified repository facts

- `docs/ONBOARDING-RUNBOOK.md:7-17` records a **read-only staging snapshot dated 2026-11-06**: one active/onboarded canonical account (`u-admin`) and no member invitations at that time. The document explicitly says this is not a current-state assertion.
- The owner-approved canonical mapping is now recorded in `docs/ONBOARDING-RUNBOOK.md:15-30`: `u-quality` is primary `head_quality`, and the literal `u-safety/security` is primary `head_safety`. A versioned v2 migration promotes those IDs while retaining legacy aliases; v1 identity groups in `backend/app/database.py` are deliberately kept for upgrade compatibility. This is an implementation check, **not an independent read of live account rows**.
- The clean-install seed does not reproduce the one-active-account staging snapshot; the runbook warns that seeded `is_active` values are not invitation/onboarding evidence.
- `as_contracted` is a shared baseline with `document:read`, `safety:read`, `roc:read`, and `aircraft:read` (`backend/app/rbac.py:102`). The application does not enforce contract-specific or function-specific access for that role.
- `FLIGHT_RELEASE_ENABLED` defaults to `false` (`backend/app/p1_routes.py:20`). Production guidance keeps release and other controlled operations inactive pending accountable-postholder sign-off (`docs/PRODUCTION-DEPLOYMENT.md:81-90`).
- Production guidance still lists upload quota, malware scanning, retention, orphan-file recovery, and a tested off-host restore as outstanding (`docs/PRODUCTION-DEPLOYMENT.md:11-12, 66-77`). Audit provenance and legacy evidence also require controlled reconciliation (`docs/PRODUCTION-DEPLOYMENT.md:52-56`).

### Roster reconciliation result so far

The project owner states that they are the authoritative source and that the live roster is accurate. The repository's 2026-11-06 snapshot remains historical and does not establish today's counts or invite states. The public staging site presented a sign-in page; no saved login was available, and no credentials were requested or entered. Therefore this plan accepts the owner's attestation, but does not claim the agent independently read the live account rows.

## Sequenced plan

| Step | Owner role | Dependency | Definition of done |
|---|---|---|---|
| 1. Record and apply owner roster confirmation | Project owner + system administrator | Owner confirmation received; no new roster source requested | Record the confirmation date and owner. For any chosen pilot or invite, check that person's canonical ID, username, name, department, assigned roles, and current status against the live roster. Do not infer approval from a seed row or the 2026-11-06 snapshot. |
| 2. Apply the owner-approved identity map | Backend/IT owner + system administrator | Step 1 recorded | Use the runbook's owner-approved primary/additional role mapping. The v2 migration preserves current login identifiers, account status, and password hashes; invalidates existing sessions/setup tokens; remaps structured foreign keys; and retains legacy aliases for historical actor references. Do not execute this migration on staging until separately authorized. |
| 3. Resolve contractor scope | System administrator + contract/function owner | Named contractor roster and job/function scope | Either approve the complete shared `as_contracted` baseline for each named person or keep that person inactive. Do not describe or use the role as contract-scoped until backend authorization and data queries enforce that scope. Do not broaden its grants by default. |
| 4. Close technical and operational gates | Backend/IT/security owner + accountable postholders | Current roster and approved sources available | Complete the deployment prerequisites: file scanning, cumulative quota, retention/legal hold, orphan reconciliation, off-host backup and restore drill, and production configuration checks. Independently validate source manuals, audit evidence/provenance, and workflow source-to-rule mappings. Keep flight release disabled until sign-off. |
| 5. Run a controlled, non-operational pilot | System administrator + a small, approved pilot cohort | Steps 1–4 accepted; separate isolated test/staging database and dedicated test accounts | Verify invitation/setup, welcome identity and role confirmation, correct role landing, permission-denied paths, one-time guide behavior, sign-out/reset support, audit trace, and account revocation. Use no operational flight or production data. |
| 6. Review pilot and authorize rollout | Accountable manager/postholders + system administrator | Pilot evidence and issues log | Close pilot defects, confirm support/escalation ownership, obtain an explicit go/no-go, then issue individual invitations in approved batches. Preserve the approved role mappings and monitor first-use issues. |

## Pilot acceptance checklist

- [ ] The roster source, owner, and as-of date are recorded.
- [ ] Each invited account maps to one approved canonical user and approved roles.
- [ ] The displayed name, canonical ID, department, and roles match the approved record.
- [ ] Active-role permissions are isolated; permitted and denied routes/API operations behave as approved.
- [ ] The workspace guide appears after onboarding, dismisses per user/browser profile, and does not alter permissions.
- [ ] Password reset, sign-out, support escalation, and rapid account deactivation have named owners and tested procedures.
- [ ] Upload, audit, backup/restore, and operational-source gates are signed off before any operational use.
- [ ] No aircraft or flight operation is released; `FLIGHT_RELEASE_ENABLED=false` remains in force pending formal approval.

## Blockers and decision gates

1. **Owner attestation recorded:** the project owner confirms the live roster is accurate as of 2026-11-07. The agent did not independently inspect live accounts; the dated repository snapshot must not be treated as today's count.
2. **Contractor scope:** the shared `as_contracted` role is not contract-scoped. Do not use it for a person whose approved work does not justify all four baseline read permissions.
3. **Operational readiness:** outstanding upload controls, off-host restore verification, source/manual reconciliation, and accountable-postholder approvals remain release blockers.
4. **Audit import:** no import has been performed. The import code's checksum and reconciliation flags are operator attestations; they do not themselves prove source authenticity or content reconciliation. Do not import until those checks and the authorized provisioning path are independently confirmed.
5. **Deployment:** staging remains held. Local tests and this plan do not establish staging, production, aviation, or regulatory readiness.

## First step

Choose the approved pilot cohort from the owner-confirmed live roster and confirm the canonical IDs and assigned roles for those specific people. Do not send passwords, tokens, session cookies, or other credentials. Continue planning only until the remaining technical and postholder gates pass and a separate go/no-go for invitations is given.
