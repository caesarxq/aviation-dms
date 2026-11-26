# Documentation Index

Entry point for the KFL Aviation DMS documentation. The project-wide overview lives in
[`../README.md`](../README.md); deployment and release gates in [`../DEPLOYMENT.md`](../DEPLOYMENT.md).

**Authoritative** documents describe how the system works today. **Historical** documents are
audit records kept for traceability — they are not a worklist.

## Reference

| Document | Purpose |
|---|---|
| [API-REFERENCE.md](API-REFERENCE.md) | Endpoint reference: auth, session lifecycle, P1–P3 routes and their permissions |
| [DATA-RETENTION-POLICY.md](DATA-RETENTION-POLICY.md) | Retention periods, legal holds, disposal |
| [THREAT-MODEL.md](THREAT-MODEL.md) | Assets, actors, threats and mitigations |
| [FORM-UX-AND-QUALITY-PLAN.md](FORM-UX-AND-QUALITY-PLAN.md) | Form UX, accessibility and mutation-testing guidance |
| [PROVENANCE-IMPORT-WALKTHROUGH.md](PROVENANCE-IMPORT-WALKTHROUGH.md) | Importing historical audits with source provenance |
| [DECISIONS.md](DECISIONS.md) | Decision log |

## Operations

| Document | Purpose |
|---|---|
| [PRODUCTION-DEPLOYMENT.md](PRODUCTION-DEPLOYMENT.md) | Production/staging topology, release gates, promotion |
| [DEVOPS-INFRASTRUCTURE-FINDINGS.md](DEVOPS-INFRASTRUCTURE-FINDINGS.md) | Infrastructure findings and remediation status |
| [DISASTER-RECOVERY.md](DISASTER-RECOVERY.md) | Backup, restore and recovery objectives |
| [OFF-HOST-RESTORE-DRILL-REPORT.md](OFF-HOST-RESTORE-DRILL-REPORT.md) | Recorded off-host restore drill |
| [INCIDENT-ESCALATION-CONTACTS.md](INCIDENT-ESCALATION-CONTACTS.md) | Escalation path and contacts |

## User onboarding and pilot

| Document | Purpose |
|---|---|
| [USER-ONBOARDING-PROCEDURE.md](USER-ONBOARDING-PROCEDURE.md) | New-user account setup and first login |
| [ONBOARDING-RUNBOOK.md](ONBOARDING-RUNBOOK.md) | Administrator roster reconciliation and invitations |
| [ONBOARDING-PILOT-PROCEDURE.md](ONBOARDING-PILOT-PROCEDURE.md) | Restricted pilot onboarding flow |
| [ONBOARDING-READINESS-PLAN.md](ONBOARDING-READINESS-PLAN.md) | Readiness plan |
| [ONBOARDING-READINESS-CHECKLIST.md](ONBOARDING-READINESS-CHECKLIST.md) | Go/no-go checklist |
| [PILOT-SCOPE-CONSTRAINTS.md](PILOT-SCOPE-CONSTRAINTS.md) | What the pilot does and does not cover |
| [POST-PILOT-HANDOFF.md](POST-PILOT-HANDOFF.md) | Handoff after the pilot |
| [ONBOARDING-WORKSHOP-DOCUMENT-REGISTER.md](ONBOARDING-WORKSHOP-DOCUMENT-REGISTER.md) | Document register for the training workshop |
| [WORKSHOP-FACILITATOR-GUIDE.md](WORKSHOP-FACILITATOR-GUIDE.md) | Facilitator instructions |
| [WORKSHOP-PARTICIPANT-WORKBOOK.md](WORKSHOP-PARTICIPANT-WORKBOOK.md) | Participant exercises |

## Architecture decisions

| ADR | Decision |
|---|---|
| [ADR-001](adr/ADR-001.md) | SQLite for the production data store |
| [ADR-002](adr/ADR-002.md) | Separate staging and production environments |
| [ADR-003](adr/ADR-003.md) | Caddy on the bastion for TLS termination |
| [ADR-004](adr/ADR-004.md) | Isolated upload-validator container |
| [ADR-005](adr/ADR-005.md) | No JWT/OIDC authentication in this release |
| [ADR-006](adr/ADR-006.md) | Port assignments for staging and production |

## Historical

| Document | Note |
|---|---|
| [WORKFLOW-CONFORMANCE-AUDIT-REPORT.md](WORKFLOW-CONFORMANCE-AUDIT-REPORT.md) | Manual-grounded conformance audit (2026-11-03). Superseded by `../REEVALUATION_REPORT.md`. |
| [WORKFLOW-LOGIC-IMPLEMENTATION-PLAN.md](WORKFLOW-LOGIC-IMPLEMENTATION-PLAN.md) | Implementation plan from that audit (2026-11-03). |
| [READINESS-GATE-RECONCILIATION-2026-11-08.md](READINESS-GATE-RECONCILIATION-2026-11-08.md) | Readiness reconciliation as of 2026-11-08. |

## Training package

`../demo and onboarding pilot/` is a self-contained workshop bundle (decks, controlled manuals,
and a snapshot of this directory). `docs/` is authoritative; the bundle's `documents/` copy is a
frozen snapshot and is not kept in sync automatically.
