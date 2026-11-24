# Onboarding Workshop — Document Register

Purpose: single index of every document relevant to the pre-onboarding workshop for all DMS users. It records what exists, what is controlled source content, and what must be created before the workshop. This register is an index only — it does not authorize accounts, invites, commits, or deployment.

Status values: Exists (in repo), Controlled source (KFL manual, read-only), Needs creation, Proposed.

## 1. Controlled aviation manuals (source content — read-only)

These are the regulated manuals users will work with in the DMS. Do not alter formatting, identity, or wording.

| Manual | Canonical content | Format | Status | Location |
|---|---|---|---|---|
| Operations Manual (Company ABCD) | KFL 2021 COMPANY ABCD | PDF + pdf2htmlEX HTML | Controlled source | attachments; published as a DMS document |
| Quality Management Systems Manual | KFL QUALITY | PDF + pdf2htmlEX HTML | Controlled source | attachments; published as a DMS document |
| Safety Manual | KFL 2021 SAFETY | PDF + pdf2htmlEX HTML | Controlled source | attachments; published as a DMS document |
| Security Manual | KFL REVISED SECURITY MANUAL | PDF + pdf2htmlEX HTML | Controlled source | attachments; published as a DMS document |
| Dangerous Goods Manual | DANGEROUS GOODS MANUAL KFL 01 may 2025 | PDF + pdf2htmlEX HTML | Controlled source | attachments; published as a DMS document |
| ROC and Ops Spec | KFL ROC & OPSSPEC 2027 | PDF | Controlled source | attachments; published as a DMS document |
| Drone Mission Sheet | KFL_Drone_Mission_Sheet | DOCX | Controlled source | attachments |
| Drone Risk Assessment | KFL_Drone_Risk_Assessment | DOCX | Controlled source | attachments |
| Safety and Security Audit Report (Sept 2026) | SAFETY AND SECURITY SEPTEMBER 2026 AUDIT REPORT | PDF | Controlled source | attachments; provenance-import subject |

## 2. Workshop and pilot controls documents (exist)

The eight pilot documents defined by the onboarding procedure.

| Document | Audience | Format | Status | Location |
|---|---|---|---|---|
| Onboarding Readiness Checklist | Facilitator, system admin | Markdown | Exists | docs/ONBOARDING-READINESS-CHECKLIST.md |
| Pilot Scope and Constraints | All participants | Markdown | Exists | docs/PILOT-SCOPE-CONSTRAINTS.md |
| Onboarding Pilot Procedure (technical runbook) | System admin, backend/IT | Markdown | Exists | docs/ONBOARDING-PILOT-PROCEDURE.md |
| Workshop Facilitator Guide | Facilitator | Markdown | Exists | docs/WORKSHOP-FACILITATOR-GUIDE.md |
| Workshop Participant Workbook | All participants | Markdown | Exists | docs/WORKSHOP-PARTICIPANT-WORKBOOK.md |
| Provenance Import Walkthrough | system admin, independent auditor | Markdown | Exists | docs/PROVENANCE-IMPORT-WALKTHROUGH.md |
| Post-Pilot Handoff Memo | Operations team | Markdown | Exists | docs/POST-PILOT-HANDOFF.md |
| Incident and Escalation Contacts | All users | Markdown | Exists | docs/INCIDENT-ESCALATION-CONTACTS.md |
| Onboarding Readiness Plan | Facilitator | Markdown | Exists | docs/ONBOARDING-READINESS-PLAN.md |
| Onboarding Runbook | System admin | Markdown | Exists | docs/ONBOARDING-RUNBOOK.md |
| User Onboarding Procedure | All users | Markdown | Exists | docs/USER-ONBOARDING-PROCEDURE.md |
| Readiness Gate Reconciliation (2026-11-08) | Facilitator, owner | Markdown | Exists | docs/READINESS-GATE-RECONCILIATION-2026-11-08.md |

## 3. User manuals (per function / workflow)

One manual per workflow, each mapped to the roles that use it. A single generic procedure exists today; the per-workflow manuals below are the target set for the workshop.

| User manual | Covers (DMS features) | Primary roles | Format | Status |
|---|---|---|---|---|
| Getting Started and Account Setup | Login, Welcome, Profile, Change Password, Notifications | All users | Markdown | Exists (docs/USER-ONBOARDING-PROCEDURE.md) |
| Reading and Searching Controlled Documents | Document Catalogue, Document Viewer, outline, Version Diff | All users | Markdown | Needs creation |
| Document Registration and Metadata | Catalogue create/edit, classifications, permissions | librarian, head_quality | Markdown | Needs creation |
| Distribution and Acknowledgement | Document Distributions, acknowledgement tracking | librarian, records_custodian | Markdown | Needs creation |
| Change Requests and Proposals | Change Requests, Document Proposals, Version Diff | librarian, editor roles | Markdown | Needs creation |
| Quality Audits and Findings | Quality Audits, Audit Findings, Audit Reports | head_quality, independent_auditor | Markdown | Needs creation |
| Compliance and Audit Trail | Compliance Dashboard, Audit Trail, Audit Dashboard | head_quality, accountable_manager | Markdown | Needs creation |
| Safety Occurrences and Investigations | Occurrences, Occurrence Detail, Investigations, Hazards | head_safety, occurrence_reporter | Markdown | Needs creation |
| Safety Actions and Security Records | Safety Actions, Security Management | head_safety, head_security | Markdown | Needs creation |
| Crew and Training Management | Crew Management, Crew Qualifications, Duty Time, Training | head_training, crew roles | Markdown | Needs creation |
| Licences and Renewals | Personnel Licences, Renewal Progress | head_training, records_custodian | Markdown | Needs creation |
| Maintenance and Fleet | Maintenance Management, Aircraft Insurance, ROC Register | head_maintenance, chief_pilot | Markdown | Needs creation |
| Operations and Dangerous Goods | Missions, Risk Assessments, Dangerous Goods, Self-Service Upload | head_operations, dg_coordinator, flight_ops_officer | Markdown | Needs creation |
| Audit Provenance Import | Provenance import workflow, role separation | system admin, independent_auditor | Markdown | Exists (docs/PROVENANCE-IMPORT-WALKTHROUGH.md) |

## 4. System administrator manual (exists)

| Document | Audience | Format | Status | Location |
|---|---|---|---|---|
| Onboarding Runbook (bootstrap, invites, setup) | System admin | Markdown | Exists | docs/ONBOARDING-RUNBOOK.md |
| Onboarding Pilot Procedure (technical runbook) | System admin, backend/IT | Markdown | Exists | docs/ONBOARDING-PILOT-PROCEDURE.md |
| Production Deployment and Operational Release | System admin, IT | Markdown | Exists | docs/PRODUCTION-DEPLOYMENT.md |
| Disaster Recovery | System admin, IT | Markdown | Exists | docs/DISASTER-RECOVERY.md |
| Off-Host Restore Drill Report | System admin, owner | Markdown | Exists | docs/OFF-HOST-RESTORE-DRILL-REPORT.md |
| Admin Observability (page reference) | System admin | In-app page | Exists | Admin Observability page |

## 5. System guide presentations (decks)

No presentation decks exist yet. Proposed set for the workshop; each should be short, role-focused, and align to the Facilitator Guide agenda.

| Deck | Audience | Covers | Format | Status |
|---|---|---|---|---|
| Executive Overview and Pilot Scope | All | Why, scope, roles, go/no-go | Slides | Needs creation |
| DMS Walkthrough — All Users | All users | Login, catalogue, viewer, notifications, profile | Slides + demo | Needs creation |
| Role-Based Deep Dives (per workflow) | Per role | One deck per section 3 manual | Slides + demo | Needs creation |
| System Administration and Operations | System admin, IT | Deployment, backup/restore, observability, incident response | Slides | Needs creation |
| Provenance Import Demonstration | Auditor, quality | Stage, review, verify, reject | Slides + demo | Needs creation |

## 6. Reference and control documents (exist)

| Document | Audience | Status | Location |
|---|---|---|---|
| API Reference | Integrators, system admin | Exists | docs/API-REFERENCE.md |
| Threat Model | Security, system admin | Exists | docs/THREAT-MODEL.md |
| Data Retention Policy | records_custodian, quality | Exists | docs/DATA-RETENTION-POLICY.md |
| DevOps Infrastructure Findings | IT, system admin | Exists | docs/DEVOPS-INFRASTRUCTURE-FINDINGS.md |
| Form UX and Quality Plan | Quality, product | Exists | docs/FORM-UX-AND-QUALITY-PLAN.md |
| Workflow Conformance Audit Report | Quality | Exists | docs/WORKFLOW-CONFORMANCE-AUDIT-REPORT.md |
| Workflow Logic Implementation Plan | Engineering | Exists | docs/WORKFLOW-LOGIC-IMPLEMENTATION-PLAN.md |
| Decisions (ADR) | All | Exists | docs/DECISIONS.md, docs/adr/ |
| Entity Relationship Diagram | Engineering | Exists | docs/ER-DIAGRAM.html |

## 7. Gaps to close before the workshop

| Gap | Type | Owner | Needed for |
|---|---|---|---|
| 13 per-workflow user manuals (section 3) | User manuals | Product/quality | Role-based workshop sessions |
| 5 presentation decks (section 5) | Presentations | Facilitator | All workshop sessions |
| Per-role preparation sheets mapped to the participant workbook | Workbook addendum | Facilitator | Pre-workshop preparation |

## Notes

- Preserve canonical identities and role assignments; do not normalize `u-safety/security` or `Brian Swanya`.
- Controlled manuals are read-only; never summarize, truncate, or rewrite them.
- Retention and legal-hold content is report-only; no automatic file disposition.
- This register does not authorize invitations, account changes, commits, or deployment.
